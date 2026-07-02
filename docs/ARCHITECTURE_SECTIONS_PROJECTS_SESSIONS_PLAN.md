# План внедрения: трёхуровневая иерархия Раздел → Проект → Сессия

> **Дата:** 01.07.2026
> **Основание:** сравнение текущего кода TermitPro + CyberFlow со спецификацией
> `Архитектура_Проекты_Сессии_Спецификация_1.md`
> **Статус:** план, согласование

---

## Сравнительная таблица: что есть vs что нужно

| # | Компонент | Статус в TermitPro | По спецификации | Разрыв |
|---|-----------|-------------------|-----------------|--------|
| **1** | **Физические папки Разделов** | ❌ Есть папки проектов в `/User/TermitPro/<ProjectName>/.termit/` — но НЕТ папок разделов на диске. Разделы — только в БД. | `/Workspace/_Sections/{id}__{slug}/` с `section.meta.json` | 🔴 КРИТИЧНЫЙ |
| **2** | **Физические папки Проектов** | ⚠️ Частично: папка проекта создаётся (`<Project>/.termit/`), но нет `project.meta.json`, нет подпапок `sessions/shared_files/prompts_library/exports/` | `/Workspace/_Sections/{section}/{id}__{slug}/` + `project.meta.json` + `sessions/shared_files/prompts_library/exports/` | 🟡 СРЕДНИЙ |
| **3** | **Сессии в папке проекта** | ⚠️ Сессии хранятся в БД (`sessions` таблица). НЕТ физических папок сессий на диске с промтами, файлами, вложениями | `sessions/{id}__{date}/` с `session.meta.json`, `prompts/`, `files/`, `attachments/`, `transcript.md` | 🔴 КРИТИЧНЫЙ |
| **4** | **Свободные сессии** | ✅ Есть: `_Unassigned_Sessions` отсутствует папка, но БД-уровень есть: сессии без `project_id` | `/Workspace/_Unassigned_Sessions/{id}__{date}/` | 🟡 СРЕДНИЙ |
| **5** | **SQLite — источник истины** | ✅ SQLite есть, схема богатая: `sections`, `projects`, `sessions`, `messages`, `file_provenance`, `project_*` (15+ таблиц) | SQLite как индекс поверх ФС | 🟢 OK (нужна перестройка на ФС-first) |
| **6** | **Переносимость** | ❌ Данные привязаны к абсолютным путям. Невозможно скопировать и перенести | Копирование `/Workspace/` → пересборка индекса → работает | 🔴 КРИТИЧНЫЙ |
| **7** | **Detail Panel** | ❌ НЕТ ни в Swift, ни в вебе. Есть только базовый сайдбар (разделы/папки) | Вкладки: Обзор/Файлы/Сессии/Хуки/Настройки | 🔴 КРИТИЧНЫЙ |
| **8** | **Открыть в Finder** | ❌ НЕТ нигде | `open -R` / `explorer /select` / helper-процесс для веба | 🔴 КРИТИЧНЫЙ |
| **9** | **Дерево файлов (File Tree)** | ❌ НЕТ UI-компонента. Есть `file_provenance` в БД | Дерево из БД (lazy load), file watcher, превью, drag-and-drop | 🔴 КРИТИЧНЫЙ |
| **10** | **Система хуков/плагинов** | ✅ **ЕСТЬ!** Полноценная в `backend/hooks.py`: 34 события, 4 типа (command/python/webhook/skill), matcher, контекст, блокировка (exit code 2), глобальные + проектные | Каталог плагинов в `/Workspace/_plugins/`, манифесты, таблицы `plugins/hooks/hook_runs`, UI подключаемых хуков | 🟢 В основном готово — нужно добавить UI + БД-слой |
| **11** | **Автосуммаризация сессии** | ⚠️ Частично: `session_summaries` таблица есть, но нет автоматического запуска на `on_session_closed` | Builtin-плагин Auto-Summary | 🟡 СРЕДНИЙ |
| **12** | **Экспорт/Импорт проекта** | ✅ Есть: `chief_export.py` (`handle_export_project`, `handle_import_project`), `projects_api.py` (`handle_import_project_from_path`, `handle_import_project_full`) | Архивация папки + `project.meta.json` | 🟢 OK |
| **13** | **Глобальный поиск FTS5** | ✅ Есть: `messages_fts` (FTS5) для сообщений | FTS5-таблица для промтов и файлов | 🟢 OK (нужно расширить) |
| **14** | **Модальное окно привязки сессии** | ⚠️ Частично: `NewSessionProjectSheet.swift` — выбор проекта при создании, но нет обязательного модального окна | Обязательное модальное окно: «Привязать к проекту» ИЛИ «Без проекта» | 🟡 МАЛЫЙ |
| **15** | **Перепривязка сессии** | ❌ НЕТ операции перемещения папки сессии между проектами | Физическое перемещение папки + обновление БД | 🟡 МАЛЫЙ |
| **16** | **Наследование хуков** | ❌ НЕТ поля `inherit` для каскадного применения хуков | `hooks.inherit` — подключение на Раздел → все дочерние Проекты/Сессии | 🟡 МАЛЫЙ |
| **17** | **Файловый вотчер** | ❌ НЕТ | `watchdog`/`chokidar` для автосинхронизации ФС ↔ БД | 🔴 КРИТИЧНЫЙ |

