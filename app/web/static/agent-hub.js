window.TermitAgentHub = (function () {
  const STATE_COLORS = {
    queued: "#6366f1",
    running: "#22d3ee",
    completed: "#34d399",
    failed: "#f87171",
    cancelled: "#94a3b8",
  };

  let authHeadersFn = () => ({});
  let queueHistory = [];
  let runStream = null;
  let pollTimer = null;
  let selectedAgentId = null;
  let agentsCache = [];

  const els = {};

  function t(key) {
    return window.tTermit ? window.tTermit(key) : key;
  }

  function hasApiKey() {
    const keyInput = document.getElementById("apiKey");
    return Boolean(keyInput && keyInput.value.trim());
  }

  function cacheElements() {
    els.cards = document.getElementById("agentCards");
    els.health = document.getElementById("agentHubHealth");
    els.timeline = document.getElementById("agentRunTimeline");
    els.liveOutput = document.getElementById("agentLiveOutput");
    els.recentRuns = document.getElementById("agentRecentRuns");
    els.stateChart = document.getElementById("chartRunStates");
    els.queueChart = document.getElementById("chartQueueHistory");
    els.workersChart = document.getElementById("chartWorkers");
    els.legend = document.getElementById("chartRunStatesLegend");
    els.refreshBtn = document.getElementById("refreshAgentHubBtn");
    els.duplicateBtn = document.getElementById("duplicateAgentBtn");
    els.agentIdInput = document.getElementById("agentId");
    els.agentRunIdInput = document.getElementById("agentRunId");
    els.agentRunInput = document.getElementById("agentRunInput");
  }

  function stateLabel(state) {
    const map = {
      queued: t("agentHub.stateQueued"),
      running: t("agentHub.stateRunning"),
      completed: t("agentHub.stateCompleted"),
      failed: t("agentHub.stateFailed"),
      cancelled: t("agentHub.stateCancelled"),
    };
    return map[state] || state;
  }

  function pushTerminalCurl(agentId, input) {
    if (!window.TermitTerminalDock) return;
    const escaped = JSON.stringify(input || "").slice(1, -1);
    const keyInput = document.getElementById("apiKey");
    const key = keyInput ? keyInput.value.trim() : "";
    const auth = key ? `-H "X-API-Key: ${key}" \\\n  ` : "";
    TermitTerminalDock.pushCommand(
      `curl -s -X POST http://127.0.0.1:8765/api/agents/${agentId}/runs \\\n  ${auth}-H "Content-Type: application/json" \\\n  -d '{"input":"${escaped}"}' | python3 -m json.tool`,
      t("terminalDock.hint.agentRun")
    );
  }

  function renderLegend(byState) {
    if (!els.legend) return;
    const order = ["running", "queued", "completed", "failed", "cancelled"];
    els.legend.innerHTML = order
      .filter((k) => (byState[k] || 0) > 0)
      .map(
        (k) =>
          `<span class="legend-item"><i style="background:${STATE_COLORS[k]}"></i>${stateLabel(k)}: ${byState[k]}</span>`
      )
      .join("");
  }

  function updateCharts(metrics) {
    if (!window.TermitCharts) return;
    const byState = metrics.by_state || {};
    const segments = Object.entries(byState)
      .filter(([, v]) => v > 0)
      .map(([key, value]) => ({
        label: stateLabel(key),
        value,
        color: STATE_COLORS[key] || "#818cf8",
      }));

    if (els.stateChart) {
      TermitCharts.drawDonut(els.stateChart, segments, {
        centerLabel: t("agentHub.runsTotal"),
        emptyLabel: t("agentHub.noRunsYet"),
      });
      renderLegend(byState);
    }

    queueHistory.push({
      y: Number(metrics.queue_utilization_percent || 0),
      t: Date.now(),
    });
    if (queueHistory.length > 24) queueHistory.shift();
    if (els.queueChart) {
      TermitCharts.drawLine(els.queueChart, queueHistory, {
        maxY: 100,
        minY: 0,
        color: "#a78bfa",
        emptyLabel: t("agentHub.collectingQueue"),
      });
    }

    if (els.workersChart) {
      const alive = Number(metrics.alive_workers || 0);
      const total = Number(metrics.worker_count || 0);
      TermitCharts.drawBars(
        els.workersChart,
        [
          { label: t("agentHub.workersAlive"), value: alive, color: "#34d399" },
          { label: t("agentHub.workersDown"), value: Math.max(total - alive, 0), color: "#475569" },
        ],
        { height: 120 }
      );
    }

    if (els.health) {
      const status = metrics.health_status || "ok";
      els.health.className = `hub-health-pill ${status}`;
      const reasons = (metrics.health_reasons || []).join("; ");
      els.health.textContent =
        status === "ok"
          ? `● ${t("agentHub.healthOk")}`
          : `● ${status}${reasons ? `: ${reasons}` : ""}`;
    }
  }

  function toolBadges(tools) {
    return (tools || [])
      .slice(0, 4)
      .map((tool) => `<span class="tool-chip">${tool}</span>`)
      .join("");
  }

  function renderAgentCards(agents) {
    agentsCache = agents || [];
    if (!els.cards) return;
    if (!agents.length) {
      els.cards.innerHTML = `<div class="agent-empty">${t("agentHub.noAgents")}</div>`;
      return;
    }

    els.cards.innerHTML = agents
      .map((agent) => {
        const active = selectedAgentId === agent.agent_id ? " is-selected" : "";
        const model = agent.model || t("agentHub.modelAuto");
        const online = agent.allow_online
          ? `<span class="badge badge-online">${t("agentHub.online")}</span>`
          : "";
        return `
          <article class="agent-card${active}" data-agent-id="${agent.agent_id}">
            <div class="agent-card-top">
              <div class="agent-avatar">${(agent.name || "?").slice(0, 1).toUpperCase()}</div>
              <div>
                <h5>${agent.name}</h5>
                <p class="agent-id">${agent.agent_id}</p>
              </div>
              ${online}
            </div>
            <p class="agent-model">${model}</p>
            <div class="agent-tools">${toolBadges(agent.enabled_tools)}</div>
            <div class="agent-card-actions">
              <button type="button" class="btn-ghost agent-select-btn" data-agent-id="${agent.agent_id}">${t("agentHub.select")}</button>
              <button type="button" class="btn-primary agent-quick-run-btn" data-agent-id="${agent.agent_id}">${t("agentHub.quickRun")}</button>
            </div>
          </article>`;
      })
      .join("");
  }

  function renderRecentRuns(runs) {
    if (!els.recentRuns) return;
    if (!runs || !runs.length) {
      els.recentRuns.innerHTML = `<p class="timeline-empty">${t("agentHub.noRecentRuns")}</p>`;
      return;
    }
    els.recentRuns.innerHTML = runs
      .slice(0, 8)
      .map(
        (run) =>
          `<button type="button" class="recent-run-row" data-run-id="${run.run_id}" data-tip="agentRunId">
            <span class="state-pill state-${run.state}">${stateLabel(run.state)}</span>
            <span class="recent-run-id">${run.run_id}</span>
            <span class="recent-run-input">${(run.input || "").slice(0, 48)}</span>
          </button>`
      )
      .join("");
  }

  async function loadRecentRuns(agentId) {
    if (!agentId || !els.recentRuns) return;
    els.recentRuns.innerHTML = `<p class="timeline-empty">…</p>`;
    try {
      const resp = await fetch(
        `/api/agents/${encodeURIComponent(agentId)}/runs?limit=8`,
        { headers: authHeadersFn() }
      );
      if (!resp.ok) {
        renderRecentRuns([]);
        return;
      }
      const data = await resp.json();
      renderRecentRuns(data.runs || []);
    } catch (_err) {
      renderRecentRuns([]);
    }
  }

  function selectAgent(agentId) {
    selectedAgentId = agentId;
    if (els.agentIdInput) els.agentIdInput.value = agentId;
    document.querySelectorAll(".agent-card").forEach((card) => {
      card.classList.toggle("is-selected", card.dataset.agentId === agentId);
    });
    loadRecentRuns(agentId);
  }

  async function duplicateSelectedAgent() {
    if (!selectedAgentId) return;
    const source = agentsCache.find((a) => a.agent_id === selectedAgentId);
    if (!source) return;
    const name = `${source.name} (copy)`;
    try {
      const resp = await fetch("/api/agents", {
        method: "POST",
        headers: authHeadersFn({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name,
          description: source.description || "Duplicated from web panel",
          system_prompt: source.system_prompt,
          task_type: source.task_type || "general",
          model: source.model || null,
          allow_online: source.allow_online,
          enabled_tools: source.enabled_tools || [],
          use_memory: source.use_memory,
          use_retrieval: source.use_retrieval,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setLiveOutput(`<pre>${JSON.stringify(data, null, 2)}</pre>`, "error");
        return;
      }
      await refresh();
      selectAgent(data.agent_id);
      if (els.newAgentName) els.newAgentName.value = data.name;
    } catch (err) {
      setLiveOutput(`<pre>${String(err)}</pre>`, "error");
    }
  }

  function renderTimeline(events) {
    if (!els.timeline) return;
    if (!events || !events.length) {
      els.timeline.innerHTML = `<p class="timeline-empty">${t("agentHub.timelineEmpty")}</p>`;
      return;
    }
    els.timeline.innerHTML = events
      .slice(-12)
      .map((ev) => {
        const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "";
        return `
          <div class="timeline-item state-${ev.state}">
            <div class="timeline-dot"></div>
            <div class="timeline-body">
              <strong>${ev.event_type}</strong>
              <span class="timeline-state">${stateLabel(ev.state)}</span>
              <p>${ev.message || ""}</p>
              <time>${ts}</time>
            </div>
          </div>`;
      })
      .join("");
    els.timeline.scrollTop = els.timeline.scrollHeight;
  }

  function setLiveOutput(html, kind) {
    if (!els.liveOutput) return;
    els.liveOutput.className = `live-output${kind ? ` ${kind}` : ""}`;
    els.liveOutput.innerHTML = html;
  }

  function renderRunStatus(data) {
    setLiveOutput(
      `<div class="live-run-card">
        <div class="live-run-header">
          <span class="state-pill state-${data.state}">${stateLabel(data.state)}</span>
          <span>${data.agent_name || ""}</span>
        </div>
        <pre class="live-run-pre">${(data.response || data.error || data.input || "").slice(0, 4000)}</pre>
      </div>`,
      data.state === "failed" ? "error" : "ok"
    );
    if (els.agentRunIdInput) els.agentRunIdInput.value = data.run_id;
  }

  function stopRunStream() {
    if (runStream) {
      runStream.close();
      runStream = null;
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function isTerminalState(state) {
    return state === "completed" || state === "failed" || state === "cancelled";
  }

  function startRunPolling(runId) {
    stopRunStream();
    if (!runId) return;
    setLiveOutput(
      `<p class="live-status">${t("agentHub.pollingMode")}: <code>${runId}</code></p>`,
      "streaming"
    );

    const poll = async () => {
      try {
        const resp = await fetch(`/api/agents/runs/${encodeURIComponent(runId)}`, {
          headers: authHeadersFn(),
        });
        if (!resp.ok) return;
        const data = await resp.json();
        renderRunStatus(data);
        if (isTerminalState(data.state)) {
          stopRunStream();
          refresh();
          if (selectedAgentId) loadRecentRuns(selectedAgentId);
        }
      } catch (_err) {
        /* ignore transient errors */
      }
    };

    poll();
    pollTimer = setInterval(poll, 1500);
  }

  function startRunStream(runId) {
    stopRunStream();
    if (!runId) return;

    if (hasApiKey()) {
      startRunPolling(runId);
      return;
    }

    setLiveOutput(`<p class="live-status">${t("agentHub.streamingRun")} <code>${runId}</code></p>`, "streaming");

    runStream = new EventSource(
      `/api/agents/runs/${encodeURIComponent(runId)}/stream?poll_ms=500&timeout_seconds=600`
    );
    runStream.addEventListener("status", (event) => {
      try {
        renderRunStatus(JSON.parse(event.data));
      } catch (_e) {
        /* ignore */
      }
    });
    runStream.addEventListener("done", () => {
      stopRunStream();
      refresh();
      if (selectedAgentId) loadRecentRuns(selectedAgentId);
    });
    runStream.addEventListener("error", () => {
      stopRunStream();
      startRunPolling(runId);
    });
  }

  async function loadRunEvents(runId) {
    if (!runId) return;
    if (els.agentRunIdInput) els.agentRunIdInput.value = runId;
    startRunStream(runId);
    try {
      const resp = await fetch(`/api/agents/runs/${encodeURIComponent(runId)}/events`, {
        headers: authHeadersFn(),
      });
      if (resp.ok) renderTimeline(await resp.json());
    } catch (_err) {
      /* ignore */
    }
  }

  async function fetchMetrics() {
    const resp = await fetch("/api/ops/agent-runs/metrics", { headers: authHeadersFn() });
    if (!resp.ok) throw new Error("metrics");
    return resp.json();
  }

  async function fetchAgents() {
    const resp = await fetch("/api/agents", { headers: authHeadersFn() });
    if (!resp.ok) throw new Error("agents");
    return resp.json();
  }

  async function refresh() {
    try {
      const [metrics, agents] = await Promise.all([fetchMetrics(), fetchAgents()]);
      updateCharts(metrics);
      renderAgentCards(agents);
      if (!selectedAgentId && agents.length) selectAgent(agents[0].agent_id);
      else if (selectedAgentId) {
        const stillExists = agents.some((agent) => agent.agent_id === selectedAgentId);
        if (stillExists) loadRecentRuns(selectedAgentId);
        else if (agents.length) selectAgent(agents[0].agent_id);
        else selectedAgentId = null;
      }
    } catch (_err) {
      if (els.health) {
        els.health.className = "hub-health-pill degraded";
        els.health.textContent = `● ${t("agentHub.loadFailed")}`;
      }
    }
  }

  async function quickRun(agentId) {
    selectAgent(agentId);
    const input = (els.agentRunInput && els.agentRunInput.value.trim()) || t("agentHub.defaultPrompt");
    if (els.agentRunInput && !els.agentRunInput.value.trim()) {
      els.agentRunInput.value = input;
    }
    setLiveOutput(`<p class="live-status">${t("agentHub.queueing")}…</p>`, "streaming");
    pushTerminalCurl(agentId, input);
    try {
      const resp = await fetch(`/api/agents/${encodeURIComponent(agentId)}/runs`, {
        method: "POST",
        headers: authHeadersFn({ "Content-Type": "application/json" }),
        body: JSON.stringify({ input }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setLiveOutput(`<pre>${JSON.stringify(data, null, 2)}</pre>`, "error");
        return;
      }
      if (els.agentRunIdInput) els.agentRunIdInput.value = data.run_id;
      startRunStream(data.run_id);
      const evResp = await fetch(`/api/agents/runs/${encodeURIComponent(data.run_id)}/events`, {
        headers: authHeadersFn(),
      });
      if (evResp.ok) renderTimeline(await evResp.json());
      loadRecentRuns(agentId);
    } catch (err) {
      setLiveOutput(`<pre>${String(err)}</pre>`, "error");
    }
  }

  function bindEvents() {
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", refresh);
    if (els.duplicateBtn) els.duplicateBtn.addEventListener("click", duplicateSelectedAgent);
    if (els.cards) {
      els.cards.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const agentId = target.dataset.agentId;
        if (!agentId) return;
        if (target.classList.contains("agent-quick-run-btn")) quickRun(agentId);
        if (target.classList.contains("agent-select-btn")) selectAgent(agentId);
      });
    }
    if (els.recentRuns) {
      els.recentRuns.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-run-id]");
        if (!btn) return;
        loadRunEvents(btn.getAttribute("data-run-id"));
      });
    }
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(refresh, 200);
    });
  }

  function init(options = {}) {
    if (options.authHeaders) authHeadersFn = options.authHeaders;
    cacheElements();
    bindEvents();
    refresh();
    setInterval(refresh, 15000);
  }

  return {
    init,
    refresh,
    selectAgent,
    renderTimeline,
    startRunStream,
    stopRunStream,
    updateCharts,
    renderAgentCards,
    loadRecentRuns,
    duplicateSelectedAgent,
  };
})();
