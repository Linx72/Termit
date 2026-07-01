from __future__ import annotations

TOOL_DEFINITIONS: dict[str, dict[str, object]] = {
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (absolute or relative)."},
                    "pattern": {"type": "string", "description": "Glob pattern, default *."},
                },
                "required": ["path"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory containing the file."},
                    "file": {"type": "string", "description": "File name or relative path."},
                },
                "required": ["path", "file"],
            },
        },
    },
    "execute_command": {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "path": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["command"],
            },
        },
    },
    "apply_patch": {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a file patch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "hunks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_text": {"type": "string"},
                                "new_text": {"type": "string"},
                            },
                            "required": ["old_text", "new_text"],
                        },
                    },
                    "create": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["path"],
            },
        },
    },
    "web_automation": {
        "type": "function",
        "function": {
            "name": "web_automation",
            "description": "Fetch web page evidence for an online objective.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "objective": {"type": "string"},
                    "max_steps": {"type": "integer"},
                },
                "required": ["url", "objective"],
            },
        },
    },
    "browser_navigate": {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": (
                "Перейти по URL в headless-браузере. "
                "Перед первым переходом на новый домен система спросит разрешение "
                "(один раз — запоминает навсегда). "
                "Возвращает состояние страницы: title, url, интерактивные элементы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Полный URL для перехода (https://...).",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Таймаут загрузки страницы в секундах (по умолчанию 30).",
                    },
                    "wait_until": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "networkidle"],
                        "description": "Когда считать страницу загруженной (по умолчанию domcontentloaded).",
                    },
                },
                "required": ["url"],
            },
        },
    },
    "browser_get_page_state": {
        "type": "function",
        "function": {
            "name": "browser_get_page_state",
            "description": (
                "Получить текущее состояние страницы: title, url, текст, "
                "список интерактивных элементов (кнопки, ссылки, поля ввода) "
                "с их селекторами и типами. Используй перед click/fill чтобы "
                "понять структуру страницы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "include_html": {
                        "type": "boolean",
                        "description": "Включить полный HTML страницы (может быть большим).",
                    },
                    "max_elements": {
                        "type": "integer",
                        "description": "Макс. число интерактивных элементов (по умолчанию 50).",
                    },
                },
            },
        },
    },
    "browser_click": {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": (
                "Кликнуть по элементу на странице по CSS-селектору или тексту. "
                "Для чувствительных действий (купить, оплатить, удалить) "
                "требуется confirmed=true. "
                "Совет: сначала вызови browser_get_page_state чтобы найти "
                "нужный селектор."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS-селектор элемента (например, '#login-btn', 'button.submit').",
                    },
                    "text": {
                        "type": "string",
                        "description": "Альтернатива: текст элемента для поиска (например, 'Войти', 'Submit').",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Индекс элемента из browser_get_page_state (начинается с 0).",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "Подтверждение для чувствительных действий (покупка, оплата, удаление).",
                    },
                },
            },
        },
    },
    "browser_fill": {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": (
                "Заполнить поле ввода (input, textarea, select) на странице. "
                "Совет: сначала вызови browser_get_page_state чтобы найти "
                "нужное поле."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS-селектор поля ввода.",
                    },
                    "value": {
                        "type": "string",
                        "description": "Текст для ввода.",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Индекс элемента из browser_get_page_state.",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "Очистить поле перед вводом (по умолчанию true).",
                    },
                },
                "required": ["value"],
            },
        },
    },
    "browser_get_text": {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": (
                "Извлечь текст элемента или всей страницы. "
                "Полезно после smart_search для извлечения карточек товаров."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS-селектор элемента. Если не указан — весь текст страницы.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Максимальное число символов (по умолчанию 10000).",
                    },
                },
            },
        },
    },
    "browser_screenshot": {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": (
                "Сделать скриншот текущей страницы (или элемента). "
                "Сохраняется в Media Studio как ассет."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS-селектор элемента для скриншота (опционально, иначе вся страница).",
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "Скриншот всей страницы со скроллом (по умолчанию false).",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "ID проекта для сохранения в Media Studio.",
                    },
                },
            },
        },
    },
    "browser_evaluate_js": {
        "type": "function",
        "function": {
            "name": "browser_evaluate_js",
            "description": (
                "Выполнить JavaScript на странице и получить результат. "
                "Используй для: извлечения данных из JSON в window.*, "
                "прокрутки, изменения DOM."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "JavaScript-выражение для выполнения.",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    "browser_wait_for": {
        "type": "function",
        "function": {
            "name": "browser_wait_for",
            "description": (
                "Подождать появления/исчезновения элемента или заданное время. "
                "Полезно после кликов по кнопкам, которые загружают контент асинхронно."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS-селектор элемента, которого ждём.",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["visible", "hidden", "attached", "detached"],
                        "description": "Какое состояние ждать (по умолчанию visible).",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Максимальное время ожидания (по умолчанию 10).",
                    },
                },
            },
        },
    },
    "browser_smart_login": {
        "type": "function",
        "function": {
            "name": "browser_smart_login",
            "description": (
                "Умный логин: автоматически находит форму входа на странице "
                "(поле пароля + соседние поля + кнопка submit), заполняет "
                "учётные данные и отправляет форму. "
                "Работает на ЛЮБОМ сайте без предварительного знания его структуры. "
                "Кэширует найденные селекторы для повторных заходов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL страницы входа (если ещё не перешли).",
                    },
                    "username": {
                        "type": "string",
                        "description": "Логин или email.",
                    },
                    "password": {
                        "type": "string",
                        "description": "Пароль.",
                    },
                    "extra_fields": {
                        "type": "object",
                        "description": (
                            "Дополнительные поля формы, если эвристика не справилась. "
                            "Ключ — название поля (placeholder/label), значение — текст."
                        ),
                    },
                    "submit_text": {
                        "type": "string",
                        "description": (
                            "Текст на кнопке входа, если эвристика не нашла "
                            "(например 'Sign in', 'Log in')."
                        ),
                    },
                },
                "required": ["username", "password"],
            },
        },
    },
    "browser_smart_search": {
        "type": "function",
        "function": {
            "name": "browser_smart_search",
            "description": (
                "Умный поиск: автоматически находит поле поиска на странице "
                "(по placeholder, aria-label, иконке лупы), вводит запрос, "
                "отправляет и извлекает результаты (карточки товаров/статей). "
                "Работает на ЛЮБОМ сайте без знания его структуры."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос.",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL страницы с поиском (если ещё не перешли).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Макс. число результатов (по умолчанию 10).",
                    },
                    "extract_cards": {
                        "type": "boolean",
                        "description": (
                            "Извлечь текст карточек товаров (по умолчанию true). "
                            "False — вернуть только заголовки."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    "browser_smart_add_to_cart": {
        "type": "function",
        "function": {
            "name": "browser_smart_add_to_cart",
            "description": (
                "Умное добавление в корзину: находит кнопку «добавить в корзину» "
                "по тексту на 6+ языках, проверяет что действие не чувствительное "
                "(не «купить сразу»), и кликает. "
                "Требует confirmed=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Название товара для поиска в результатах.",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "Обязательное подтверждение (true).",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Количество (если есть выбор).",
                    },
                },
                "required": ["confirmed"],
            },
        },
    },
    "browser_allowed_domains": {
        "type": "function",
        "function": {
            "name": "browser_allowed_domains",
            "description": (
                "Управление списком разрешённых доменов: добавить, удалить, показать. "
                "Домены из списка не требуют подтверждения при первом заходе."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "add": {
                        "type": "string",
                        "description": "Домен для добавления в разрешённые (например, 'amazon.com').",
                    },
                    "remove": {
                        "type": "string",
                        "description": "Домен для удаления из разрешённых.",
                    },
                    "list": {
                        "type": "boolean",
                        "description": "Показать все разрешённые домены.",
                    },
                },
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return structured ranked results with citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional domain allow-list filter.",
                    },
                    "recency_days": {
                        "type": "integer",
                        "description": "Optional recency window in days.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "spawn_agent": {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": "Spawn a child agent run and return its summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["task"],
            },
        },
    },
    "mcp_invoke": {
        "type": "function",
        "function": {
            "name": "mcp_invoke",
            "description": "Invoke a tool on a registered MCP server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server_id", "tool_name"],
            },
        },
    },
    "mcp_read_resource": {
        "type": "function",
        "function": {
            "name": "mcp_read_resource",
            "description": "Read an MCP resource URI from a registered server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "uri": {"type": "string"},
                },
                "required": ["server_id", "uri"],
            },
        },
    },
    "mcp_get_prompt": {
        "type": "function",
        "function": {
            "name": "mcp_get_prompt",
            "description": "Fetch a named MCP prompt template from a registered server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server_id": {"type": "string"},
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server_id", "name"],
            },
        },
    },
    "generate_image": {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate PNG image from prompt; saves to Media Studio asset store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "project_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "provider": {
                        "type": "string",
                        "description": "openai, comfy (local SDXL via ComfyUI), sdxl (alias comfy), or stub",
                    },
                    "confirmed": {"type": "boolean"},
                },
                "required": ["prompt"],
            },
        },
    },
    "list_media_assets": {
        "type": "function",
        "function": {
            "name": "list_media_assets",
            "description": "List media assets for project or run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    "vision_qa_media": {
        "type": "function",
        "function": {
            "name": "vision_qa_media",
            "description": "Score image asset against criteria (heuristic or vision).",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "criteria": {"type": "string"},
                    "min_score": {"type": "number"},
                },
                "required": ["asset_id"],
            },
        },
    },
    "estimate_media_cost": {
        "type": "function",
        "function": {
            "name": "estimate_media_cost",
            "description": "Estimate USD cost from storyboard JSON or path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "storyboard_path": {"type": "string"},
                    "storyboard": {"type": "object"},
                },
            },
        },
    },
    "tts_generate": {
        "type": "function",
        "function": {
            "name": "tts_generate",
            "description": "Generate voiceover WAV from text (OpenAI TTS or stub).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "voice_id": {"type": "string"},
                    "language": {"type": "string"},
                    "project_id": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["text"],
            },
        },
    },
    "transcribe_media": {
        "type": "function",
        "function": {
            "name": "transcribe_media",
            "description": "Transcribe audio/video asset to SRT via Whisper.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string"},
                    "language": {"type": "string"},
                    "project_id": {"type": "string"},
                },
                "required": ["asset_id"],
            },
        },
    },
    "compose_media": {
        "type": "function",
        "function": {
            "name": "compose_media",
            "description": "Build MP4 slideshow from timeline (image clips, optional audio/subs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeline_path": {"type": "string"},
                    "timeline": {"type": "object"},
                    "project_id": {"type": "string"},
                    "output_name": {"type": "string"},
                    "preset": {"type": "string", "description": "youtube_16x9|reels_9x16|telegram_1x1"},
                },
            },
        },
    },
    "render_video": {
        "type": "function",
        "function": {
            "name": "render_video",
            "description": "Start I2V render job from source image asset; returns job_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "source_asset_id": {"type": "string"},
                    "scene_id": {"type": "string"},
                    "duration_sec": {"type": "number"},
                    "mode": {"type": "string"},
                    "provider": {"type": "string"},
                    "project_id": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["prompt", "source_asset_id"],
            },
        },
    },
    "wait_media_job": {
        "type": "function",
        "function": {
            "name": "wait_media_job",
            "description": "Poll media job until terminal state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "timeout_sec": {"type": "integer"},
                },
                "required": ["job_id"],
            },
        },
    },
    "export_gif": {
        "type": "function",
        "function": {
            "name": "export_gif",
            "description": "Export animated GIF from PNG asset_ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_ids": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": "string"},
                    "fps": {"type": "integer"},
                    "width": {"type": "integer"},
                },
                "required": ["asset_ids"],
            },
        },
    },
    "export_lottie": {
        "type": "function",
        "function": {
            "name": "export_lottie",
            "description": "Export Lottie JSON animation from PNG asset_ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_ids": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": "string"},
                    "fps": {"type": "integer"},
                    "width": {"type": "integer"},
                },
                "required": ["asset_ids"],
            },
        },
    },
    "run_storyboard": {
        "type": "function",
        "function": {
            "name": "run_storyboard",
            "description": "Studio pipeline: storyboard scenes → images/I2V → master MP4.",
            "parameters": {
                "type": "object",
                "properties": {
                    "storyboard_path": {"type": "string"},
                    "storyboard": {"type": "object"},
                    "brand_kit_id": {"type": "string"},
                    "project_id": {"type": "string"},
                    "max_scenes": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
            },
        },
    },
    "describe_tools": {
        "type": "function",
        "function": {
            "name": "describe_tools",
            "description": (
                "Load full JSON schemas for deferred tools before calling them. "
                "Use when you need apply_patch, execute_command, media, MCP, or other lazy tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tool names from the agent allowlist.",
                    }
                },
                "required": ["tool_names"],
            },
        },
    },
    "invoke_skill": {
        "type": "function",
        "function": {
            "name": "invoke_skill",
            "description": (
                "Load full instructions for a Termit agent skill by skill_id. "
                "Use when task matches an available skill or user references a slash skill."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "description": "Skill folder id, e.g. fix-ci, write-tests, media-studio.",
                    }
                },
                "required": ["skill_id"],
            },
        },
    },
}