### Легенда
- 🔴 КРИТИЧНЫЙ — фундаментальное отличие, требует создания с нуля
- 🟡 СРЕДНИЙ — есть частичная реализация, требует доработки
- 🟢 OK — уже есть или близко к спецификации

---

## Текущая архитектура TermitPro (что построено)

```
┌─────────────────────────────────────────────────────────┐
│                  TermitPro (macOS .app)                  │
│                                                         │
│  ┌──────────────────┐     ┌───────────────────────────┐ │
│  │   SwiftUI Client  │────▶│   FastAPI Backend (:8645) │ │
│  │   (Sources/)      │     │   (CyberFlow/backend/)    │ │
│  │                   │     │                           │ │
│  │  - Sidebar        │     │  - projects_api.py        │ │
│  │  - ChatView       │     │  - hooks.py (✅)          │ │
│  │  - FolderStore    │     │  - chief_export.py        │ │
│  │  - TabManager     │     │  - termit_backend.py      │ │
│  └──────────────────┘     └───────────┬───────────────┘ │
│                                       │                  │
│                            ┌──────────▼───────────────┐ │
│                            │   SQLite state.db         │ │
│                            │   (~/.termit/data/)       │ │
│                            │                           │ │
│                            │   sections                │ │
│                            │   projects (10 шт)        │ │
│                            │   sessions (158+ шт)      │ │
│                            │   messages + FTS5         │ │
│                            │   file_provenance         │ │
│                            │   project_* (6 таблиц)    │ │
│                            │   session_* (4 таблицы)   │ │
│                            └───────────────────────────┘ │
│                                                         │
│  Файловая система:                                      │
│  /Users/amoros/TermitPro/                              │
│    <ProjectName>/                                       │
│      .termit/          ← метаданные проекта             │
│        project.json                                     │
│        project.md                                       │
│        memory.json                                      │
│        files/                                            │
│        knowledge/                                        │
│        sessions/                                         │
│        agents/                                           │
│        config/                                           │
│        logs/                                             │
└─────────────────────────────────────────────────────────┘
```

---

## Целевая архитектура (по спецификации)

