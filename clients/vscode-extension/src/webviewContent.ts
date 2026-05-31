export function getSidebarHtml(webviewCssNonce: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${webviewCssNonce}';" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Termit</title>
  <style>
    :root {
      color: var(--vscode-foreground);
      background: var(--vscode-sideBar-background);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }
    body { margin: 0; padding: 8px; }
    .tabs { display: flex; gap: 4px; margin-bottom: 8px; }
    .tab {
      flex: 1;
      border: 1px solid var(--vscode-panel-border);
      background: var(--vscode-editor-background);
      color: inherit;
      padding: 6px 4px;
      cursor: pointer;
    }
    .tab.active { border-color: var(--vscode-focusBorder); }
    .panel { display: none; }
    .panel.active { display: block; }
    .status { font-size: 11px; color: var(--vscode-descriptionForeground); margin-bottom: 8px; }
    .log {
      white-space: pre-wrap;
      border: 1px solid var(--vscode-panel-border);
      background: var(--vscode-editor-background);
      min-height: 180px;
      max-height: 320px;
      overflow: auto;
      padding: 8px;
      margin-bottom: 8px;
    }
    textarea, select, input {
      width: 100%;
      box-sizing: border-box;
      margin-bottom: 6px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, var(--vscode-panel-border));
      padding: 6px;
    }
    textarea { min-height: 72px; resize: vertical; }
    .row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
    button {
      border: 1px solid var(--vscode-button-border, transparent);
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      padding: 6px 10px;
      cursor: pointer;
    }
    button.secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    .list {
      border: 1px solid var(--vscode-panel-border);
      max-height: 280px;
      overflow: auto;
      margin-bottom: 8px;
    }
    .list-item {
      padding: 8px;
      border-bottom: 1px solid var(--vscode-panel-border);
      cursor: pointer;
    }
    .list-item:hover { background: var(--vscode-list-hoverBackground); }
    .muted { color: var(--vscode-descriptionForeground); font-size: 11px; }
    label { display: block; margin-bottom: 4px; font-size: 11px; }
  </style>
