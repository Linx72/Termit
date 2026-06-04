window.TERMIT_I18N = {
  en: {
    pageTitle: "Termit - Open Source Coding Agent",
    subtitle: "Open-source coding orchestrator MVP · control panel",
    langLabel: "Interface language",
    helpTitle: "Help & logic overview",
    helpNavLabel: "Sections:",
    helpQuickstartTitle: "Quick start (2 terminals)",
    helpTroubleTitle: "If there is no response",
    apiKeyLabel: "API key (optional, saved locally)",
    apiKeyPlaceholder: "Used when TERMIT_AUTH_ENABLED=true",
    sectionDashboard: "Operator dashboard",
    sectionChat: "Chat",
    sectionWebApps: "Web apps & assignments",
    sectionTask: "Task console",
    sectionOrchestration: "Multi-agent orchestration",
    sectionAgents: "Agent profiles",
    sectionTeam: "Team workspace",
    sectionFinetune: "Fine-tune pipeline",
    sectionEval: "Eval harness",
    sectionStage1: "Finetune Stage1 Queue",
    sectionOps: "Beta ops",
    sectionRetrieval: "Code retrieval",
    sectionResponse: "Response",
    refreshDashboard: "Refresh dashboard",
    checkHealthz: "Check /healthz",
    taskType: "Task type",
    model: "Model (optional override)",
    modelAuto: "auto (router decides)",
    sessionId: "Session ID (optional)",
    sessionPlaceholder: "auto-create when memory is enabled",
    useMemory: "Use session memory",
    useRetrieval: "Use codebase retrieval",
    retrievalPrefix: "Retrieval path prefix (optional)",
    repoProfile: "Repo profile (optional)",
    routingPolicy: "Routing policy",
    prompt: "Prompt",
    promptPlaceholder: "Describe coding task...",
    run: "Run",
    runStream: "Run stream",
    clearSession: "Clear session memory",
    exportFormat: "Export format",
    exportSession: "Export session",
    downloadExport: "Download export",
    checkProviders: "Check providers",
    checkUsage: "Check usage",
    feedback: "Beta feedback",
    feedbackPlaceholder: "What should we improve?",
    sendFeedback: "Send feedback",
    taskInput: "Task input",
    taskInputPlaceholder: "Describe end-to-end task...",
    taskMode: "Task mode",
    createTask: "Create task",
    taskId: "Task ID",
    taskIdPlaceholder: "filled after task creation",
    refreshTask: "Refresh task",
    listTasks: "List recent tasks",
    loadTaskEvents: "Load task events",
    cancelTask: "Cancel task",
    orchestrationInput: "Orchestration objective",
    orchestrationPlaceholder: "Plan, execute, verify, and report...",
    runOrchestration: "Run orchestration",
    newAgentName: "New agent name",
    newAgentPrompt: "New agent system prompt",
    newAgentModel: "New agent model (optional)",
    newAgentTools: "Enabled tools (comma separated)",
    allowOnline: "Allow online automation for this agent",
    createAgent: "Create agent",
    listAgents: "List agents",
    agentId: "Agent ID",
    agentRunInput: "Agent run input",
    agentOnlineUrl: "Agent online URL (optional)",
    agentOnlineObjective: "Agent online objective (optional)",
    runAgent: "Run agent",
    queueAgentRun: "Queue run (background)",
    agentRunId: "Agent run ID",
    checkAgentRun: "Check queued run",
    loadAgentRunEvents: "Load run events",
    cancelAgentRun: "Cancel queued run",
    agentToolPath: "Agent tool path",
    agentReadFile: "Agent read file tool",
    teamUsage: "Team usage",
    listRoutingProfiles: "List routing profiles",
    exportDashboard: "Export KPI dashboard JSON",
    datasetName: "Dataset name",
    exportDataset: "Export dataset",
    jobId: "Job ID",
    createJob: "Create job from last export",
    runJob: "Run / validate job",
    listJobs: "List jobs",
    trainingRecipe: "Training recipe",
    adapterModel: "Adapter model",
    registerAdapter: "Register adapter",
    listAdapters: "List adapters",
    scenarioId: "Scenario ID",
    listScenarios: "List scenarios",
    runScenario: "Run scenario",
    suiteCategory: "Suite category filter (optional)",
    runSuite: "Run full suite (24)",
    listEvalReports: "List eval reports",
    captureMetrics: "Capture KPI snapshot",
    pipelineName: "Pipeline name",
    baseModel: "Base model",
    runBaseline: "Run baseline eval before pipeline",
    pipelineRunId: "Pipeline run ID",
    enqueueStage1: "Enqueue stage1 pipeline",
    listStage1Runs: "List stage1 runs",
    listFailedRuns: "List failed runs",
    checkStage1Run: "Check stage1 run",
    cancelStage1Run: "Cancel stage1 run",
    retryFailedRun: "Retry failed run",
    trainStage1Run: "Train now",
    opsReadiness: "Check readiness",
    opsDrill: "Run incident drill",
    opsQuota: "Quota summary (admin)",
    searchQuery: "Search query",
    reindex: "Reindex workspace",
    searchCodebase: "Search codebase",
    dashQueue: "Queue utilization",
    dashWorkers: "Workers alive",
    dashDeadLetter: "Dead-letter rate",
    dashRuns: "Run states",
    dashWaiting: "Waiting for metrics...",
    dashLoadFailed: "Failed to load agent metrics.",
    dashRefreshFailed: "Dashboard refresh failed.",
    navSidebarDashboard: "Dashboard",
    navSidebarChat: "Chat",
    navSidebarWebApps: "Web & assignments",
    navSidebarTasks: "Tasks",
    navSidebarAgents: "Agents",
    navSidebarFinetune: "Finetune",
    navSidebarStage1: "Stage1",
    navSidebarEval: "Eval",
    navSidebarOps: "Ops",
    webAppsHub: {
      intro: "Create assignment workspaces, inspect npm scripts, seed web/online agents.",
      assignmentTitle: "Assignment title",
      assignmentBrief: "Brief (min 10 chars)",
      successCriteria: "Success criteria (one per line)",
      targetUrls: "Target URLs (one per line)",
      createAssignment: "Create assignment",
      refreshAssignments: "Refresh list",
      workspace: "Workspace path (optional)",
      loadScripts: "Load workspace scripts",
      seedTitle: "Quick agent seed",
      seedWebApp: "Web App (Vite)",
      seedOnlineProject: "Online Project Manager",
      seedResearchFast: "Research Fast",
      noAssignments: "No assignments yet.",
      devPreviewCmd: "Dev preview cmd",
      devPreviewHint: "Run in project root (Vite :5173)",
      assignmentsLoaded: "Assignments loaded",
      assignmentCreated: "Assignment created",
      assignmentValidation: "Title and brief (≥10 chars) required",
      scriptsLoaded: "Workspace scripts loaded",
      agentSeeded: "Agent ready",
    },
    agentHub: {
      title: "Agent Hub",
      subtitle: "Profile cards, live queue metrics, and run timeline — everything for working with autonomous agents.",
      chartStates: "Run states",
      chartQueue: "Queue load (live)",
      chartWorkers: "Workers",
      yourAgents: "Your agents",
      refresh: "Refresh",
      compose: "Launch agent",
      liveFeed: "Live feed",
      advanced: "Advanced settings & create agent",
      promptPlaceholder: "Describe the task for the agent...",
      timelineEmpty: "Start a run — event timeline will appear here.",
      liveEmpty: "Agent response and run status in real time.",
      select: "Select",
      quickRun: "Quick run",
      online: "online",
      modelAuto: "auto",
      noAgents: "No agents yet — create one in advanced settings below.",
      healthOk: "System healthy",
      loadFailed: "Failed to load hub",
      streamingRun: "Streaming run",
      queueing: "Queueing",
      defaultPrompt: "Give a brief overview of this repository.",
      runsTotal: "runs",
      noRunsYet: "No runs yet",
      collectingQueue: "Collecting queue data...",
      workersAlive: "alive",
      workersDown: "down",
      stateQueued: "queued",
      stateRunning: "running",
      stateCompleted: "completed",
      stateFailed: "failed",
      stateCancelled: "cancelled",
    },
    helpHtml: {
      dashboard: `<summary>Queue, workers, dead-letter trend</summary>
        <ul>
          <li><strong>Logic:</strong> cards poll agent queue metrics every 15s and compare against alert thresholds.</li>
          <li><strong>Queue utilization</strong> — depth vs capacity; high values mean backlog risk.</li>
          <li><strong>Workers alive</strong> — background threads processing agent runs.</li>
          <li><strong>Dead-letter rate</strong> — failed runs among terminal states; sparkline is session-local trend.</li>
          <li><strong>/healthz</strong> — dependency probe for load balancers (DB paths, providers, workers, scheduler).</li>
        </ul>
        <span class="cmd-block">curl -s http://127.0.0.1:8765/healthz
curl -s http://127.0.0.1:8765/api/metrics/thresholds
curl -s http://127.0.0.1:8765/api/ops/agent-runs/metrics</span>`,
      chat: `<summary>Chat — buttons and routing logic</summary>
        <ul>
          <li><strong>Run</strong> — single LLM request; router picks model by task_type if Model is empty.</li>
          <li><strong>Run stream</strong> — SSE token stream for long answers.</li>
          <li><strong>Session memory</strong> — multi-turn context stored in SQLite/memory backend.</li>
          <li><strong>Codebase retrieval</strong> — injects relevant workspace chunks (RAG) into prompt.</li>
          <li><strong>Repo profile + routing policy</strong> — benchmark-aware model selection per path prefix.</li>
        </ul>`,
      task: `<summary>Tasks — plan → execute → verify → report</summary>
        <ul>
          <li><strong>Create task</strong> — auto mode runs full lifecycle; guided stops between phases.</li>
          <li><strong>Events</strong> — structured log with retries and failure_class for debugging.</li>
        </ul>`,
      agents: `<summary>Agents — profiles, queue, online mode</summary>
        <ul>
          <li><strong>Profile</strong> — system prompt, model, allowed tools, online policy.</li>
          <li><strong>Run</strong> — synchronous execution; <strong>Queue run</strong> — background worker with retry/backoff.</li>
          <li><strong>Run events</strong> — timeline (queued, attempt, retry, dead-letter).</li>
          <li><strong>Online</strong> — requires allow_online + web_automation tool + URL in payload.</li>
        </ul>`,
      orchestration: `<summary>Orchestration — planner → executor → verifier</summary>
        <ul>
          <li>Single request runs multi-phase chain and task runner; output includes plan and report.</li>
          <li>May take several minutes — watch Response block.</li>
        </ul>`,
      finetune: `<summary>Finetune MVP — dataset and adapters</summary>
        <ul>
          <li><strong>Export</strong> — JSONL from feedback + tasks + agent_runs (min_samples).</li>
          <li><strong>Job validate</strong> — dataset check; use <strong>Train now</strong> or TERMIT_FINETUNE_AUTO_TRAIN for built-in Ollama training.</li>
          <li><strong>Register adapter</strong> — bind finetuned model to repo profile.</li>
        </ul>`,
      eval: `<summary>Eval — 24 quality scenarios</summary>
        <ul>
          <li>Categories: coding (A*), local ops (L*), web (W*).</li>
          <li>Suite writes pass_rate to eval_reports.jsonl.</li>
        </ul>`,
      retrieval: `<summary>RAG — workspace index and search</summary>
        <ul>
          <li><strong>Reindex</strong> — after large code changes.</li>
          <li><strong>Search</strong> — use with Use codebase retrieval in chat.</li>
        </ul>`,
      team: `<summary>Teams and routing profiles</summary>
        <ul>
          <li><strong>Team usage</strong> — TERMIT_TEAM_QUOTAS consumption.</li>
          <li><strong>Routing profiles</strong> — repo_model_profiles.json.</li>
        </ul>`,
      stage1: `<summary>Stage1 — weekly dataset + eval pipeline</summary>
        <ul>
          <li>Pipeline: export dataset → optional baseline eval → validate job → built-in train (Train now / auto-train) or Modelfile recipe.</li>
          <li>Built-in trainer: POST …/stage1-runs/{run_id}/train or TERMIT_FINETUNE_AUTO_TRAIN=true (Ollama create).</li>
          <li>Enable built-in scheduler: TERMIT_STAGE1_SCHEDULE_ENABLED=true</li>
        </ul>`,
      ops: `<summary>Ops — readiness and incident drills</summary>
        <ul>
          <li><strong>Readiness</strong> — DB paths, RBAC, tool safety, providers (public).</li>
          <li><strong>Incident drill</strong> — extended checks + recommended actions (admin).</li>
        </ul>`,
      response: `<summary>Where to read results</summary>
        <ul>
          <li><strong>responseMeta</strong> — short status line.</li>
          <li><strong>responseBox</strong> — full JSON/text.</li>
        </ul>`,
    },
    helpQuickstartHtml: `<ul>
      <li><strong>Terminal 1</strong> — keep uvicorn running on port 8765.</li>
      <li><strong>Terminal 2</strong> — curl, scripts, and status checks.</li>
      <li>API output appears in the <strong>Response</strong> block below, not in the uvicorn terminal.</li>
    </ul>`,
    helpTroubleHtml: `<ul>
      <li>Do not run curl in the same terminal as uvicorn — use a second terminal.</li>
      <li>Stage1 requires a non-empty <strong>Pipeline name</strong>.</li>
      <li>If auth is enabled, set API key at the top of the page.</li>
    </ul>`,
    nav: {
      dashboard: "Dashboard",
      chat: "Chat",
      webapps: "Web & assignments",
      task: "Tasks",
      agents: "Agents",
      finetune: "Finetune",
      stage1: "Stage1",
      eval: "Eval",
      ops: "Ops",
    },
  },
  ru: {
    pageTitle: "Termit — локальный AI-оркестратор кода",
    subtitle: "Open-source оркестратор кода · панель управления",
    langLabel: "Язык интерфейса",
    helpTitle: "Справка: функционал и логика работы",
    helpNavLabel: "Разделы:",
    helpQuickstartTitle: "Быстрый старт (2 терминала)",
    helpTroubleTitle: "Если «нет ответа»",
    apiKeyLabel: "API-ключ (необязательно, сохраняется локально)",
    apiKeyPlaceholder: "Нужен при TERMIT_AUTH_ENABLED=true",
    sectionDashboard: "Панель оператора",
    sectionChat: "Чат",
    sectionWebApps: "Веб-приложения и задания",
    sectionTask: "Консоль задач",
    sectionOrchestration: "Мульти-агентная оркестрация",
    sectionAgents: "Профили агентов",
    sectionTeam: "Командное пространство",
    sectionFinetune: "Fine-tune pipeline",
    sectionEval: "Eval (оценка качества)",
    sectionStage1: "Очередь Finetune Stage1",
    sectionOps: "Beta ops",
    sectionRetrieval: "Поиск по коду (RAG)",
    sectionResponse: "Ответ API",
    refreshDashboard: "Обновить панель",
    checkHealthz: "Проверить /healthz",
    taskType: "Тип задачи",
    model: "Модель (необязательная подмена)",
    modelAuto: "auto (выбирает router)",
    sessionId: "ID сессии (необязательно)",
    sessionPlaceholder: "создаётся автоматически при включённой памяти",
    useMemory: "Память сессии",
    useRetrieval: "Подмешивать код из workspace (RAG)",
    retrievalPrefix: "Префикс пути для retrieval",
    repoProfile: "Repo profile (необязательно)",
    routingPolicy: "Политика маршрутизации",
    prompt: "Запрос (prompt)",
    promptPlaceholder: "Опишите задачу по коду...",
    run: "Запустить",
    runStream: "Стриминг",
    clearSession: "Очистить память сессии",
    exportFormat: "Формат экспорта",
    exportSession: "Экспорт сессии",
    downloadExport: "Скачать экспорт",
    checkProviders: "Проверить провайдеры",
    checkUsage: "Статистика использования",
    feedback: "Обратная связь (beta)",
    feedbackPlaceholder: "Что улучшить?",
    sendFeedback: "Отправить feedback",
    taskInput: "Текст задачи",
    taskInputPlaceholder: "Опишите end-to-end задачу...",
    taskMode: "Режим задачи",
    createTask: "Создать задачу",
    taskId: "ID задачи",
    taskIdPlaceholder: "появится после создания",
    refreshTask: "Обновить задачу",
    listTasks: "Список задач",
    loadTaskEvents: "События задачи",
    cancelTask: "Отменить задачу",
    orchestrationInput: "Цель оркестрации",
    orchestrationPlaceholder: "Спланировать, выполнить, проверить, отчёт...",
    runOrchestration: "Запустить оркестрацию",
    newAgentName: "Имя нового агента",
    newAgentPrompt: "System prompt агента",
    newAgentModel: "Модель агента (необязательно)",
    newAgentTools: "Разрешённые tools (через запятую)",
    allowOnline: "Разрешить online-автomation",
    createAgent: "Создать агента",
    listAgents: "Список агентов",
    agentId: "ID агента",
    agentRunInput: "Вход для run агента",
    agentOnlineUrl: "Online URL (необязательно)",
    agentOnlineObjective: "Online objective (необязательно)",
    runAgent: "Запустить агента",
    queueAgentRun: "В очередь (фон)",
    agentRunId: "ID run агента",
    checkAgentRun: "Проверить run",
    loadAgentRunEvents: "События run",
    cancelAgentRun: "Отменить queued run",
    agentToolPath: "Путь для read_file",
    agentReadFile: "Tool: read file",
    teamUsage: "Usage по командам",
    listRoutingProfiles: "Routing profiles",
    exportDashboard: "Экспорт KPI JSON",
    datasetName: "Имя датасета",
    exportDataset: "Экспорт датасета",
    jobId: "ID job",
    createJob: "Создать job из export",
    runJob: "Validate job",
    listJobs: "Список jobs",
    trainingRecipe: "Training recipe",
    adapterModel: "Модель адаптера",
    registerAdapter: "Register adapter",
    listAdapters: "Список adapters",
    scenarioId: "ID сценария",
    listScenarios: "Список сценариев",
    runScenario: "Запустить сценарий",
    suiteCategory: "Фильтр категории (необяз.)",
    runSuite: "Полный suite (24)",
    listEvalReports: "Отчёты eval",
    captureMetrics: "Снимок KPI",
    pipelineName: "Имя pipeline",
    baseModel: "Базовая модель",
    runBaseline: "Baseline eval перед pipeline",
    pipelineRunId: "ID pipeline run",
    enqueueStage1: "Поставить Stage1 в очередь",
    listStage1Runs: "Список Stage1 runs",
    listFailedRuns: "Только failed",
    checkStage1Run: "Проверить Stage1 run",
    cancelStage1Run: "Отменить Stage1 run",
    retryFailedRun: "Retry failed run",
    trainStage1Run: "Обучить сейчас",
    opsReadiness: "Readiness",
    opsDrill: "Incident drill",
    opsQuota: "Quota summary (admin)",
    searchQuery: "Поисковый запрос",
    reindex: "Переиндексировать",
    searchCodebase: "Поиск по коду",
    dashQueue: "Загрузка очереди",
    dashWorkers: "Живые воркеры",
    dashDeadLetter: "Dead-letter rate",
    dashRuns: "Состояния run",
    dashWaiting: "Ожидание метрик...",
    dashLoadFailed: "Не удалось загрузить метрики агентов.",
    dashRefreshFailed: "Ошибка обновления панели.",
    navSidebarDashboard: "Панель",
    navSidebarChat: "Чат",
    navSidebarWebApps: "Веб и задания",
    navSidebarTasks: "Задачи",
    navSidebarAgents: "Агенты",
    navSidebarFinetune: "Finetune",
    navSidebarStage1: "Stage1",
    navSidebarEval: "Eval",
    navSidebarOps: "Ops",
    webAppsHub: {
      intro: "Создайте assignment workspace, проверьте npm-скрипты, засейте web/online агентов.",
      assignmentTitle: "Название задания",
      assignmentBrief: "Brief (≥10 символов)",
      successCriteria: "Критерии успеха (по строке)",
      targetUrls: "Целевые URL (по строке)",
      createAssignment: "Создать задание",
      refreshAssignments: "Обновить список",
      workspace: "Путь workspace (необязательно)",
      loadScripts: "Скрипты workspace",
      seedTitle: "Быстрый seed агентов",
      seedWebApp: "Web App (Vite)",
      seedOnlineProject: "Online Project Manager",
      seedResearchFast: "Research Fast",
      noAssignments: "Заданий пока нет.",
      devPreviewCmd: "Команда dev preview",
      devPreviewHint: "Запустить в корне проекта (Vite :5173)",
      assignmentsLoaded: "Список заданий обновлён",
      assignmentCreated: "Задание создано",
      assignmentValidation: "Нужны название и brief ≥10 символов",
      scriptsLoaded: "Скрипты workspace загружены",
      agentSeeded: "Агент готов",
    },
    agentHub: {
      title: "Центр агентов",
      subtitle: "Карточки профилей, live-метрики очереди и timeline run — всё для работы с автономными агентами.",
      chartStates: "Состояния run",
      chartQueue: "Загрузка очереди (live)",
      chartWorkers: "Воркеры",
      yourAgents: "Ваши агенты",
      refresh: "Обновить",
      compose: "Запуск агента",
      liveFeed: "Live feed",
      advanced: "Расширенные настройки и создание агента",
      promptPlaceholder: "Опишите задачу для агента...",
      timelineEmpty: "Запустите run — здесь появится timeline событий.",
      liveEmpty: "Ответ агента и статус run в реальном времени.",
      select: "Выбрать",
      quickRun: "Быстрый run",
      online: "online",
      modelAuto: "auto",
      noAgents: "Агентов пока нет — создайте в расширенных настройках ниже.",
      healthOk: "Система в норме",
      loadFailed: "Не удалось загрузить hub",
      streamingRun: "Стрим run",
      queueing: "Постановка в очередь",
      defaultPrompt: "Дай краткий обзор этого репозитория.",
      runsTotal: "run",
      noRunsYet: "Пока нет run",
      collectingQueue: "Сбор данных очереди...",
      workersAlive: "живые",
      workersDown: "offline",
      stateQueued: "в очереди",
      stateRunning: "выполняется",
      stateCompleted: "завершён",
      stateFailed: "ошибка",
      stateCancelled: "отменён",
    },
    helpHtml: {
      dashboard: `<summary>Панель: очередь, воркеры, dead-letter</summary>
        <ul>
          <li><strong>Логика:</strong> карточки опрашивают <code>/api/ops/agent-runs/metrics</code> каждые 15 сек и сравнивают с порогами из <code>/api/metrics/thresholds</code>.</li>
          <li><strong>Загрузка очереди</strong> — сколько run ждут воркеров относительно ёмкости; высокие значения = риск backlog.</li>
          <li><strong>Воркеры</strong> — фоновые потоки, выполняющие agent runs (retry, backoff, dead-letter после исчерпания попыток).</li>
          <li><strong>Dead-letter</strong> — доля failed среди завершённых run; sparkline — тренд в текущей сессии браузера.</li>
          <li><strong>/healthz</strong> — проверка зависимостей: SQLite, провайдеры LLM, воркеры, scheduler обслуживания.</li>
        </ul>
        <span class="cmd-block">curl -s http://127.0.0.1:8765/healthz
curl -s http://127.0.0.1:8765/api/metrics/thresholds
curl -s http://127.0.0.1:8765/api/ops/agent-runs/metrics</span>`,
      chat: `<summary>Чат — кнопки и логика маршрутизации</summary>
        <ul>
          <li><strong>Запустить</strong> — один запрос к LLM; если Model пусто, <em>router</em> выбирает модель по task_type (coding/review/debug/explain/general).</li>
          <li><strong>Стриминг</strong> — ответ по токенам (SSE), удобно для длинных текстов.</li>
          <li><strong>Память сессии</strong> — многотуровый диалог; история в SQLite/memory backend.</li>
          <li><strong>RAG</strong> — keyword-индекс workspace, релевантные чанки добавляются в prompt.</li>
          <li><strong>Repo profile + routing policy</strong> — привязка модели к префиксу пути (app/, tests/) и benchmark-routing.</li>
          <li><strong>Fallback</strong> — при сбое провайдера router может переключиться на запасную модель (см. .env).</li>
        </ul>
        <span class="cmd-block">curl -s -X POST http://127.0.0.1:8765/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{"message":"Привет","task_type":"general","use_memory":false}'</span>`,
      task: `<summary>Задачи — plan → execute → verify → report</summary>
        <ul>
          <li><strong>Создать задачу</strong> — mode=auto проходит полный цикл; guided — по шагам с паузами между фазами.</li>
          <li><strong>Обновить задачу</strong> — текущий state, report, error. Ожидайте: queued → running → verifying → completed | failed.</li>
          <li><strong>Список задач</strong> — последние записи из SQLite.</li>
          <li><strong>События задачи</strong> — журнал шагов (retry, failure_class). Смотрите при failed.</li>
          <li><strong>Отмена</strong> — только для queued/running задач.</li>
        </ul>
        <span class="cmd-block">curl -s -X POST http://127.0.0.1:8765/api/tasks \\
  -H "Content-Type: application/json" \\
  -d '{"input":"Подготовь отчёт","task_type":"coding","mode":"auto"}'</span>`,
      agents: `<summary>Агенты — профили, очередь, online</summary>
        <ul>
          <li><strong>Создать агента</strong> — профиль: prompt, model, tools. После создания — agent_id в поле ID агента.</li>
          <li><strong>Список агентов</strong> — все профили и их настройки.</li>
          <li><strong>Запустить агента</strong> — синхронный run; ответ сразу в блоке Response.</li>
          <li><strong>В очередь (фон)</strong> — arun_... в очередь; проверяйте через «Проверить run» / «События run».</li>
          <li><strong>Отменить queued run</strong> — только для статуса queued.</li>
          <li><strong>Tool: read file</strong> — тест read_file для выбранного agent_id.</li>
          <li><strong>Online</strong> — галочка allow_online + tool web_automation + online_url/objective в payload.</li>
          <li><strong>Run events</strong> — run_queued, run_attempt_started, run_retry_scheduled, run_dead_lettered.</li>
        </ul>
        <span class="cmd-block">curl -s http://127.0.0.1:8765/api/agents
curl -s -X POST http://127.0.0.1:8765/api/agents/AGENT_ID/runs \\
  -H "Content-Type: application/json" \\
  -d '{"input":"Сделай краткий обзор README"}'</span>`,
      orchestration: `<summary>Оркестрация planner → executor → verifier</summary>
        <ul>
          <li>Один запрос запускает цепочку фаз и task runner; результат — plan, phases, report.</li>
          <li>Может занять несколько минут — смотрите блок Response.</li>
        </ul>
        <span class="cmd-block">curl -s -X POST http://127.0.0.1:8765/api/orchestration/run \\
  -H "Content-Type: application/json" \\
  -d '{"objective":"Проверь health endpoint и опиши риски"}'</span>`,
      finetune: `<summary>Finetune MVP — датасет, job, recipe, adapter</summary>
        <ul>
          <li><strong>Экспорт датасета</strong> — JSONL из feedback + tasks + agent_runs (нужен min_samples). Путь dataset_path — в Response.</li>
          <li><strong>Создать job</strong> — job на последний export; job_id появится в поле ID job.</li>
          <li><strong>Validate job</strong> — проверка датасета; для обучения — кнопка <strong>Обучить сейчас</strong> или TERMIT_FINETUNE_AUTO_TRAIN.</li>
          <li><strong>Список jobs / Training recipe</strong> — jobs и подсказки Modelfile/CLI для QLoRA/Ollama.</li>
          <li><strong>Register adapter</strong> — finetuned модель + опционально repo profile.</li>
        </ul>
        <span class="cmd-block">python3 scripts/finetune_export.py --name termit-export --min-samples 1
curl -s -X POST http://127.0.0.1:8765/api/finetune/datasets/export \\
  -H "Content-Type: application/json" \\
  -d '{"name":"termit-export","min_samples":1}'</span>`,
      eval: `<summary>Eval — 24 сценария качества</summary>
        <ul>
          <li><strong>Список сценариев</strong> — 24 сценария: coding (A*), local ops (L*), web (W*).</li>
          <li><strong>Запустить сценарий</strong> — один прогон по ID (A1, L1, W1...).</li>
          <li><strong>Полный suite (24)</strong> — долгий прогон; отчёт в eval_reports.jsonl с pass_rate.</li>
          <li><strong>Отчёты eval</strong> — pass_rate последних прогонов.</li>
          <li><strong>Снимок KPI</strong> — telemetry для dashboard.</li>
        </ul>
        <span class="cmd-block">curl -s http://127.0.0.1:8765/api/eval/scenarios
curl -s -X POST http://127.0.0.1:8765/api/eval/suite \\
  -H "Content-Type: application/json" \\
  -d '{"limit":24}'</span>`,
      stage1: `<summary>Stage1 — автоматический weekly pipeline (важно)</summary>
        <ul>
          <li><strong>Поставить Stage1 в очередь</strong> — export → eval (если галочка) → validate job → recipe. Сразу JSON с run_id; прогресс — finetunePanel и SSE.</li>
          <li><strong>Имя pipeline обязательно!</strong> Пустое имя = ошибка без enqueue.</li>
          <li><strong>Baseline eval</strong> — eval-suite перед pipeline (дольше, но с метриками baseline).</li>
          <li><strong>Список / failed runs</strong> — история и только failed для retry.</li>
          <li><strong>Статусы:</strong> queued → running → completed | failed | cancelled. Cancel — только queued.</li>
          <li><strong>Retry failed run</strong> — повтор failed run (тот же run_id).</li>
          <li><strong>Обучить сейчас</strong> — встроенный trainer (ollama create) после completed pipeline.</li>
          <li>Auto-train: TERMIT_FINETUNE_AUTO_TRAIN=true; API: POST …/stage1-runs/{run_id}/train</li>
          <li>Scheduler: TERMIT_STAGE1_SCHEDULE_ENABLED=true + перезапуск uvicorn; launchd/cron — scripts/install_stage1_scheduler.sh</li>
        </ul>
        <span class="cmd-block">python3 scripts/stage1_enqueue.py \\
  --base-url http://127.0.0.1:8765 \\
  --name weekly-stage1 --min-samples 1 --no-eval-baseline

curl -s http://127.0.0.1:8765/api/finetune/pipeline/stage1-runs/RUN_ID
curl -s -X POST http://127.0.0.1:8765/api/finetune/pipeline/stage1-runs/RUN_ID/retry</span>`,
      ops: `<summary>Ops — readiness и инциденты</summary>
        <ul>
          <li><strong>Readiness</strong> — БД, paths, RBAC, tool safety, providers (без auth).</li>
          <li><strong>Incident drill</strong> — расширенные проверки + recommended actions (admin).</li>
          <li><strong>Quota</strong> — расход API keys и team quotas.</li>
        </ul>`,
      team: `<summary>Команды и routing profiles</summary>
        <ul>
          <li><strong>Usage по командам</strong> — потребление квот TERMIT_TEAM_QUOTAS.</li>
          <li><strong>Routing profiles</strong> — repo_model_profiles.json: какая модель для app/, tests/ и т.д.</li>
          <li><strong>Экспорт KPI JSON</strong> — снимок метрик для отчётов и dashboard.</li>
        </ul>`,
      retrieval: `<summary>RAG — индекс и поиск по workspace</summary>
        <ul>
          <li><strong>Переиндексировать</strong> — пересборка индекса после больших изменений в коде.</li>
          <li><strong>Поиск по коду</strong> — чанки для чата при включённом «Подмешивать код из workspace».</li>
        </ul>
        <span class="cmd-block">curl -s -X POST http://127.0.0.1:8765/api/retrieval/reindex
curl -s -X POST http://127.0.0.1:8765/api/retrieval/search \\
  -H "Content-Type: application/json" \\
  -d '{"query":"ChatService","limit":5}'</span>`,
      response: `<summary>Куда смотреть результат</summary>
        <ul>
          <li><strong>responseMeta</strong> — краткий статус (ok/error, run_id).</li>
          <li><strong>responseBox</strong> — полный JSON или текст.</li>
          <li><strong>finetunePanel / taskPanel</strong> — компактный прогресс pipeline и задач.</li>
        </ul>`,
    },
    helpQuickstartHtml: `<ul>
      <li><strong>Терминал 1</strong> — держите сервер: <code>uvicorn app.main:app --host 0.0.0.0 --port 8765</code></li>
      <li><strong>Терминал 2</strong> — curl, python-скрипты, проверки.</li>
      <li>Ответы API — в блоке <strong>Response</strong> внизу страницы, не в терминале uvicorn.</li>
    </ul>
    <span class="cmd-block">cd ~/Projects/Termit && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8765

curl -s http://127.0.0.1:8765/healthz</span>`,
    helpTroubleHtml: `<ul>
      <li>Не запускайте curl в том же терминале, где uvicorn — откройте второй.</li>
      <li>Для Stage1 заполните <strong>Имя pipeline</strong>.</li>
      <li>При auth укажите API-ключ вверху страницы.</li>
      <li>Ошибки смотрите в Response и finetunePanel / taskPanel.</li>
    </ul>`,
    nav: {
      dashboard: "Панель",
      chat: "Чат",
      webapps: "Веб и задания",
      task: "Задачи",
      agents: "Агенты",
      finetune: "Finetune",
      stage1: "Stage1",
      eval: "Eval",
      ops: "Ops",
    },
  },
};