```
┌─────────────────────────────────────────────────────────────┐
│             TermitPro Workspace                              │
│                                                              │
│  /Users/amoros/TermitPro/Workspace/  ← КОРЕНЬ               │
│  │                                                           │
│  ├── _index/workspace.db              ← SQLite индекс       │
│  │                                                           │
│  ├── _Sections/                        ← ВСЕ разделы         │
│  │   ├── {id}__{slug}/                                        │
│  │   │   ├── section.meta.json         ← метаданные раздела  │
│  │   │   ├── {id}__{slug}/              ← ПРОЕКТ             │
│  │   │   │   ├── project.meta.json                            │
│  │   │   │   ├── sessions/              ← сессии проекта      │
│  │   │   │   │   └── {id}__{date}/                            │
│  │   │   │   │       ├── session.meta.json                    │
│  │   │   │   │       ├── prompts/                             │
│  │   │   │   │       ├── files/                               │
│  │   │   │   │       ├── attachments/                         │
│  │   │   │   │       └── transcript.md                        │
│  │   │   │   ├── shared_files/                                │
│  │   │   │   ├── prompts_library/                             │
│  │   │   │   └── exports/                                     │
│  │   │   └── ... другие проекты                               │
│  │   └── ... другие разделы                                   │
│  │                                                           │
│  ├── _Unassigned_Sessions/             ← свободные сессии    │
│  │   └── {id}__{date}/                                         │
│  │       ├── session.meta.json                                │
│  │       ├── prompts/                                         │
│  │       ├── files/                                           │
│  │       └── transcript.md                                    │
│  │                                                           │
│  └── _plugins/                          ← каталог плагинов   │
│      └── {id}__{slug}/                                         │
│          ├── plugin.manifest.json                             │
│          ├── entrypoint.(js|py|sh)                            │
│          └── icon.png                                         │
└──────────────────────────────────────────────────────────────┘
```

---

## План внедрения по фазам

### ══════════════ ФАЗА 0: Подготовка и миграция ══════════════

#### 0.1 Выбор корневой папки Workspace
- **Решение:** `/Users/amoros/TermitPro/Workspace/` — новый чистый корень
- Старая структура (`<Project>/.termit/`) остаётся нетронутой для обратной совместимости
- Миграция: одноразовый скрипт `scripts/migrate_to_workspace.py`

#### 0.2 Создание корневой структуры
```bash
mkdir -p /Users/amoros/TermitPro/Workspace/{_Sections,_Unassigned_Sessions,_index,_plugins}
```

#### 0.3 Миграция существующих данных
- 10 проектов из БД → физические папки с `project.meta.json`
- 158 сессий → физические папки (с промтами/файлами из `messages`)
- 3 системных раздела → физические папки разделов
- Скрипт: `scripts/migrate_to_workspace.py`

---

### ══════════════ ФАЗА 1: Фундамент (БД + ФС-слой) ══════════════

#### 1.1 Новая схема БД (расширение существующей)

**Что уже есть и НЕ трогаем:**
- `sections` — уже имеет `parent_id`, `item_type`, `path`, `source`, `slug`, `description`, `project_id`, `archived`, `metadata`
- `projects` — уже имеет `slug`, `description`, `root_path`, `is_active`
- `sessions` — уже имеет `project_id`, `section_id`, `metadata`, все поля токенов/стоимости
- `messages` + FTS5 — полноценный

**Что добавляем (ALTER TABLE):**

