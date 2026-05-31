window.TermitTerminalDock = (function () {
  let els = {};

  function t(key) {
    return window.tTermit ? window.tTermit(key) : key;
  }

  function cacheElements() {
    els.root = document.getElementById("terminalDock");
    els.toggle = document.getElementById("terminalDockToggle");
    els.output = document.getElementById("terminalDockOutput");
    els.copyBtn = document.getElementById("terminalDockCopy");
    els.hint = document.getElementById("terminalDockHint");
  }

  function apiKeyHeader() {
    const keyInput = document.getElementById("apiKey");
    const key = keyInput ? keyInput.value.trim() : "";
    return key ? `-H "X-API-Key: ${key}" \\\n  ` : "";
  }

  function setCommand(cmd, hint) {
    if (!els.output) return;
    els.output.textContent = cmd;
    if (els.hint && hint) els.hint.textContent = hint;
    if (els.root && els.root.classList.contains("is-collapsed")) {
      els.root.classList.remove("is-collapsed");
    }
  }

  function pushCommand(cmd, hint) {
    setCommand(cmd, hint || t("terminalDock.copiedHint"));
  }

  const QUICK = {
    healthz: () => "curl -s http://127.0.0.1:8765/healthz | python3 -m json.tool",
    agents: () =>
      `curl -s http://127.0.0.1:8765/api/agents \\\n  ${apiKeyHeader()}| python3 -m json.tool`,
    metrics: () =>
      `curl -s http://127.0.0.1:8765/api/ops/agent-runs/metrics \\\n  ${apiKeyHeader()}| python3 -m json.tool`,
    agentRun: () => {
      const agentId = (document.getElementById("agentId") || {}).value || "AGENT_ID";
      const input = (document.getElementById("agentRunInput") || {}).value || "Brief repo overview";
      const escaped = JSON.stringify(input).slice(1, -1);
      return (
        `curl -s -X POST http://127.0.0.1:8765/api/agents/${agentId}/runs \\\n  ` +
        `${apiKeyHeader()}-H "Content-Type: application/json" \\\n  ` +
        `-d '{"input":"${escaped}"}' | python3 -m json.tool`
      );
    },
    stage1: () =>
      "python3 scripts/stage1_enqueue.py \\\n  --base-url http://127.0.0.1:8765 \\\n  --name weekly-stage1 \\\n  --min-samples 1 \\\n  --no-eval-baseline",
  };

  async function copyOutput() {
    if (!els.output) return;
    try {
      await navigator.clipboard.writeText(els.output.textContent || "");
      if (els.copyBtn) {
        const prev = els.copyBtn.textContent;
        els.copyBtn.textContent = t("terminalDock.copied");
        setTimeout(() => {
          els.copyBtn.textContent = prev;
        }, 1500);
      }
    } catch (_err) {
      /* clipboard blocked */
    }
  }

  function bind() {
    if (els.toggle && els.root) {
      els.toggle.addEventListener("click", () => {
        els.root.classList.toggle("is-collapsed");
      });
    }
    if (els.copyBtn) els.copyBtn.addEventListener("click", copyOutput);
    document.querySelectorAll("[data-terminal-cmd]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.getAttribute("data-terminal-cmd");
        if (QUICK[key]) {
          const hintKey = `terminalDock.hint.${key}`;
          pushCommand(QUICK[key](), t(hintKey) || t("terminalDock.copiedHint"));
        }
      });
    });
  }

  function init() {
    cacheElements();
    bind();
    setCommand(t("terminalDock.welcomeCmd"), t("terminalDock.welcomeHint"));
  }

  return { init, pushCommand, setCommand };
})();
