"""
browser_tool.py — инструмент полноценного управления браузером для termitpro.
Работает на ЛЮБОМ сайте: универсальные эвристики (Слой A) + самообучающийся
кэш селекторов по доменам (Слой B), без site-specific кода под конкретные
магазины.

Зависимости:
    pip install playwright
    playwright install chromium

Архитектура:
    BrowserSession   — persistent контекст браузера на одну сессию диалога.
    AllowedDomains   — список разрешённых доменов с политикой
                        "спроси один раз — запомни".
    SiteProfiles     — кэш найденных селекторов по доменам (учится сам).
    TOOL_SCHEMAS     — JSON-схемы для function calling.
    dispatch_tool_call() — точка входа для вызовов от LLM.

Этот файл — стартовый скелет, не финальная реализация. Перед продакшеном:
    - расширить ADD_TO_CART_PHRASES/SEARCH_FIELD_HINTS под нужные языки,
    - подключить реальный механизм подтверждения у пользователя
      (сейчас это просто возврат статуса "needs_confirmation"),
    - решить, как подаются логин/пароль (см. README в промте).
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


# ---------------------------------------------------------------------------
# Конфиг безопасности.
# ---------------------------------------------------------------------------

ALLOWED_DOMAINS_PATH = Path("./allowed_domains.json")

# Многоязычный словарь ключевых фраз для универсальных эвристик (раздел 3.5
# промта). Расширяй под нужные языки/сайты — это конфиг, не код.
ADD_TO_CART_PHRASES = [
    "в корзину", "купить", "add to cart", "add to bag", "buy now",
    "в кошик", "agregar al carrito", "in den warenkorb", "ajouter au panier",
]
SEARCH_FIELD_HINTS = ["search", "поиск", "найти", "искать", "buscar", "suche"]

# Действия, текст которых требует явного подтверждения пользователя перед
# кликом (финальная оплата/удаление — отличается от просто "добавить в корзину").
SENSITIVE_ACTION_KEYWORDS = (
    "купить", "оплатить", "подтвердить заказ", "оформить заказ",
    "удалить", "buy now", "checkout", "place order", "pay", "delete",
)

MAX_STEPS_PER_REQUEST = 15
STORAGE_STATE_PATH = Path("./auth_state.json")
SITE_PROFILES_PATH = Path("./site_profiles.json")
PAGE_TEXT_MAX_CHARS = 8000  # чтобы не раздувать контекст модели


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class DomainNotAllowedError(Exception):
    """Домен ещё не подтверждён пользователем — требуется needs_confirmation."""


class StepLimitExceededError(Exception):
    pass


class SiteAlreadyActiveError(Exception):
    """На этот домен уже есть активный браузерный контекст в этом процессе."""


# Реестр доменов с активным BrowserSession в рамках текущего процесса termitpro —
# не даёт случайно открыть второй параллельный логин на тот же сайт.
_active_domains: set[str] = set()


@dataclass
class AllowedDomains:
    """
    Персистентный список разрешённых доменов с политикой "спроси один раз —
    запомни" (раздел 3 промта), вместо статичного allowlist под один сайт.
    """

    path: Path = ALLOWED_DOMAINS_PATH

    def _read(self) -> set[str]:
        return set(_load_json(self.path, []))

    def is_allowed(self, url: str) -> bool:
        host = urlparse(url).hostname or ""
        return host in self._read()

    def approve(self, url: str) -> None:
        host = urlparse(url).hostname or ""
        domains = self._read()
        domains.add(host)
        _save_json(self.path, sorted(domains))


@dataclass
class SiteProfiles:
    """
    Слой B универсальной архитектуры: кэш селекторов, которые сработали для
    конкретного домена. При первом визите на домен — пусто, используются
    эвристики Слоя A; найденное сохраняется сюда и переиспользуется при
    следующих визитах без повторного перебора.
    """

    path: Path = SITE_PROFILES_PATH

    def _read(self) -> dict:
        return _load_json(self.path, {})

    def get(self, domain: str) -> dict:
        return self._read().get(domain, {})

    def update(self, domain: str, **fields: Any) -> None:
        profiles = self._read()
        entry = profiles.setdefault(domain, {})
        entry.update(fields)
        entry["last_verified"] = time.strftime("%Y-%m-%d")
        _save_json(self.path, profiles)


@dataclass
class BrowserSession:
    """
    Один объект на сессию диалога termitpro. Не создавай новый BrowserContext
    на каждый вызов тула — иначе логин и состояние страницы будут теряться.
    """

    headless: bool = True
    _playwright: Any = field(default=None, init=False, repr=False)
    _browser: Optional[Browser] = field(default=None, init=False, repr=False)
    _context: Optional[BrowserContext] = field(default=None, init=False, repr=False)
    _page: Optional[Page] = field(default=None, init=False, repr=False)
    _steps_used: int = field(default=0, init=False)
    _last_activity: float = field(default_factory=time.time, init=False)
    allowed_domains: AllowedDomains = field(default_factory=AllowedDomains, init=False)
    site_profiles: SiteProfiles = field(default_factory=SiteProfiles, init=False)
    _claimed_domains: set[str] = field(default_factory=set, init=False)

    # -- lifecycle ----------------------------------------------------------

    async def _ensure_started(self) -> None:
        if self._page is not None:
            self._last_activity = time.time()
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)

        storage_state = str(STORAGE_STATE_PATH) if STORAGE_STATE_PATH.exists() else None
        self._context = await self._browser.new_context(storage_state=storage_state)
        self._page = await self._context.new_page()
        self._last_activity = time.time()

    async def save_auth_state(self) -> None:
        """
        Сохранить cookies/localStorage, чтобы логин пережил перезапуск.
        Atomic write + бэкап предыдущей версии — чтобы падение процесса
        посреди записи не убило рабочую сессию.
        """
        if self._context is None:
            return
        if STORAGE_STATE_PATH.exists():
            STORAGE_STATE_PATH.replace(STORAGE_STATE_PATH.with_suffix(".json.bak"))
        tmp_path = STORAGE_STATE_PATH.with_suffix(".json.tmp")
        await self._context.storage_state(path=str(tmp_path))
        tmp_path.replace(STORAGE_STATE_PATH)

    async def session_is_valid(self, account_url: str) -> bool:
        """
        Проверка, что сохранённая сессия ещё рабочая (например, открыта
        страница аккаунта и виден элемент профиля/выхода), чтобы не
        логиниться заново "на всякий случай" при каждом запуске.
        """
        await self._ensure_started()
        if not self.allowed_domains.is_allowed(account_url):
            return False
        await self._page.goto(account_url, wait_until="domcontentloaded")
        password_field = self._page.locator("input[type='password']")
        # Если на "странице аккаунта" снова просят пароль — сессия не валидна.
        return await password_field.count() == 0

    async def close(self) -> None:
        if self._context is not None:
            await self.save_auth_state()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        _active_domains.difference_update(self._claimed_domains)
        self._claimed_domains.clear()
        self._page = self._context = self._browser = self._playwright = None

    # -- безопасность ---------------------------------------------------

    def _check_step_limit(self) -> None:
        self._steps_used += 1
        if self._steps_used > MAX_STEPS_PER_REQUEST:
            raise StepLimitExceededError(
                f"Превышен лимит действий браузера за запрос ({MAX_STEPS_PER_REQUEST})."
            )

    def _check_domain_allowed(self, url: str) -> None:
        if not self.allowed_domains.is_allowed(url):
            host = urlparse(url).hostname or url
            raise DomainNotAllowedError(
                f"Домен '{host}' открывается впервые и ещё не подтверждён "
                f"пользователем. Нужно спросить разрешение в чате, затем вызвать "
                f"approve_domain('{url}') и повторить навигацию."
            )

    async def _is_sensitive(self, selector: str) -> bool:
        """Грубая проверка: похож ли selector/его текст на чувствительное действие."""
        try:
            text = (await self._page.locator(selector).first.inner_text()).lower()
        except Exception:
            text = selector.lower()
        return any(keyword in text for keyword in SENSITIVE_ACTION_KEYWORDS)

    # -- тулы для LLM ------------------------------------------------------

    async def navigate(self, url: str) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        if not self.allowed_domains.is_allowed(url):
            host = urlparse(url).hostname or url
            return {
                "status": "needs_confirmation",
                "message": (
                    f"Сайт '{host}' открывается впервые. Спроси у пользователя "
                    f"разрешение, затем вызови approve_domain и повтори navigate."
                ),
            }
        await self._page.goto(url, wait_until="domcontentloaded")
        domain = urlparse(self._page.url).hostname or ""
        if domain in _active_domains and domain not in self._claimed_domains:
            return {
                "status": "error",
                "message": (
                    f"На домен '{domain}' уже есть активный контекст в этом "
                    f"процессе — не открываем второй параллельный логин."
                ),
            }
        _active_domains.add(domain)
        self._claimed_domains.add(domain)
        return await self.get_page_state()

    async def approve_domain(self, url: str) -> dict:
        """Вызывается ТОЛЬКО после явного 'да' пользователя в чате на конкретный домен."""
        self.allowed_domains.approve(url)
        return {"status": "ok"}

    async def click(self, selector: str) -> dict:
        self._check_step_limit()
        await self._ensure_started()

        if await self._is_sensitive(selector):
            return {
                "status": "needs_confirmation",
                "message": (
                    f"Клик по '{selector}' похож на чувствительное действие "
                    "(покупка/оплата/удаление). Нужно явное подтверждение "
                    "пользователя в чате перед выполнением."
                ),
            }

        await self._page.locator(selector).first.click()
        return {"status": "ok", **await self.get_page_state()}

    async def confirmed_click(self, selector: str) -> dict:
        """
        Отдельный тул для клика по чувствительным действиям — вызывается
        ТОЛЬКО после того, как пользователь явно подтвердил в чате.
        Логика подтверждения (кто и как подтвердил) живёт в оркестраторе
        termitpro, а не в этом модуле — этот метод просто выполняет клик.
        """
        self._check_step_limit()
        await self._ensure_started()
        await self._page.locator(selector).first.click()
        return {"status": "ok", **await self.get_page_state()}

    async def fill(self, selector: str, value: str) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        await self._page.locator(selector).first.fill(value)
        return {"status": "ok"}

    async def get_text(self, selector: Optional[str] = None) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        if selector:
            text = await self._page.locator(selector).first.inner_text()
        else:
            text = await self._page.inner_text("body")
        return {"text": text[:PAGE_TEXT_MAX_CHARS]}

    async def wait_for(self, selector: str, timeout_ms: int = 5000) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        await self._page.locator(selector).first.wait_for(timeout=timeout_ms)
        return {"status": "ok"}

    async def evaluate_js(self, script: str) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        result = await self._page.evaluate(script)
        return {"result": result}

    async def screenshot(self) -> dict:
        self._check_step_limit()
        await self._ensure_started()
        path = f"./screenshot_{int(time.time())}.png"
        await self._page.screenshot(path=path)
        return {"screenshot_path": path}

    # -- Слой A: универсальные эвристики (работают на любом сайте) --------

    async def _find_login_form(self) -> Optional[dict]:
        """
        Универсальный поиск формы логина: input[type=password] — почти
        100%-но надёжный маркер на любом сайте независимо от языка/вёрстки.
        """
        password = self._page.locator("input[type='password']").first
        if await password.count() == 0:
            return None
        # Поле логина обычно ближайший text/email input перед паролем.
        login_field = self._page.locator(
            "input[type='email'], input[type='text'], input[name*='login' i], "
            "input[name*='user' i], input[name*='email' i]"
        ).first
        submit = self._page.locator(
            "button[type='submit'], input[type='submit']"
        ).first
        return {
            "login_selector": "input[type='email'], input[type='text']",
            "password_selector": "input[type='password']",
            "submit_selector": "button[type='submit'], input[type='submit']",
        } if await login_field.count() and await submit.count() else None

    async def _find_search_field(self) -> Optional[str]:
        candidates = [
            "input[type='search']",
            "input[role='search']",
            *[f"input[aria-label*='{h}' i]" for h in SEARCH_FIELD_HINTS],
            *[f"input[placeholder*='{h}' i]" for h in SEARCH_FIELD_HINTS],
        ]
        for sel in candidates:
            if await self._page.locator(sel).count() > 0:
                return sel
        return None

    async def _find_add_to_cart_button(self) -> Optional[str]:
        for phrase in ADD_TO_CART_PHRASES:
            locator = self._page.get_by_text(phrase, exact=False)
            if await locator.count() > 0:
                # Возвращаем текстовый локатор как "селектор" — Playwright
                # понимает синтаксис text= нативно.
                return f"text={phrase}"
        return None

    # -- Слой B: смарт-тулы (эвристики + кэш профилей сайтов) ------------

    async def smart_login(self, url: str, username: str, password: str) -> dict:
        """
        Работает на произвольном сайте. Логин/пароль должны приходить из
        локального хранилища (.env/keychain), а не от LLM — см. раздел 3
        промта про обращение с кредами.
        """
        self._check_step_limit()
        nav = await self.navigate(url)
        if nav.get("status") == "needs_confirmation":
            return nav

        domain = urlparse(self._page.url).hostname or ""
        cached = self.site_profiles.get(domain)

        form = None
        if cached.get("login_form"):
            form = cached["login_form"]
        else:
            form = await self._find_login_form()
            if form is None:
                return {"status": "error", "message": "Форма логина не найдена эвристиками."}
            self.site_profiles.update(domain, login_form=form)

        await self._page.locator(form["login_selector"]).first.fill(username)
        await self._page.locator(form["password_selector"]).first.fill(password)
        await self._page.locator(form["submit_selector"]).first.click()
        await self._page.wait_for_load_state("domcontentloaded")
        await self.save_auth_state()
        return {"status": "ok", **await self.get_page_state()}

    async def smart_search(self, url: str, query: str) -> dict:
        self._check_step_limit()
        nav = await self.navigate(url)
        if nav.get("status") == "needs_confirmation":
            return nav

        domain = urlparse(self._page.url).hostname or ""
        cached = self.site_profiles.get(domain)
        selector = cached.get("search_input")

        if not selector:
            selector = await self._find_search_field()
            if selector is None:
                return {"status": "error", "message": "Поле поиска не найдено эвристиками."}
            self.site_profiles.update(domain, search_input=selector)

        field = self._page.locator(selector).first
        await field.fill(query)
        await field.press("Enter")
        await self._page.wait_for_load_state("domcontentloaded")
        return {"status": "ok", **await self.get_page_state()}

    async def smart_add_to_cart(self, product_url: str) -> dict:
        self._check_step_limit()
        nav = await self.navigate(product_url)
        if nav.get("status") == "needs_confirmation":
            return nav

        domain = urlparse(self._page.url).hostname or ""
        cached = self.site_profiles.get(domain)
        selector = cached.get("add_to_cart_button")

        if not selector:
            selector = await self._find_add_to_cart_button()
            if selector is None:
                return {"status": "error", "message": "Кнопка 'в корзину' не найдена эвристиками."}

        if await self._is_sensitive(selector):
            return {
                "status": "needs_confirmation",
                "message": f"'{selector}' похоже на финальную покупку, а не просто добавление в корзину.",
            }

        await self._page.locator(selector).first.click()
        self.site_profiles.update(domain, add_to_cart_button=selector)
        return {"status": "ok", **await self.get_page_state()}

    async def get_page_state(self) -> dict:
        """
        Снапшот страницы для модели: URL, заголовок и список видимых
        интерактивных элементов с их selector'ами. Без этого модель
        вынуждена угадывать селекторы для click/fill.
        """
        await self._ensure_started()

        elements = await self._page.evaluate(
            """
            () => {
                const sel = (el) => {
                    if (el.id) return '#' + el.id;
                    if (el.name) return `[name="${el.name}"]`;
                    return el.tagName.toLowerCase();
                };
                const nodes = Array.from(
                    document.querySelectorAll('button, a, input, textarea, select')
                ).filter(el => el.offsetParent !== null);
                return nodes.slice(0, 50).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    selector: sel(el),
                    text: (el.innerText || el.value || el.placeholder || '').slice(0, 80),
                }));
            }
            """
        )

        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "interactive_elements": elements,
        }


# ---------------------------------------------------------------------------
# JSON-схемы для function calling — добавь в общий реестр тулов termitpro.
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "browser_navigate",
        "description": "Открыть URL в браузере. Возвращает снапшот страницы.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "browser_click",
        "description": (
            "Кликнуть по элементу. Если действие похоже на оплату/покупку/удаление, "
            "вернёт needs_confirmation вместо клика — сначала спроси пользователя."
        ),
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "browser_fill",
        "description": "Заполнить поле формы значением.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "browser_get_text",
        "description": "Получить текст страницы или конкретного элемента.",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "browser_wait_for",
        "description": "Подождать появления элемента на странице.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "browser_evaluate_js",
        "description": "Выполнить произвольный JavaScript в контексте страницы.",
        "parameters": {
            "type": "object",
            "properties": {"script": {"type": "string"}},
            "required": ["script"],
        },
    },
    {
        "name": "browser_screenshot",
        "description": "Сделать скриншот текущей страницы.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_get_page_state",
        "description": "Получить URL, заголовок и список видимых интерактивных элементов с selector'ами.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_approve_domain",
        "description": "Подтвердить переход на новый домен. Вызывать ТОЛЬКО после явного 'да' пользователя в чате.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "browser_smart_login",
        "description": (
            "Универсальный логин на ЛЮБОМ сайте: эвристически находит форму логина "
            "(не требует знания конкретного сайта заранее), заполняет и отправляет."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["url", "username", "password"],
        },
    },
    {
        "name": "browser_smart_search",
        "description": "Универсальный поиск на ЛЮБОМ сайте: эвристически находит поле поиска и вводит запрос.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}, "query": {"type": "string"}},
            "required": ["url", "query"],
        },
    },
    {
        "name": "browser_smart_add_to_cart",
        "description": (
            "Универсальное добавление в корзину на ЛЮБОМ сайте: эвристически находит "
            "кнопку 'в корзину' по мультиязычному словарю фраз и кликает."
        ),
        "parameters": {
            "type": "object",
            "properties": {"product_url": {"type": "string"}},
            "required": ["product_url"],
        },
    },
]


# ---------------------------------------------------------------------------
# Диспетчер вызовов от LLM. Подключи в основной tool-loop termitpro.
# ---------------------------------------------------------------------------

async def dispatch_tool_call(session: BrowserSession, name: str, arguments: dict) -> dict:
    handlers = {
        "browser_navigate": lambda: session.navigate(arguments["url"]),
        "browser_click": lambda: session.click(arguments["selector"]),
        "browser_fill": lambda: session.fill(arguments["selector"], arguments["value"]),
        "browser_get_text": lambda: session.get_text(arguments.get("selector")),
        "browser_wait_for": lambda: session.wait_for(
            arguments["selector"], arguments.get("timeout_ms", 5000)
        ),
        "browser_evaluate_js": lambda: session.evaluate_js(arguments["script"]),
        "browser_screenshot": lambda: session.screenshot(),
        "browser_get_page_state": lambda: session.get_page_state(),
        "browser_approve_domain": lambda: session.approve_domain(arguments["url"]),
        "browser_smart_login": lambda: session.smart_login(
            arguments["url"], arguments["username"], arguments["password"]
        ),
        "browser_smart_search": lambda: session.smart_search(
            arguments["url"], arguments["query"]
        ),
        "browser_smart_add_to_cart": lambda: session.smart_add_to_cart(
            arguments["product_url"]
        ),
    }

    handler = handlers.get(name)
    if handler is None:
        return {"status": "error", "message": f"Неизвестный тул: {name}"}

    try:
        return await handler()
    except (DomainNotAllowedError, StepLimitExceededError) as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Пример ручной проверки (замени на pytest при интеграции в CI).
# ---------------------------------------------------------------------------

async def _manual_smoke_test() -> None:
    """Пример: подставь любой URL — эвристики не завязаны на конкретный сайт."""
    session = BrowserSession(headless=False)
    try:
        state = await session.navigate("https://example.com")
        if state.get("status") == "needs_confirmation":
            # В реальном flow здесь нужно подтверждение пользователя в чате.
            await session.approve_domain("https://example.com")
            state = await session.navigate("https://example.com")
        print(json.dumps(state, ensure_ascii=False, indent=2))
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(_manual_smoke_test())