```sql
-- Разделы: добавляем поле для пути к папке на диске
ALTER TABLE sections ADD COLUMN fs_path TEXT;       -- путь от корня Workspace

-- Проекты: добавляем поля для ФС-структуры
ALTER TABLE projects ADD COLUMN fs_path TEXT;       -- путь от корня Workspace
ALTER TABLE projects ADD COLUMN schema_version INTEGER DEFAULT 1;
ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'active';  -- active/archived/paused

-- Сессии: добавляем поля для ФС
ALTER TABLE sessions ADD COLUMN fs_path TEXT;       -- путь от корня Workspace
ALTER TABLE sessions ADD COLUMN is_assigned INTEGER DEFAULT 0;  -- 0=Unassigned, 1=в проекте

-- НОВЫЕ таблицы:
-- Файлы (индекс для быстрого поиска)
CREATE TABLE workspace_files (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id) ON DELETE CASCADE,
    session_id      TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    path            TEXT NOT NULL,           -- относительный от корня Workspace
    file_type       TEXT,                    -- pdf/docx/image/code/...
    size_bytes      INTEGER,
    content_hash    TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL
);
CREATE INDEX idx_wsfiles_project ON workspace_files(project_id);
CREATE INDEX idx_wsfiles_session ON workspace_files(session_id);

-- Библиотека промтов
CREATE TABLE prompts_library (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT,
    content         TEXT NOT NULL,
    tags            TEXT,                    -- JSON-массив
    source_session_id TEXT,                  -- из какой сессии сохранён
    created_at      REAL NOT NULL
);
CREATE INDEX idx_prompts_project ON prompts_library(project_id);
CREATE VIRTUAL TABLE prompts_fts USING fts5(title, content, content_rowid='rowid');

-- Плагины (каталог)
CREATE TABLE workspace_plugins (
    id              TEXT PRIMARY KEY,
    slug            TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    version         TEXT,
    type            TEXT NOT NULL,           -- script/webhook/builtin
    manifest_path   TEXT,
    supported_events TEXT,                   -- JSON-массив
    fs_path         TEXT,                    -- путь к папке плагина
    created_at      REAL NOT NULL
);

-- Хуки (подключения плагинов к объектам)
CREATE TABLE workspace_hooks (
    id              TEXT PRIMARY KEY,
    plugin_id       TEXT NOT NULL REFERENCES workspace_plugins(id) ON DELETE CASCADE,
    scope_type      TEXT NOT NULL,           -- section/project/session
    scope_id        TEXT NOT NULL,
    event           TEXT NOT NULL,
    config          TEXT,                    -- JSON настройки
    inherit         INTEGER DEFAULT 0,       -- каскадно на дочерние объекты
    enabled         INTEGER DEFAULT 1,
    created_at      REAL NOT NULL
);
CREATE INDEX idx_whooks_scope ON workspace_hooks(scope_type, scope_id);
CREATE INDEX idx_whooks_plugin ON workspace_hooks(plugin_id);

-- Журнал запусков хуков
CREATE TABLE workspace_hook_runs (
    id              TEXT PRIMARY KEY,
    hook_id         TEXT NOT NULL REFERENCES workspace_hooks(id) ON DELETE CASCADE,
    triggered_at    REAL NOT NULL,
    status          TEXT,                    -- success/error/running/pending
    log             TEXT,
    duration_ms     INTEGER,
    retry_count     INTEGER DEFAULT 0
);
CREATE INDEX idx_whruns_hook ON workspace_hook_runs(hook_id);
```

#### 1.2 Python-модуль: `backend/workspace_fs.py`

Новый модуль — **единственный слой для работы с ФС**. Все операции создания/чтения/удаления Разделов/Проектов/Сессий идут через него.

```python
# Ключевые функции:

# Разделы
create_section_fs(section_id, slug, metadata) -> path
read_section_meta(section_id) -> dict
update_section_meta(section_id, meta) -> None
delete_section_fs(section_id) -> bool

# Проекты
create_project_fs(project_id, slug, section_id, metadata) -> path
init_project_structure(project_path)          # sessions/, shared_files/, prompts_library/, exports/
read_project_meta(project_id) -> dict
update_project_meta(project_id, meta) -> None
delete_project_fs(project_id) -> bool
move_project_to_section(project_id, new_section_id) -> path

# Сессии
create_session_fs(session_id, project_id=None) -> path
init_session_structure(session_path)          # prompts/, files/, attachments/, transcript.md
read_session_meta(session_id) -> dict
update_session_meta(session_id, meta) -> None
save_transcript(session_id, messages) -> path
save_prompt(session_id, prompt_text) -> path
move_session_to_project(session_id, new_project_id) -> path
delete_session_fs(session_id) -> bool

# Утилиты
scan_workspace() -> dict                       # полный обход ФС → словарь
rebuild_index_from_disk() -> None              # пересборка БД по ФС
reveal_in_finder(path) -> None                 # open -R для macOS
add_file_to_project(project_id, file_path) -> None  # копирование в shared_files/
add_file_to_session(session_id, file_path, category) -> None
get_file_tree(scope_type, scope_id) -> list    # дерево файлов из БД
```

#### 1.3 Фоновый сканер: `backend/workspace_scanner.py`

