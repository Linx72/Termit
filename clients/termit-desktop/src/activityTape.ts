import type { AgentRunEvent, AgentRunRecord } from "@termit/client";

export type GitChangeRef = { status: string; path: string };

export type CompletionBundle = {
  text: string;
  /** Быстрые команды — кнопки под итогом, как follow-up в Cursor. */
  actions: string[];
};

type LoopTracePayload = {
  step?: number;
  action?: string;
  tool?: string;
  observation?: string;
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

  const visibleEvents = events.filter((ev) => {
    const eventType = ev.event_type.toLowerCase();
    if (eventType === "tool_loop_trace") {
      return true;
    }
    if (eventType.startsWith("tool_loop_")) {
      return false;
    }
    return true;
  });

  const source = visibleEvents.length > 0 ? visibleEvents : events;
  const lines = source.map((ev, index) => formatTapeLine(locale, ev, index));

  return `${header}\n\n${lines.join("\n")}`;
}

function formatTapeLine(locale: "ru" | "en", ev: AgentRunEvent, index: number): string {
  const eventType = ev.event_type.toLowerCase();
  const marker = tapeMarker(ev.event_type);
  const message = ev.message?.trim() || ev.event_type;

  if (eventType === "tool_loop_trace") {
    const trace = parseLoopTrace(message);
    if (trace) {
      return `${index + 1}. ${marker} ${formatLoopTrace(locale, trace)}`;
    }
  }

  if (locale === "ru") {
    if (eventType === "run_queued") {
      return `${index + 1}. ⏳ Run поставлен в очередь`;
    }
    if (eventType === "run_attempt_started") {
      return `${index + 1}. ▶️ Началась попытка выполнения`;
    }
    if (eventType === "run_retry_scheduled") {
      return `${index + 1}. 🔁 Запланирован повтор: ${message}`;
    }
    if (eventType === "run_completed") {
      return `${index + 1}. ✅ Run завершён успешно`;
    }
    if (eventType === "run.failed" || eventType === "run_dead_lettered") {
      return `${index + 1}. ✗ Run завершился ошибкой: ${message}`;
    }
    if (eventType === "confirmation_required") {
      return `${index + 1}. 🛑 Нужна проверка человека: ${message}`;
    }
    if (eventType === "skills_mounted") {
      return `${index + 1}. 🧩 Подключены skills: ${message}`;
    }
  } else {
    if (eventType === "run_queued") {
      return `${index + 1}. ⏳ Run queued`;
    }
    if (eventType === "run_attempt_started") {
      return `${index + 1}. ▶️ Run attempt started`;
    }
    if (eventType === "run_retry_scheduled") {
      return `${index + 1}. 🔁 Retry scheduled: ${message}`;
    }
    if (eventType === "run_completed") {
      return `${index + 1}. ✅ Run completed`;
    }
    if (eventType === "run.failed" || eventType === "run_dead_lettered") {
      return `${index + 1}. ✗ Run failed: ${message}`;
    }
    if (eventType === "confirmation_required") {
      return `${index + 1}. 🛑 Human confirmation required: ${message}`;
    }
    if (eventType === "skills_mounted") {
      return `${index + 1}. 🧩 Skills mounted: ${message}`;
    }
  }

  return `${index + 1}. ${marker} ${ev.event_type} — ${message}`;
}

function parseLoopTrace(raw: string): LoopTracePayload | null {
  try {
    const data = JSON.parse(raw) as LoopTracePayload;
    if (!data || typeof data !== "object") {
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

function formatLoopTrace(locale: "ru" | "en", trace: LoopTracePayload): string {
  const step = typeof trace.step === "number" ? trace.step : undefined;
  const action = String(trace.action ?? "").trim().toLowerCase();
  const tool = String(trace.tool ?? "").trim();
  const observation = String(trace.observation ?? "").trim();
  const prefix =
    step !== undefined
      ? locale === "ru"
        ? `Шаг ${step}`
        : `Step ${step}`
      : locale === "ru"
        ? "Шаг"
        : "Step";

  if (locale === "ru") {
    if (action === "tool") {
      return tool
        ? `${prefix}: действие — вызов инструмента ${tool}${observation ? ` · ${shortObservation(observation)}` : ""}`
        : `${prefix}: действие — вызов инструмента`;
    }
    if (action === "final") {
      return `${prefix}: формирую финальный ответ`;
    }
    if (action === "verify_pass") {
      return `${prefix}: проверка пройдена`;
    }
    if (action === "verify_failed") {
      return `${prefix}: проверка не пройдена${observation ? ` · ${shortObservation(observation)}` : ""}`;
    }
    if (action === "parse_error") {
      return `${prefix}: размышление — исправляю формат JSON${observation ? ` · ${shortObservation(observation)}` : ""}`;
    }
    if (action === "repeat_blocked") {
      return `${prefix}: размышление — избегаю повторного шага`;
    }
    if (action === "final_blocked_missing_apply_patch") {
      return `${prefix}: размышление — блокирую финал, сначала нужен apply_patch`;
    }
    return `${prefix}: ${action || "промежуточный шаг"}${observation ? ` · ${shortObservation(observation)}` : ""}`;
  }

  if (action === "tool") {
    return tool
      ? `${prefix}: action — calling ${tool}${observation ? ` · ${shortObservation(observation)}` : ""}`
      : `${prefix}: action — tool call`;
  }
  if (action === "final") {
    return `${prefix}: composing final answer`;
  }
  if (action === "verify_pass") {
    return `${prefix}: verification passed`;
  }
  if (action === "verify_failed") {
    return `${prefix}: verification failed${observation ? ` · ${shortObservation(observation)}` : ""}`;
  }
  if (action === "parse_error") {
    return `${prefix}: reasoning — fixing JSON format${observation ? ` · ${shortObservation(observation)}` : ""}`;
  }
  if (action === "repeat_blocked") {
    return `${prefix}: reasoning — avoiding repeated step`;
  }
  if (action === "final_blocked_missing_apply_patch") {
    return `${prefix}: reasoning — final blocked until apply_patch`;
  }
  return `${prefix}: ${action || "intermediate step"}${observation ? ` · ${shortObservation(observation)}` : ""}`;
}

function shortObservation(value: string): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > 140 ? `${compact.slice(0, 140)}…` : compact;
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