window.TERMIT_I18N_KEYS = {
  "page.subtitle": "subtitle",
  "help.title": "helpTitle",
  "help.navLabel": "helpNavLabel",
  "help.quickstartTitle": "helpQuickstartTitle",
  "help.troubleTitle": "helpTroubleTitle",
  "label.apiKey": "apiKeyLabel",
  "section.dashboard": "sectionDashboard",
  "section.chat": "sectionChat",
  "section.webApps": "sectionWebApps",
  "section.task": "sectionTask",
  "nav.sidebarWebApps": "navSidebarWebApps",
  "section.orchestration": "sectionOrchestration",
  "section.agents": "sectionAgents",
  "section.team": "sectionTeam",
  "section.finetune": "sectionFinetune",
  "section.eval": "sectionEval",
  "section.stage1": "sectionStage1",
  "section.ops": "sectionOps",
  "section.retrieval": "sectionRetrieval",
  "section.response": "sectionResponse",
  "btn.refreshDashboard": "refreshDashboard",
  "btn.checkHealthz": "checkHealthz",
  "label.taskType": "taskType",
  "label.model": "model",
  "label.sessionId": "sessionId",
  "label.useMemory": "useMemory",
  "label.useRetrieval": "useRetrieval",
  "label.retrievalPrefix": "retrievalPrefix",
  "label.repoProfile": "repoProfile",
  "label.routingPolicy": "routingPolicy",
  "label.prompt": "prompt",
  "btn.run": "run",
  "btn.runStream": "runStream",
  "btn.clearSession": "clearSession",
  "label.exportFormat": "exportFormat",
  "btn.exportSession": "exportSession",
  "btn.downloadExport": "downloadExport",
  "btn.checkProviders": "checkProviders",
  "btn.checkUsage": "checkUsage",
  "label.feedback": "feedback",
  "btn.sendFeedback": "sendFeedback",
  "label.taskInput": "taskInput",
  "label.taskMode": "taskMode",
  "btn.createTask": "createTask",
  "label.taskId": "taskId",
  "btn.refreshTask": "refreshTask",
  "btn.listTasks": "listTasks",
  "btn.loadTaskEvents": "loadTaskEvents",
  "btn.cancelTask": "cancelTask",
  "label.orchestrationInput": "orchestrationInput",
  "btn.runOrchestration": "runOrchestration",
  "label.newAgentName": "newAgentName",
  "label.newAgentPrompt": "newAgentPrompt",
  "label.newAgentModel": "newAgentModel",
  "label.newAgentTools": "newAgentTools",
  "label.allowOnline": "allowOnline",
  "btn.createAgent": "createAgent",
  "btn.listAgents": "listAgents",
  "label.agentId": "agentId",
  "label.agentRunInput": "agentRunInput",
  "label.agentOnlineUrl": "agentOnlineUrl",
  "label.agentOnlineObjective": "agentOnlineObjective",
  "btn.runAgent": "runAgent",
  "btn.queueAgentRun": "queueAgentRun",
  "label.agentRunId": "agentRunId",
  "btn.checkAgentRun": "checkAgentRun",
  "btn.loadAgentRunEvents": "loadAgentRunEvents",
  "btn.cancelAgentRun": "cancelAgentRun",
  "label.agentToolPath": "agentToolPath",
  "btn.agentReadFile": "agentReadFile",
  "btn.teamUsage": "teamUsage",
  "btn.listRoutingProfiles": "listRoutingProfiles",
  "btn.exportDashboard": "exportDashboard",
  "label.datasetName": "datasetName",
  "btn.exportDataset": "exportDataset",
  "label.jobId": "jobId",
  "btn.createJob": "createJob",
  "btn.runJob": "runJob",
  "btn.listJobs": "listJobs",
  "btn.trainingRecipe": "trainingRecipe",
  "label.adapterModel": "adapterModel",
  "btn.registerAdapter": "registerAdapter",
  "btn.listAdapters": "listAdapters",
  "label.scenarioId": "scenarioId",
  "btn.listScenarios": "listScenarios",
  "btn.runScenario": "runScenario",
  "label.suiteCategory": "suiteCategory",
  "btn.runSuite": "runSuite",
  "btn.listEvalReports": "listEvalReports",
  "btn.captureMetrics": "captureMetrics",
  "label.pipelineName": "pipelineName",
  "label.baseModel": "baseModel",
  "label.runBaseline": "runBaseline",
  "label.pipelineRunId": "pipelineRunId",
  "btn.enqueueStage1": "enqueueStage1",
  "btn.listStage1Runs": "listStage1Runs",
  "btn.listFailedRuns": "listFailedRuns",
  "btn.checkStage1Run": "checkStage1Run",
  "btn.cancelStage1Run": "cancelStage1Run",
  "btn.retryFailedRun": "retryFailedRun",
  "btn.trainStage1Run": "trainStage1Run",
  "btn.opsReadiness": "opsReadiness",
  "btn.opsDrill": "opsDrill",
  "btn.opsQuota": "opsQuota",
  "label.searchQuery": "searchQuery",
  "btn.reindex": "reindex",
  "btn.searchCodebase": "searchCodebase",
  "dash.queue": "dashQueue",
  "dash.workers": "dashWorkers",
  "dash.deadLetter": "dashDeadLetter",
  "dash.runs": "dashRuns",
  "dash.waiting": "dashWaiting",
  "label.lang": "langLabel",
};