- При запуске сервера: сверяет ФС ↔ БД, перестраивает при расхождениях
- При каждом изменении (CRUD): мгновенно синхронизирует БД
- Файловый вотчер (`watchdog`): отслеживает ручные изменения через Finder

```python
class WorkspaceScanner:
    """Сканер для синхронизации ФС ↔ БД."""
    
    async def full_scan(self) -> ScanReport
    async def start_watcher(self) -> None        # watchdog.Observer
    async def stop_watcher(self) -> None
    async def on_file_event(self, event) -> None  # created/modified/deleted
```

#### 1.4 API-роуты: `backend/workspace_api.py`

```python
# Разделы
GET    /api/workspace/sections              # список разделов + дети
POST   /api/workspace/sections              # создать раздел
PUT    /api/workspace/sections/{id}         # обновить
DELETE /api/workspace/sections/{id}         # удалить

# Проекты
GET    /api/workspace/projects              # список проектов
GET    /api/workspace/projects/{id}         # детали проекта (файлы, сессии, хуки)
POST   /api/workspace/projects              # создать проект (в разделе)
PUT    /api/workspace/projects/{id}         # обновить
DELETE /api/workspace/projects/{id}         # удалить
POST   /api/workspace/projects/{id}/export  # экспорт в ZIP
POST   /api/workspace/projects/import       # импорт из ZIP

# Сессии
POST   /api/workspace/sessions              # создать сессию (с выбором проекта)
PUT    /api/workspace/sessions/{id}/assign  # перепривязать сессию
PUT    /api/workspace/sessions/{id}/unassign # отвязать от проекта

# Файлы
GET    /api/workspace/{type}/{id}/files     # дерево файлов (lazy load)
POST   /api/workspace/{type}/{id}/files     # добавить файл (multipart)
DELETE /api/workspace/{type}/{id}/files/{file_id}  # удалить
POST   /api/workspace/reveal               # открыть в Finder {path}

# Система хуков
GET    /api/workspace/plugins               # каталог плагинов
POST   /api/workspace/plugins/install       # установить плагин
GET    /api/workspace/{type}/{id}/hooks     # список хуков объекта
POST   /api/workspace/{type}/{id}/hooks     # подключить плагин (создать хук)
PUT    /api/workspace/hooks/{id}            # обновить настройки хука
DELETE /api/workspace/hooks/{id}            # отключить хук
POST   /api/workspace/hooks/{id}/run        # запустить хук вручную
GET    /api/workspace/hooks/{id}/runs       # лог запусков

# Системные
POST   /api/workspace/rebuild-index         # пересборка БД из ФС
GET    /api/workspace/health                # состояние синхронизации
GET    /api/workspace/search                # FTS5-поиск (промты + файлы)
```

---

### ══════════════ ФАЗА 2: UI — Detail Panel (Swift) ══════════════

#### 2.1 Компонент: `ProjectDetailPanel.swift`

```swift
struct ProjectDetailPanel: View {
    let project: ProjectInfo
    
    @State private var selectedTab: DetailTab = .overview
    
    enum DetailTab: String, CaseIterable {
        case overview = "Обзор"
        case files = "Файлы"
        case sessions = "Сессии"
        case hooks = "Хуки и плагины"
        case settings = "Настройки"
    }
    
    var body: some View {
        VStack {
            // Табы
            Picker("", selection: $selectedTab) { ... }
            
            // Содержимое вкладки
            switch selectedTab {
            case .overview:  OverviewTab(project: project)
            case .files:     FileTreeTab(scopeType: "project", scopeId: project.id)
            case .sessions:  ProjectSessionsTab(project: project)
            case .hooks:     HooksTab(scopeType: "project", scopeId: project.id)
            case .settings:  ProjectSettingsTab(project: project)
            }
        }
    }
}
```

**Вкладки:**
- **Обзор:** название, описание, статус, теги, даты, кнопка «Открыть в Finder» (`open -R`)
- **Файлы:** дерево `WorkspaceFileTree` (lazy load поддиректорий), drag-and-drop, кнопка «Добавить файл»
- **Сессии:** список сессий проекта с переходами
- **Хуки и плагины:** подключённые хуки (с пометкой «унаследовано»), кнопка «Подключить плагин», лог запусков
- **Настройки:** переименовать, переместить, архивировать, экспортировать