# Группы для lazy tool schemas (ось B harness): старт с core, расширение по heuristics/usage.
TOOL_TIER_CORE = frozenset({"list_files", "read_file", "describe_tools", "invoke_skill"})
TOOL_TIER_MUTATE = frozenset({"apply_patch", "execute_command", "browser_click"})
TOOL_TIER_BROWSER = frozenset({
    "browser_navigate",
    "browser_get_page_state",
    "browser_click",
    "browser_fill",
    "browser_get_text",
    "browser_screenshot",
    "browser_evaluate_js",
    "browser_wait_for",
    "browser_smart_login",
    "browser_smart_search",
    "browser_smart_add_to_cart",
    "browser_allowed_domains",
    "web_automation",
})
TOOL_TIER_ONLINE = frozenset({"web_search"})
TOOL_TIER_MCP = frozenset({"mcp_invoke", "mcp_read_resource", "mcp_get_prompt"})
TOOL_TIER_AGENT = frozenset({"spawn_agent"})
TOOL_TIER_MEDIA = frozenset(
    {
        "generate_image",
        "list_media_assets",
        "vision_qa_media",
        "estimate_media_cost",
        "tts_generate",
        "transcribe_media",
        "compose_media",
        "render_video",
        "wait_media_job",
        "export_gif",
        "export_lottie",
        "run_storyboard",
    }
)