window.TERMIT_LANG_KEY = "termit_ui_lang";

window.getTermitLang = function getTermitLang() {
  const stored = localStorage.getItem(window.TERMIT_LANG_KEY);
  return stored === "en" ? "en" : "ru";
};

window.setTermitLang = function setTermitLang(lang) {
  localStorage.setItem(window.TERMIT_LANG_KEY, lang === "en" ? "en" : "ru");
};

window.tTermit = function tTermit(key, lang) {
  const active = lang || window.getTermitLang();
  const pack = window.TERMIT_I18N[active] || window.TERMIT_I18N.ru;
  if (pack[key]) return pack[key];
  if (key.startsWith("agentHub.")) {
    const hubKey = key.slice("agentHub.".length);
    if (pack.agentHub && pack.agentHub[hubKey]) return pack.agentHub[hubKey];
    const enHub = window.TERMIT_I18N.en.agentHub || {};
    if (enHub[hubKey]) return enHub[hubKey];
  }
  if (key.startsWith("webAppsHub.")) {
    const hubKey = key.slice("webAppsHub.".length);
    if (pack.webAppsHub && pack.webAppsHub[hubKey]) return pack.webAppsHub[hubKey];
    const enHub = window.TERMIT_I18N.en.webAppsHub || {};
    if (enHub[hubKey]) return enHub[hubKey];
  }
  if (key.startsWith("terminalDock.")) {
    const parts = key.slice("terminalDock.".length).split(".");
    let cur = pack.terminalDock;
    for (const p of parts) {
      if (!cur) break;
      cur = cur[p];
    }
    if (typeof cur === "string") return cur;
    const enTd = window.TERMIT_I18N.en.terminalDock || {};
    let enCur = enTd;
    for (const p of parts) {
      if (!enCur) break;
      enCur = enCur[p];
    }
    if (typeof enCur === "string") return enCur;
  }
  return window.TERMIT_I18N.en[key] || key;
};