#### 2.2 Компонент: `WorkspaceFileTree.swift`

```swift
struct WorkspaceFileTree: View {
    let scopeType: String  // "section" | "project" | "session"
    let scopeId: String
    
    @State private var rootNode: FileTreeNode?
    @State private var expandedPaths: Set<String> = []
    
    var body: some View {
        // Lazy-load дерево файлов из API
        // Иконки по типу (pdf/docx/image/code/...)
        // Размер, дата изменения
        // Превью для текстовых/markdown
        // Drag-and-drop область
    }
}
```

#### 2.3 Компонент: `HooksTab.swift`

```swift
struct HooksTab: View {
    let scopeType: String
    let scopeId: String
    
    @State private var hooks: [WorkspaceHook] = []
    @State private var showPluginCatalog = false
    
    var body: some View {
        List {
            // Подключённые хуки
            ForEach(hooks) { hook in
                HookRow(hook: hook)
            }
            
            // Унаследованные хуки (от родительского раздела/проекта)
            Section("Унаследовано") {
                ForEach(inheritedHooks) { hook in
                    HookRow(hook: hook, isInherited: true)
                }
            }
        }
        .toolbar {
            Button("Подключить плагин") { showPluginCatalog = true }
        }
        .sheet(isPresented: $showPluginCatalog) {
            PluginCatalogView(scopeType: scopeType, scopeId: scopeId)
        }
    }
}
```

#### 2.4 Модальное окно: `NewSessionModal.swift` (доработка)

Существующий `NewSessionProjectSheet.swift` — заменить/расширить:
- **Обязательное** модальное окно (нельзя пропустить)
- Два варианта:
  1. «Привязать к проекту» → выпадающий список (Раздел → Проект, с поиском)
  2. «Без проекта» — кнопка по умолчанию (сразу доступна)

---

### ══════════════ ФАЗА 3: Интеграция хуков (БД + UI) ══════════════

#### 3.1 Перенос существующих хуков в БД

Существующий `hooks.py` работает с JSON-файлами. Нужно добавить БД-слой:
- При запуске: миграция JSON-хуков → таблицы `workspace_hooks`
- Дальше: БД — primary source для хуков, JSON — fallback

#### 3.2 Каталог плагинов (Builtin)

Стартовый набор builtin-плагинов:

| Плагин | Событие | Действие |
|--------|---------|----------|
| **Auto-Summary** | `on_session_closed` / `SessionEnd` | Авторезюме в `session.meta.json` + `session_summaries` |
| **Export-to-PDF** | ручной запуск | Экспорт транскрипта в PDF |
| **Export-to-DOCX** | ручной запуск | Экспорт транскрипта в DOCX |
| **Archive-to-ZIP** | `on_project_archived` | Архивация папки проекта |
| **Webhook-Notifier** | `on_session_created` / `on_session_closed` | HTTP POST во внешнюю систему |
| **Auto-Tag** | `on_message_sent` | Автотегирование по содержимому промтов |

#### 3.3 Добавление поля `inherit` в хуки

В существующих хуках нет поля `inherit`. Добавить:
- `ALTER TABLE workspace_hooks ADD COLUMN inherit INTEGER DEFAULT 0`
- В UI: чекбокс «Применить ко всем дочерним объектам»
- При создании сессии в проекте: проверять хуки с `inherit=1` у родительского проекта и раздела

#### 3.4 Retry-механизм для хуков

```python
async def run_hook_with_retry(hook, ctx, max_retries=3):
    """Запуск хука с экспоненциальной задержкой."""
    for attempt in range(max_retries):
        result = await run_hook(hook, ctx)
        if result.status != 'error':
            return result
        await asyncio.sleep(2 ** attempt)
    return result  # последняя ошибка
```

---

### ══════════════ ФАЗА 4: Переносимость и экспорт ══════════════

#### 4.1 Экспорт проекта

