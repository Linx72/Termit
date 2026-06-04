window.TermitWebAppsHub = (function () {
  let authHeadersFn = () => ({});

  const SEED_AGENTS = [
    { template_id: "web-app-vite", labelKey: "seedWebApp" },
    { template_id: "online-project-manager", labelKey: "seedOnlineProject" },
    { template_id: "research-fast", labelKey: "seedResearchFast" },
  ];

  const els = {};

  function t(key) {
    return window.tTermit ? window.tTermit(key) : key;
  }

  function packKey(key) {
    const hub = window.TERMIT_I18N?.[window.getTermitLang?.() || "ru"]?.webAppsHub;
    return (hub && hub[key]) || key;
  }

  function cacheElements() {
    els.list = document.getElementById("webAppsAssignmentList");
    els.title = document.getElementById("webAppsAssignmentTitle");
    els.brief = document.getElementById("webAppsAssignmentBrief");
    els.criteria = document.getElementById("webAppsSuccessCriteria");
    els.urls = document.getElementById("webAppsTargetUrls");
    els.createBtn = document.getElementById("webAppsCreateAssignmentBtn");
    els.refreshBtn = document.getElementById("webAppsRefreshAssignmentsBtn");
    els.scriptsPanel = document.getElementById("webAppsScriptsPanel");
    els.workspaceInput = document.getElementById("webAppsWorkspace");
    els.loadScriptsBtn = document.getElementById("webAppsLoadScriptsBtn");
    els.seedRow = document.getElementById("webAppsSeedAgents");
    els.status = document.getElementById("webAppsStatus");
  }

  function setStatus(text) {
    if (els.status) {
      els.status.textContent = text;
    }
  }

  async function apiFetch(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: authHeadersFn(options.headers || {}),
    });
    const body = await res.text();
    let data = null;
    try {
      data = body ? JSON.parse(body) : null;
    } catch {
      data = body;
    }
    if (!res.ok) {
      const detail =
        typeof data === "object" && data && data.detail
          ? JSON.stringify(data.detail)
          : String(data || res.statusText);
      throw new Error(`${res.status}: ${detail}`);
    }
    return data;
  }

  function renderAssignments(items) {
    if (!els.list) return;
    if (!items || items.length === 0) {
      els.list.innerHTML = `<div class="meta">${packKey("noAssignments")}</div>`;
      return;
    }
    els.list.innerHTML = items
      .map(
        (item) =>
          `<div class="hub-card compact">
            <strong>${item.assignment_id}</strong>
            <div class="meta">${item.assignment_id}</div>
            <div class="meta">${item.root_path}</div>
            <button type="button" class="secondary compact" data-root="${item.root_path}" data-action="dev-cmd">
              ${packKey("devPreviewCmd")}
            </button>
          </div>`
      )
      .join("");
    els.list.querySelectorAll('[data-action="dev-cmd"]').forEach((btn) => {
      btn.addEventListener("click", () => {
        const root = btn.getAttribute("data-root") || "";
        const cmd = root ? `cd "${root}" && npm run dev` : "npm run dev";
        if (window.TermitTerminalDock) {
          TermitTerminalDock.pushCommand(cmd, packKey("devPreviewHint"));
        }
      });
    });
  }

  async function refreshAssignments() {
    try {
      const items = await apiFetch("/api/assignments?limit=30");
      renderAssignments(items);
      setStatus(packKey("assignmentsLoaded"));
    } catch (error) {
      setStatus(String(error));
    }
  }

  async function createAssignment() {
    const title = (els.title?.value || "").trim();
    const brief = (els.brief?.value || "").trim();
    const criteriaRaw = (els.criteria?.value || "").trim();
    const urlsRaw = (els.urls?.value || "").trim();
    const success_criteria = criteriaRaw
      ? criteriaRaw.split("\n").map((line) => line.trim()).filter(Boolean)
      : [];
    const target_urls = urlsRaw
      ? urlsRaw.split("\n").map((line) => line.trim()).filter(Boolean)
      : [];
    if (!title || brief.length < 10) {
      setStatus(packKey("assignmentValidation"));
      return;
    }
    try {
      const created = await apiFetch("/api/assignments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, brief, success_criteria, target_urls }),
      });
      setStatus(`${packKey("assignmentCreated")}: ${created.assignment_id}`);
      if (els.title) els.title.value = "";
      if (els.brief) els.brief.value = "";
      await refreshAssignments();
    } catch (error) {
      setStatus(String(error));
    }
  }

  async function loadWorkspaceScripts() {
    const workspace = (els.workspaceInput?.value || "").trim();
    const query = workspace ? `?workspace=${encodeURIComponent(workspace)}` : "";
    try {
      const data = await apiFetch(`/api/tools/workspace-scripts${query}`);
      if (els.scriptsPanel) {
        els.scriptsPanel.textContent = JSON.stringify(data, null, 2);
      }
      setStatus(packKey("scriptsLoaded"));
    } catch (error) {
      if (els.scriptsPanel) {
        els.scriptsPanel.textContent = String(error);
      }
      setStatus(String(error));
    }
  }

  async function seedAgent(templateId) {
    try {
      const data = await apiFetch(
        `/api/projects/agent-templates/${encodeURIComponent(templateId)}/ensure-agent`,
        { method: "POST" }
      );
      setStatus(`${packKey("agentSeeded")}: ${data.agent_id || templateId}`);
      if (window.TermitAgentHub && typeof TermitAgentHub.refresh === "function") {
        await TermitAgentHub.refresh();
      }
    } catch (error) {
      setStatus(String(error));
    }
  }

  function renderSeedButtons() {
    if (!els.seedRow) return;
    els.seedRow.innerHTML = SEED_AGENTS.map(
      (item) =>
        `<button type="button" class="secondary" data-template="${item.template_id}">${packKey(item.labelKey)}</button>`
    ).join("");
    els.seedRow.querySelectorAll("button[data-template]").forEach((btn) => {
      btn.addEventListener("click", () => {
        void seedAgent(btn.getAttribute("data-template"));
      });
    });
  }

  function bindEvents() {
    els.createBtn?.addEventListener("click", () => void createAssignment());
    els.refreshBtn?.addEventListener("click", () => void refreshAssignments());
    els.loadScriptsBtn?.addEventListener("click", () => void loadWorkspaceScripts());
  }

  function init(options) {
    authHeadersFn = options?.authHeaders || authHeadersFn;
    cacheElements();
    renderSeedButtons();
    bindEvents();
    void refreshAssignments();
    void loadWorkspaceScripts();
  }

  return { init, refresh: refreshAssignments };
})();