_FILE_WRITE_MARKERS = (
    "create file",
    "write file",
    "edit file",
    "modify file",
    "update file",
    "delete file",
    "apply patch",
    "apply_patch",
    "создай файл",
    "измени файл",
    "правк",
    "patch",
    "refactor",
    "implement",
    "fix bug",
    "add test",
)

_ONLINE_MARKERS = (
    "search web",
    "google",
    "internet",
    "online",
    "browser",
    "website",
    "найди в интернете",
    "поиск",
    "стать",
)

_MEDIA_MARKERS = (
    "image",
    "video",
    "storyboard",
    "lottie",
    "gif",
    "tts",
    "media",
    "изображен",
    "видео",
    "анимац",
)


def _enabled_set(enabled_tools: list[str]) -> set[str]:
    return {name.strip() for name in enabled_tools if name and name.strip()}


def select_initial_tool_names(
    enabled_tools: list[str],
    task_message: str,
    *,
    run_mode: str = "agent",
    verify_after_patch: bool = False,
) -> list[str]:
    """Минимальный набор native tool schemas для первого шага agent loop."""
    enabled = _enabled_set(enabled_tools)
    active = set(TOOL_TIER_CORE & enabled)
    msg = task_message.lower()
    plan_only = run_mode.strip().lower() == "plan"

    if not plan_only and any(marker in msg for marker in _FILE_WRITE_MARKERS):
        active |= TOOL_TIER_MUTATE & enabled
    if not plan_only and (
        verify_after_patch
        or "test" in msg
        or "pytest" in msg
        or "npm" in msg
        or "lint" in msg
        or "verify" in msg
    ):
        if "execute_command" in enabled:
            active.add("execute_command")
    if any(marker in msg for marker in _ONLINE_MARKERS):
        active |= (TOOL_TIER_ONLINE | TOOL_TIER_BROWSER) & enabled
    if any(marker in msg for marker in _MEDIA_MARKERS):
        active |= TOOL_TIER_MEDIA & enabled
    if "mcp" in msg or "mcp_invoke" in enabled:
        active |= TOOL_TIER_MCP & enabled
    if "spawn" in msg or "subagent" in msg or "parallel" in msg:
        active |= TOOL_TIER_AGENT & enabled

    if not active:
        active = set(enabled)
    return sorted(active)