window.applyTermitLanguage = function applyTermitLanguage(lang) {
  const active = lang === "en" ? "en" : "ru";
  window.setTermitLang(active);
  const pack = window.TERMIT_I18N[active];
  document.documentElement.lang = active;
  document.title = pack.pageTitle;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    const mapKey = window.TERMIT_I18N_KEYS[key];
    if (mapKey && pack[mapKey]) {
      el.textContent = pack[mapKey];
      return;
    }
    if (key.startsWith("agentHub.") && pack.agentHub) {
      const hubVal = pack.agentHub[key.slice("agentHub.".length)];
      if (hubVal) {
        el.textContent = hubVal;
        return;
      }
    }
    if (key.startsWith("webAppsHub.") && pack.webAppsHub) {
      const hubVal = pack.webAppsHub[key.slice("webAppsHub.".length)];
      if (hubVal) {
        el.textContent = hubVal;
        return;
      }
    }
    if (key.startsWith("terminalDock.") && pack.terminalDock) {
      const tdVal = pack.terminalDock[key.slice("terminalDock.".length)];
      if (tdVal) {
        el.textContent = tdVal;
        return;
      }
    }
    if (key.startsWith("nav.sidebar") && pack[key.replace("nav.sidebar", "navSidebar")]) {
      el.textContent = pack[key.replace("nav.sidebar", "navSidebar")];
    }
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const mapKey = el.getAttribute("data-i18n-placeholder");
    if (mapKey && pack[mapKey]) {
      el.placeholder = pack[mapKey];
      return;
    }
    if (mapKey.startsWith("agentHub.") && pack.agentHub) {
      const hubVal = pack.agentHub[mapKey.slice("agentHub.".length)];
      if (hubVal) el.placeholder = hubVal;
    }
  });

  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const section = el.getAttribute("data-i18n-html");
    if (pack.helpHtml && pack.helpHtml[section]) {
      el.innerHTML = pack.helpHtml[section];
    }
  });

  const quickstart = document.getElementById("helpQuickstartBody");
  if (quickstart) quickstart.innerHTML = pack.helpQuickstartHtml;
  const trouble = document.getElementById("helpTroubleBody");
  if (trouble) trouble.innerHTML = pack.helpTroubleHtml;

  const nav = pack.nav || {};
  Object.entries({
    "nav-dashboard": nav.dashboard,
    "nav-chat": nav.chat,
    "nav-webapps": nav.webapps,
    "nav-task": nav.task,
    "nav-agents": nav.agents,
    "nav-finetune": nav.finetune,
    "nav-stage1": nav.stage1,
    "nav-eval": nav.eval,
    "nav-ops": nav.ops,
  }).forEach(([id, text]) => {
    const el = document.getElementById(id);
    if (el && text) el.textContent = text;
  });

  const langSelect = document.getElementById("uiLang");
  if (langSelect) langSelect.value = active;

  const modelAuto = document.getElementById("modelAutoOption");
  if (modelAuto) modelAuto.textContent = pack.modelAuto;

  if (typeof window.onTermitLanguageApplied === "function") {
    window.onTermitLanguageApplied(active);
  }
  if (window.TermitAgentHub && typeof window.TermitAgentHub.refresh === "function") {
    window.TermitAgentHub.refresh();
  }
  if (window.TermitTooltips && typeof window.TermitTooltips.applyTipsToDom === "function") {
    window.TermitTooltips.applyTipsToDom();
  }
  if (window.TermitTerminalDock && typeof window.TermitTerminalDock.init === "function") {
    window.TermitTerminalDock.init();
  }
};
