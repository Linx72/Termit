import type { AgentRunEvent, AgentRunRecord } from "@termit/client";

export type GitChangeRef = { status: string; path: string };

export type CompletionBundle = {
  text: string;
  /** Быстрые команды — кнопки под итогом, как follow-up в Cursor. */
  actions: string[];
};

/** Компактная лента шагов агента для чата (как task tape в Cursor). */
export function formatActivityTape(
  locale: "ru" | "en",
  run: AgentRunRecord,
  events: AgentRunEvent[]
): string {
  const shortId = run.run_id.length > 8 ? run.run_id.slice(0, 8) : run.run_id;
  const header =
    locale === "ru"
      ? `Задача · ${shortId} · статус: ${run.state}`
      : `Task · ${shortId} · state: ${run.state}`;

  if (events.length === 0) {
    return locale === "ru"
      ? `${header}\n\n⏳ Ожидаю действия агента…`
      : `${header}\n\n⏳ Waiting for agent activity…`;
  }

  const lines = events.map((ev, index) => {
    const marker = tapeMarker(ev.event_type);
    const msg = ev.message?.trim() || ev.event_type;
    return `${index + 1}. ${marker} ${ev.event_type} — ${msg}`;
  });

  return `${header}\n\n${lines.join("\n")}`;
}

function tapeMarker(eventType: string): string {
  const t = eventType.toLowerCase();
  if (t.includes("tool") || t.includes("read") || t.includes("write") || t.includes("patch")) {
    return "🔧";
  }
  if (t.includes("verify") || t.includes("test")) {
    return "✓";
  }
  if (t.includes("error") || t.includes("fail")) {
    return "✗";
  }
  if (t.includes("think") || t.includes("plan")) {
    return "💭";
  }
  return "•";
}

/** Рекомендации после завершения run — текст + кликабельные follow-up команды. */
export function buildCompletionSuggestions(
  locale: "ru" | "en",
  run: AgentRunRecord,
  events: AgentRunEvent[],
  changes: GitChangeRef[]
): CompletionBundle {
  const verifyFailed = events.some(
    (ev) =>
      ev.event_type.toLowerCase().includes("verify") &&
      /fail|error|не прош/i.test(ev.message ?? "")
  );
  const hasPatch = events.some((ev) =>
    /apply_patch|write_file|patch/i.test(`${ev.event_type} ${ev.message ?? ""}`)
  );

  if (locale === "ru") {
    const lines: string[] = ["### Итог", ""];
    const actions: string[] = [];

    if (run.state === "failed") {
      lines.push("Задача завершилась с ошибкой. Смотрите ленту выполнения выше.");
      actions.push("Исправь ошибку из лога и повтори минимальный fix");
      actions.push("Покажи только diff и объясни причину падения");
      if (run.error) {
        lines.push("", `Ошибка: ${run.error}`);
      }
      return { text: lines.join("\n"), actions };
    }

    if (run.state === "awaiting_confirmation") {
      lines.push("Агент ждёт подтверждения опасной операции.");
      actions.push("Продолжи без опасных команд, только read и patch с preview");
      return { text: lines.join("\n"), actions };
    }

    lines.push(
      run.response?.trim()
        ? run.response.trim().slice(0, 500) + (run.response.length > 500 ? "…" : "")
        : `Готово · статус: ${run.state}.`
    );
    lines.push("");
    lines.push("**Что можно сделать дальше:**");

    if (changes.length > 0) {
      lines.push(`Изменено файлов: ${changes.length} — список справа в Live Changes.`);
    } else if (hasPatch) {
      lines.push("Патчи могли примениться — обновите Live Changes (↻).");
    }

    if (verifyFailed) {
      actions.push("Исправь ошибки verify и перезапусти тесты");
    } else {
      actions.push("Запусти dev-сервер и проверь в браузере");
      actions.push("Добавь unit-тесты для нового кода");
    }
    actions.push("Улучши UI и добавь README");
    actions.push("Подготовь деплой и smoke-check");

    return { text: lines.join("\n"), actions };
  }

  const lines: string[] = ["### Summary", ""];
  const actions: string[] = [];

  if (run.state === "failed") {
    lines.push("The task failed. Review the activity tape above.");
    actions.push("Fix the error from the log with a minimal patch");
    actions.push("Explain the failure and show only the required diff");
    if (run.error) {
      lines.push("", `Error: ${run.error}`);
    }
    return { text: lines.join("\n"), actions };
  }

  if (run.state === "awaiting_confirmation") {
    lines.push("The agent is awaiting human confirmation.");
    actions.push("Continue without risky commands — read and patch with preview only");
    return { text: lines.join("\n"), actions };
  }

  lines.push(
    run.response?.trim()
      ? run.response.trim().slice(0, 500) + (run.response.length > 500 ? "…" : "")
      : `Done · state: ${run.state}.`
  );
  lines.push("");
  lines.push("**Suggested next steps:**");

  if (changes.length > 0) {
    lines.push(`${changes.length} files changed — see Live Changes on the right.`);
  } else if (hasPatch) {
    lines.push("Patches may have been applied — refresh Live Changes (↻).");
  }

  if (verifyFailed) {
    actions.push("Fix verify errors and rerun tests");
  } else {
    actions.push("Run dev server and smoke-test in the browser");
    actions.push("Add unit tests for the new code");
  }
  actions.push("Polish UI and add README");
  actions.push("Prepare deploy and smoke-check");

  return { text: lines.join("\n"), actions };
}