def expand_tools_after_use(
    used_tool: str,
    enabled_tools: list[str],
    current_active: set[str],
    *,
    describe_request: list[str] | None = None,
) -> set[str]:
    """Расширить lazy schema после tool call или describe_tools."""
    enabled = _enabled_set(enabled_tools)
    expanded = set(current_active)
    if describe_request:
        for name in describe_request:
            if name in enabled:
                expanded.add(name)
        if "mcp_invoke" in expanded:
            expanded |= TOOL_TIER_MCP & enabled
    if used_tool in TOOL_TIER_CORE:
        expanded |= TOOL_TIER_MUTATE & enabled
    if used_tool in {"apply_patch", "execute_command"}:
        if "execute_command" in enabled:
            expanded.add("execute_command")
        if "apply_patch" in enabled:
            expanded.add("apply_patch")
    if used_tool in TOOL_TIER_BROWSER:
        expanded |= TOOL_TIER_BROWSER & enabled
    if used_tool in TOOL_TIER_MCP:
        expanded |= TOOL_TIER_MCP & enabled
    if used_tool in TOOL_TIER_MEDIA:
        expanded |= TOOL_TIER_MEDIA & enabled
    return expanded


def resolve_described_tools(arguments: dict[str, object], enabled_tools: list[str]) -> list[str]:
    """Извлечь и отфильтровать tool_names из describe_tools arguments."""
    enabled = _enabled_set(enabled_tools)
    raw = arguments.get("tool_names", [])
    if not isinstance(raw, list):
        return []
    return [str(name).strip() for name in raw if str(name).strip() in enabled]