```python
# backend/workspace_fs.py
def export_project(project_id: str, output_path: str = None) -> str:
    """
    Архивация папки проекта в ZIP.
    - Включает project.meta.json, sessions/, shared_files/, prompts_library/, exports/
    - Исключает временные файлы (.DS_Store, __pycache__)
    - Возвращает путь к ZIP-файлу
    """
```

#### 4.2 Импорт проекта

```python
def import_project(zip_path: str, target_section_id: str = None) -> dict:
    """
    Распаковка ZIP → создание папки проекта → регистрация в БД.
    - Проверка schema_version в project.meta.json
    - Генерация нового id при конфликте
    - Автоматическая регистрация в БД новой оболочки
    """
```

#### 4.3 Пересборка индекса из ФС

```python
async def rebuild_index_from_disk(workspace_root: str) -> RebuildReport:
    """
    Полный обход /Workspace/ → восстановление всех записей в БД
    - Читает section.meta.json, project.meta.json, session.meta.json
    - Сканирует files/, prompts_library/, plugins/
    - Обновляет FTS5-индексы
    - Возвращает отчёт: найдено разделов, проектов, сессий, файлов
    """
```

---

### ══════════════ ФАЗА 5: Дополнительные улучшения ══════════════

#### 5.1 Глобальный поиск (FTS5)

```sql
-- Единая FTS5-таблица для поиска по промтам и файлам
CREATE VIRTUAL TABLE workspace_search USING fts5(
    source_type,    -- 'prompt' / 'file' / 'transcript'
    source_id,
    project_id,
    title,
    content,
    content_rowid='rowid'
);
```

#### 5.2 Конфликты имён

При создании проекта с существующим slug → авто-суффикс `-2`, `-3`...

```python
def generate_unique_slug(base_slug: str, section_id: str) -> str:
    existing = get_existing_slugs(section_id)
    if base_slug not in existing:
        return base_slug
    i = 2
    while f"{base_slug}-{i}" in existing:
        i += 1
    return f"{base_slug}-{i}"
```

#### 5.3 Архивация проектов

- Статус `archived` → скрыть в интерфейсе
- Опционально: физическая архивация в `.zip`, ссылка на архив в БД
- Кнопка «Разархивировать» → распаковка + восстановление в интерфейсе

#### 5.4 Версионирование схемы

```json
// project.meta.json
{
    "schema_version": 2,
    "id": "...",
    "slug": "...",
    "name": "...",
    ...
}
```

Миграции при изменении структуры:
```python
MIGRATIONS = {
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
}
```

---

## Приоритеты и оценки трудозатрат

| Фаза | Компонент | Сложность | Часов | Приоритет |
|------|-----------|-----------|-------|-----------|
| **0** | Миграция существующих данных | 🟡 Средняя | 4-6 | P0 |
| **1.1** | Новая схема БД (ALTER + CREATE) | 🟢 Низкая | 2-3 | P0 |
| **1.2** | `workspace_fs.py` (ФС-операции) | 🟡 Средняя | 6-8 | P0 |
| **1.3** | `workspace_scanner.py` (вотчер) | 🟡 Средняя | 4-6 | P0 |
| **1.4** | `workspace_api.py` (API-роуты) | 🟡 Средняя | 5-7 | P0 |
| **2.1** | `ProjectDetailPanel.swift` | 🔴 Высокая | 8-10 | P1 |
| **2.2** | `WorkspaceFileTree.swift` | 🔴 Высокая | 6-8 | P1 |
| **2.3** | `HooksTab.swift` | 🟡 Средняя | 4-6 | P1 |
| **2.4** | `NewSessionModal.swift` (доработка) | 🟢 Низкая | 2-3 | P1 |
| **3.1** | Миграция хуков в БД | 🟡 Средняя | 3-4 | P2 |
| **3.2** | Builtin-плагины (6 шт.) | 🟡 Средняя | 6-8 | P2 |
| **3.3** | Поле `inherit` для хуков | 🟢 Низкая | 1-2 | P2 |
| **3.4** | Retry-механизм | 🟢 Низкая | 2-3 | P2 |
| **4.1** | Экспорт/Импорт проекта | 🟡 Средняя | 3-4 | P2 |
| **4.2** | Пересборка индекса из ФС | 🟡 Средняя | 3-4 | P2 |
| **5.1** | FTS5 глобальный поиск | 🟡 Средняя | 3-4 | P3 |
| **5.2** | Конфликты имён | 🟢 Низкая | 1-2 | P3 |
| **5.3** | Архивация проектов | 🟢 Низкая | 2-3 | P3 |
| **5.4** | Версионирование схемы | 🟢 Низкая | 1-2 | P3 |