</head>
<body>
  <div class="status" id="status">Connecting...</div>
  <div class="tabs">
    <button class="tab active" data-tab="chat">Chat</button>
    <button class="tab" data-tab="composer">Composer</button>
    <button class="tab" data-tab="tasks">Tasks</button>
    <button class="tab" data-tab="agents">Agents</button>
  </div>

  <section class="panel active" id="panel-chat">
    <label for="taskType">Task type</label>
    <select id="taskType">
      <option value="general">general</option>
      <option value="coding" selected>coding</option>
      <option value="review">review</option>
      <option value="debug">debug</option>
      <option value="explain">explain</option>
    </select>
    <label><input type="checkbox" id="useRetrieval" /> @codebase retrieval</label>
    <label for="model">Model</label>
    <select id="model" class="model-select"><option value="">Auto (router)</option></select>
    <div class="log" id="chatLog">Ask Termit about your codebase.</div>
    <textarea id="chatInput" placeholder="Message... (Cmd/Ctrl+Enter to send)"></textarea>
    <div class="row">
      <button id="sendChat">Send</button>
      <button class="secondary" id="addContext">@ file</button>
      <button class="secondary" id="clearChat">Clear</button>
    </div>
    <div class="row">
      <button class="secondary" id="createTaskFromChat">Queue task</button>
    </div>
  </section>

  <section class="panel" id="panel-composer">
    <p class="muted">Multi-file edits: attach context files, describe the change, review patches, apply all.</p>
    <div class="list" id="composerFileList"><div class="list-item muted">No context files yet.</div></div>
    <div class="row">
      <button class="secondary" id="composerAddFile">@ add file</button>
      <button class="secondary" id="composerClearFiles">Clear files</button>
    </div>
    <label for="composerModel">Model</label>
    <select id="composerModel" class="model-select"><option value="">Auto (router)</option></select>
    <textarea id="composerInput" rows="6" placeholder="Describe a multi-file change..."></textarea>
    <div class="row">
      <button id="composerRun">Run Composer</button>
    </div>
    <div class="log" id="composerLog">Composer response appears here.</div>
    <div class="list" id="composerPatchList"></div>
    <div class="row">
      <button class="secondary" id="composerApplyAll" disabled>Apply all patches</button>
    </div>
  </section>

  <section class="panel" id="panel-tasks">
    <div class="row">
      <button class="secondary" id="refreshTasks">Refresh</button>
    </div>
    <div class="list" id="taskList"></div>
    <pre class="log" id="taskDetail">Select a task.</pre>
  </section>

  <section class="panel" id="panel-agents">
    <div class="row">
      <button class="secondary" id="refreshAgents">Refresh agents</button>
    </div>
    <div class="list" id="agentList"></div>
    <div class="list" id="agentRunList"></div>
    <label for="agentInput">Agent run input</label>
    <textarea id="agentInput" placeholder="Prompt for selected agent..."></textarea>
    <div class="row">
      <button id="runAgent">Run agent</button>
    </div>
    <pre class="log" id="agentDetail">Select an agent.</pre>
    <pre class="log" id="agentTimeline">Run timeline appears here.</pre>
  </section>

  <script nonce="${webviewCssNonce}">
    const vscode = acquireVsCodeApi();
    let selectedAgentId = null;
    let selectedTaskId = null;
    let composerFiles = [];
    let composerPatches = [];

    function setStatus(text) {
      document.getElementById('status').textContent = text;
    }

    function activeTab(name) {
      document.querySelectorAll('.tab').forEach((el) => {
        el.classList.toggle('active', el.dataset.tab === name);
      });
      document.querySelectorAll('.panel').forEach((el) => {
        el.classList.toggle('active', el.id === 'panel-' + name);
      });
    }

    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => activeTab(tab.dataset.tab));
    });

    const chatLog = document.getElementById('chatLog');
    const chatInput = document.getElementById('chatInput');

    function appendChat(prefix, text) {
      chatLog.textContent += '\\n\\n' + prefix + text;
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    document.getElementById('sendChat').addEventListener('click', () => {
      const message = chatInput.value.trim();
      if (!message) return;
      appendChat('You: ', message);
      appendChat('Termit: ', '');
      vscode.postMessage({
        type: 'chat',
        message,
        taskType: document.getElementById('taskType').value,
        useRetrieval: document.getElementById('useRetrieval').checked,
        model: document.getElementById('model').value,
      });
      chatInput.value = '';
    });

    chatInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        document.getElementById('sendChat').click();
      }
    });

    document.getElementById('addContext').addEventListener('click', () => {
      vscode.postMessage({ type: 'addContext' });
    });

    document.getElementById('clearChat').addEventListener('click', () => {
      chatLog.textContent = 'Ask Termit about your codebase.';
      vscode.postMessage({ type: 'clearSession' });
    });

    document.getElementById('createTaskFromChat').addEventListener('click', () => {
      const message = chatInput.value.trim();
      if (!message) return;
      vscode.postMessage({
        type: 'task',
        input: message,
        taskType: document.getElementById('taskType').value,
      });
    });

    document.getElementById('refreshTasks').addEventListener('click', () => {
      vscode.postMessage({ type: 'refreshTasks' });
    });

    document.getElementById('refreshAgents').addEventListener('click', () => {
      vscode.postMessage({ type: 'refreshAgents' });
    });

    document.getElementById('runAgent').addEventListener('click', () => {
      const input = document.getElementById('agentInput').value.trim();
      if (!selectedAgentId || !input) return;
      vscode.postMessage({ type: 'agentRun', agentId: selectedAgentId, input });
    });

    function renderComposerFiles() {
      const list = document.getElementById('composerFileList');
      list.innerHTML = '';
      if (!composerFiles.length) {
        list.innerHTML = '<div class="list-item muted">No context files yet. Click @ add file.</div>';
        return;
      }
      composerFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = '<strong>@' + file.path + '</strong><div class="muted">' +
          file.content.length + ' chars · click to remove</div>';
        item.addEventListener('click', () => {
          composerFiles.splice(index, 1);
          renderComposerFiles();
        });
        list.appendChild(item);
      });
    }

    function renderComposerPatches() {
      const list = document.getElementById('composerPatchList');
      const applyBtn = document.getElementById('composerApplyAll');
      list.innerHTML = '';
      if (!composerPatches.length) {
        applyBtn.disabled = true;
        return;
      }
      applyBtn.disabled = false;
      composerPatches.forEach((patch, index) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        const kind = patch.content !== undefined ? 'full file' :
          (patch.hunks ? patch.hunks.length + ' hunk(s)' : 'patch');
        item.innerHTML = '<strong>' + patch.path + '</strong><div class="muted">' +
          kind + ' · double-click to preview diff</div>';
        item.addEventListener('dblclick', () => {
          vscode.postMessage({ type: 'composerPreview', index });
        });
        list.appendChild(item);
      });
    }

    document.getElementById('composerAddFile').addEventListener('click', () => {
      vscode.postMessage({ type: 'composerAddFile' });
    });

    document.getElementById('composerClearFiles').addEventListener('click', () => {
      composerFiles = [];
      renderComposerFiles();
    });

    document.getElementById('composerRun').addEventListener('click', () => {
      const instruction = document.getElementById('composerInput').value.trim();
      if (!instruction) return;
      document.getElementById('composerLog').textContent = 'Running Composer...\\n';
      composerPatches = [];
      renderComposerPatches();
      vscode.postMessage({
        type: 'composerRun',
        instruction,
        model: document.getElementById('composerModel').value,
        files: composerFiles,
      });
    });

    document.getElementById('composerApplyAll').addEventListener('click', () => {
      vscode.postMessage({ type: 'composerApplyAll' });
    });

    function renderTasks(tasks) {
      const list = document.getElementById('taskList');
      list.innerHTML = '';
      if (!tasks.length) {
        list.innerHTML = '<div class="list-item muted">No tasks yet.</div>';
        return;
      }
      tasks.forEach((task) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = '<strong>' + task.task_id + '</strong><div class="muted">' +
          task.state + ' · ' + task.task_type + '</div>';
        item.addEventListener('click', () => {
          selectedTaskId = task.task_id;
          vscode.postMessage({ type: 'getTask', taskId: task.task_id });
        });
        list.appendChild(item);
      });
    }

    function renderModels(models) {
      document.querySelectorAll('.model-select').forEach((select) => {
        const current = select.value;
        select.innerHTML = '<option value="">Auto (router)</option>';
        models.forEach((model) => {
          const option = document.createElement('option');
          option.value = model;
          option.textContent = model;
          select.appendChild(option);
        });
        if (current) {
          select.value = current;
        }
      });
    }

    function renderAgents(agents) {
      const list = document.getElementById('agentList');
      list.innerHTML = '';
      if (!agents.length) {
        list.innerHTML = '<div class="list-item muted">No agents configured.</div>';
        return;
      }
      agents.forEach((agent) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = '<strong>' + agent.name + '</strong><div class="muted">' +
          agent.agent_id + ' · ' + agent.task_type + '</div>';
        item.addEventListener('click', () => {
          selectedAgentId = agent.agent_id;
          document.getElementById('agentDetail').textContent =
            agent.name + '\\n' + (agent.description || '') + '\\nTools: ' +
            ((agent.enabled_tools || []).join(', ') || 'none');
          vscode.postMessage({ type: 'listAgentRuns', agentId: agent.agent_id });
        });
        list.appendChild(item);
      });
    }

    function renderAgentRuns(runs) {
      const list = document.getElementById('agentRunList');
      list.innerHTML = '';
      if (!runs.length) {
        list.innerHTML = '<div class="list-item muted">No runs yet.</div>';
        return;
      }
      runs.forEach((run) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = '<strong>' + run.run_id + '</strong><div class="muted">' +
          run.state + ' · ' + run.updated_at + '</div>';
        item.addEventListener('click', () => {
          vscode.postMessage({ type: 'watchAgentRun', runId: run.run_id });
        });
        list.appendChild(item);
      });
    }

    function renderAgentTimeline(run, events) {
      const lines = [
        'run: ' + run.run_id,
        'state: ' + run.state,
        run.model ? 'model: ' + run.model : '',
        run.error ? 'error: ' + run.error : '',
        '',
        '--- timeline ---',
      ].filter(Boolean);
      events.forEach((ev) => {
        lines.push('[' + ev.timestamp + '] ' + ev.state + ' · ' + ev.event_type + ': ' + ev.message);
      });
      document.getElementById('agentTimeline').textContent = lines.join('\\n');
    }

    window.addEventListener('message', (event) => {
      const msg = event.data;
      switch (msg.type) {
        case 'status':
          setStatus(msg.text);
          break;
        case 'token':
          chatLog.textContent += msg.text;
          chatLog.scrollTop = chatLog.scrollHeight;
          break;
        case 'meta':
          chatLog.textContent += '[model: ' + msg.model + ']\\n';
          break;
        case 'done':
          chatLog.textContent += '\\n';
          break;
        case 'error':
          chatLog.textContent += '\\nError: ' + msg.detail + '\\n';
          break;
        case 'contextAppended':
          chatInput.value = (chatInput.value ? chatInput.value + '\\n\\n' : '') + msg.text;
          break;
        case 'tasks':
          renderTasks(msg.tasks || []);
          break;
        case 'taskDetail':
          document.getElementById('taskDetail').textContent = msg.text;
          break;
        case 'agents':
          renderAgents(msg.agents || []);
          break;
        case 'models':
          renderModels(msg.models || []);
          break;
        case 'agentRunCreated':
          document.getElementById('agentDetail').textContent =
            'Run queued: ' + msg.runId + ' (' + msg.state + ')';
          break;
        case 'agentRuns':
          renderAgentRuns(msg.runs || []);
          break;
        case 'agentTimeline':
          renderAgentTimeline(msg.run, msg.events || []);
          break;
        case 'taskCreated':
          appendChat('Task queued: ', msg.taskId);
          break;
        case 'composerFileAdded':
          composerFiles = composerFiles.filter((f) => f.path !== msg.path);
          composerFiles.push({ path: msg.path, content: msg.content });
          renderComposerFiles();
          break;
        case 'composerToken':
          document.getElementById('composerLog').textContent += msg.text;
          break;
        case 'composerDone':
          document.getElementById('composerLog').textContent = msg.prose || '(no text)';
          composerPatches = msg.patches || [];
          renderComposerPatches();
          if (composerPatches.length) {
            document.getElementById('composerLog').textContent +=
              '\\n\\nParsed ' + composerPatches.length + ' patch(es). Double-click a file to preview diff.';
          }
          break;
        case 'composerApplyResult':
          document.getElementById('composerLog').textContent +=
            '\\nApplied ' + msg.applied + ' patch(es).';
          break;
        case 'focusTab':
          activeTab(msg.tab);
          break;
      }
    });

    vscode.postMessage({ type: 'init' });
  </script>
</body>
</html>`;
}