def build_tool_schema_response(tool_names: list[str]) -> str:
    """JSON observation для describe_tools."""
    import json

    schemas = build_openai_tools(tool_names)
    return json.dumps(
        {
            "loaded_tools": tool_names,
            "schemas": schemas,
            "hint": "Schemas are now active for native tool calling on next steps.",
        },
        ensure_ascii=True,
    )


def deferred_tool_catalog(enabled_tools: list[str], active_tools: set[str]) -> str:
    """Краткий список отложенных tools для system prompt (native loop)."""
    enabled = _enabled_set(enabled_tools)
    deferred = sorted(name for name in enabled if name not in active_tools and name in TOOL_DEFINITIONS)
    if not deferred:
        return ""
    return (
        "\n\n[Lazy tools] Schemas for these tools load on demand after exploration: "
        + ", ".join(deferred)
    )


def build_openai_tools(enabled_tools: list[str]) -> list[dict[str, object]]:
    names = list(enabled_tools)
    if "mcp_invoke" in names:
        for companion in ("mcp_read_resource", "mcp_get_prompt"):
            if companion not in names:
                names.append(companion)
    tools: list[dict[str, object]] = []
    for name in names:
        spec = TOOL_DEFINITIONS.get(name)
        if spec is not None:
            tools.append(spec)
    return tools