**Итого:** ~65-88 часов (~8-11 рабочих дней)

---

## Что НЕ трогаем (работает и так)

1. ❌ **hooks.py** — существующая система хуков (34 события, 4 типа) остаётся. Добавляем БД-слой **поверх**, не заменяя.

2. ❌ **term_store.py / TermStore** — существующее хранилище терминальных сессий. Оно для другого use-case (терминал), не трогаем.

3. ❌ **messages + FTS5** — полнотекстовый поиск сообщений уже есть.

4. ❌ **project_memory, project_snapshots, project_events, project_dependencies** — существующие таблицы остаются.

5. ❌ **session_summaries, session_contracts, session_collaborators, session_intents** — существуют и работают.

6. ❌ **SwiftUI ChatView, TabManager, FolderStore** — основной UI чата не меняется, добавляем Detail Panel **рядом**.

---

## Ключевые архитектурные решения

### 1. ФС — источник истины, БД — индекс

Это **главный принцип** всей архитектуры. Никакие данные не могут существовать ТОЛЬКО в БД. Всё дублируется на диске.

**Порядок операций:** ФС → БД (не наоборот).

### 2. Desktop-first: macOS — прямой доступ к ФС

TermitPro — macOS `.app` (SwiftUI + FastAPI backend), поэтому:
- `open -R` работает напрямую через `NSWorkspace`
- `FSEvents` (вотчер) — нативный, не нужен `watchdog`
- Файловый диалог — нативный `NSOpenPanel`

**НЕ нужен** локальный компаньон-процесс (п. 4.2 спецификации) — мы desktop, а не веб.

### 3. Обратная совместимость

Старая структура `<Project>/.termit/` **НЕ удаляется**. Новый Workspace создаётся рядом. Миграция — одноразовый скрипт, который **копирует** данные (не перемещает).

### 4. Постепенное внедрение

Каждая фаза даёт **самодостаточный результат**, который можно деплоить независимо:
- Фаза 0+1: серверный API работает, curl-тесты проходят
- Фаза 2: UI в Swift готов, можно тыкать
- Фаза 3: хуки в UI + БД
- Фаза 4: переносимость
- Фаза 5: улучшения

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Большой объём Swift-кода (Detail Panel) | Высокая | Задержка фазы 2 | Сначала веб-UI (Next.js) как прототип, потом Swift |
| Миграция 158 сессий может быть медленной | Средняя | Долгий первый запуск | Фоновая миграция, индикатор прогресса |
| Конфликты с существующими хуками | Низкая | Поломка автосуммаризации | Новые таблицы `workspace_hooks` отдельно от JSON-хуков |
| Файловый вотчер на macOS — ложные срабатывания | Средняя | Лишние перестроения индекса | Debounce 2с, проверка хеша перед обновлением |

---

## Итог

Текущая архитектура TermitPro **уже имеет ~60%** от спецификации:
- ✅ SQLite с богатой схемой (sections, projects, sessions, messages, project_*, session_*)
- ✅ Система хуков (34 события, 4 типа, matcher, блокировка)
- ✅ Экспорт/Импорт проектов
- ✅ FTS5-поиск по сообщениям
- ✅ SwiftUI сайдбар с разделами и папками

**Главный разрыв — ФС-слой:**
- Нет физических папок с `*.meta.json`
- Нет переносимости (копирование папки)
- Нет UI для Detail Panel (Файлы, Хуки, Настройки)
- Нет файлового вотчера

План из 5 фаз закрывает все разрывы за ~8-11 дней.
