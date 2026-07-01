"""
Сервис управления браузером через Playwright (sync API).

Слой A — универсальные эвристики (работают на любом сайте без знания о нём заранее):
  - Поиск формы логина: input[type=password] → соседние поля → кнопка submit
  - Поиск поля поиска: input[type=search] / aria-label / иконка лупы
  - Поиск кнопки «в корзину»: сопоставление текста со словарём фраз на разных языках

Слой B — самообучающийся кэш сайтов (site_profiles.json):
  - После успешного нахождения элемента через эвристики — сохраняем селектор
  - При следующем визите — используем кэш
  - Если кэш невалиден — авто-откат на эвристики и обновление кэша

Политика доменов «спроси один раз — запомни»:
  - При первом переходе на домен → запрос подтверждения
  - После подтверждения → сохранение в allowed_domains.json
  - Повторные переходы на разрешённый домен — без подтверждения
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.sync_api import (  # noqa: F401
        Browser,
        BrowserContext,
        Page,
        Playwright,
        sync_playwright,
        TimeoutError as PlaywrightTimeout,
        Error as PlaywrightError,
    )
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

# ── Исключения ─────────────────────────────────────────────────────────────

class PlaywrightUnavailableError(RuntimeError):
    """Playwright недоступен (не установлен или нет браузера)."""


# ── Конфигурация ──────────────────────────────────────────────────────────

# Пути к файлам данных (относительно корня проекта)
ALLOWED_DOMAINS_PATH = "./allowed_domains.json"
STORAGE_STATE_PATH = "./auth_state.json"
SITE_PROFILES_PATH = "./site_profiles.json"

# Ограничения
MAX_STEPS_PER_REQUEST = 15
PAGE_TEXT_MAX_CHARS = 8000
INTERACTIVE_ELEMENTS_MAX = 50
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # секунды

# Словари ключевых фраз для эвристик (расширяемые)
ADD_TO_CART_PHRASES = [
    "в корзину", "купить", "купити", "в кошик", "до кошика",
    "add to cart", "add to bag", "buy now", "buy it now",
    "agregar al carrito", "añadir al carro", "ajouter au panier",
    "in den warenkorb", "aggiungi al carrello", "カートに入れる",
    "加入购物车", "장바구니에 담기",
]
SEARCH_FIELD_HINTS = [
    "search", "поиск", "найти", "buscar", "rechercher", "suche",
    "cerca", "検索", "搜索", "검색",
]
SENSITIVE_ACTION_KEYWORDS = [
    "купить", "оплатить", "подтвердить заказ", "оформить заказ",
    "buy", "pay", "place order", "confirm order", "checkout",
    "удалить", "delete", "remove", "деактивировать",
    "списать", "charge", "отправить", "submit order",
]
LOGIN_SUCCESS_INDICATORS = [
    "выйти", "выход", "log out", "logout", "sign out", "signout",
    "мой профиль", "my profile", "my account", "личный кабинет",
    "мои заказы", "my orders",
]


# ═══════════════════════════════════════════════════════════════════════════
# Вспомогательные утилиты
# ═══════════════════════════════════════════════════════════════════════════

def _atomic_write(fp: str, data: Any) -> None:
    """Атомарная запись: tmp → rename, с бэкапом предыдущей версии."""
    path = Path(fp)
    tmp = path.with_suffix(path.suffix + ".tmp")
    bak = path.with_suffix(path.suffix + ".bak")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            os.replace(str(path), str(bak))
        except OSError:
            pass  # бэкап — best-effort
    os.replace(str(tmp), str(path))


def _load_json(path: str, default: Any = None) -> Any:
    """Загрузить JSON-файл, вернуть default если не существует."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default() if callable(default) else default


def _text_matches_any(text: str, phrases: list[str]) -> bool:
    """Проверить, содержит ли текст любую из фраз (регистронезависимо)."""
    low = text.lower()
    return any(p.lower() in low for p in phrases)


def _extract_interactive_elements(page: "Page") -> list[dict[str, Any]]:
    """Извлечь видимые интерактивные элементы со страницы."""
    elements: list[dict[str, Any]] = []
    selectors = [
        "button:visible",
        "a:visible",
        "input:visible",
        "select:visible",
        "textarea:visible",
        "[role='button']:visible",
        "[role='link']:visible",
        "[role='textbox']:visible",
        "[role='searchbox']:visible",
    ]
    seen = set()
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = loc.count()
            for i in range(count):
                if len(elements) >= INTERACTIVE_ELEMENTS_MAX:
                    break
                try:
                    el = loc.nth(i)
                    if not el.is_visible():
                        continue
                    tag = el.evaluate("el => el.tagName?.toLowerCase() || ''")
                    text = el.inner_text().strip()[:200]
                    uid = f"{tag}|{text[:80]}"
                    if uid in seen:
                        continue
                    seen.add(uid)
                    elem_info = {
                        "tag": tag,
                        "text": text,
                        "type": el.get_attribute("type") or "",
                        "id": el.get_attribute("id") or "",
                        "class": (el.get_attribute("class") or "")[:100],
                        "name": el.get_attribute("name") or "",
                        "placeholder": el.get_attribute("placeholder") or "",
                        "href": el.get_attribute("href") or "",
                        "aria_label": el.get_attribute("aria-label") or "",
                        "role": el.get_attribute("role") or "",
                        "disabled": el.is_disabled(),
                    }
                    # CSS-селектор для быстрого поиска
                    if elem_info["id"]:
                        elem_info["selector"] = f"#{elem_info['id']}"
                    elif elem_info["name"]:
                        elem_info["selector"] = f"[name='{elem_info['name']}']"
                    else:
                        elem_info["selector"] = ""
                    elements.append(elem_info)
                except PlaywrightError:
                    continue
            if len(elements) >= INTERACTIVE_ELEMENTS_MAX:
                break
        except PlaywrightError:
            continue
    return elements


def _clean_page_text(page: "Page") -> str:
    """Извлечь и очистить текст страницы (убрать шум: меню, футеры, скрипты)."""
    try:
        # Удаляем скрипты и стили
        page.evaluate("""() => {
            document.querySelectorAll('script, style, noscript, [aria-hidden="true"]').forEach(el => el.remove());
        }""")
        body = page.locator("body")
        if body.count() > 0:
            text = body.inner_text()
        else:
            text = ""
    except PlaywrightError:
        text = ""

    # Убираем пустые строки и обрезаем
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    clean = "\n".join(lines)
    if len(clean) > PAGE_TEXT_MAX_CHARS:
        clean = clean[:PAGE_TEXT_MAX_CHARS] + "\n... (текст обрезан)"
    return clean


# ═══════════════════════════════════════════════════════════════════════════
# Слой B — самообучающийся кэш сайтов
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SiteProfile:
    """Профиль домена с закэшированными селекторами."""
    domain: str
    search_input: Optional[str] = None
    add_to_cart_button: Optional[str] = None
    login_form: Optional[dict[str, str]] = None  # {"login": "...", "password": "...", "submit": "..."}
    last_verified: str = ""  # дата ISO

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"domain": self.domain}
        if self.search_input:
            d["search_input"] = self.search_input
        if self.add_to_cart_button:
            d["add_to_cart_button"] = self.add_to_cart_button
        if self.login_form:
            d["login_form"] = self.login_form
        if self.last_verified:
            d["last_verified"] = self.last_verified
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SiteProfile":
        return cls(
            domain=d.get("domain", ""),
            search_input=d.get("search_input"),
            add_to_cart_button=d.get("add_to_cart_button"),
            login_form=d.get("login_form"),
            last_verified=d.get("last_verified", ""),
        )


class SiteProfilesStore:
    """Хранилище профилей сайтов (Слой B)."""

    def __init__(self, path: str = SITE_PROFILES_PATH) -> None:
        self._path = path
        self._profiles: dict[str, SiteProfile] = {}
        self._load()

    def _load(self) -> None:
        data = _load_json(self._path, default={})
        if isinstance(data, list):
            # старый формат — список
            for item in data:
                sp = SiteProfile.from_dict(item)
                self._profiles[sp.domain] = sp
        elif isinstance(data, dict):
            for domain, item in data.items():
                item["domain"] = domain
                sp = SiteProfile.from_dict(item)
                self._profiles[domain] = sp

    def _save(self) -> None:
        data = {d: sp.to_dict() for d, sp in self._profiles.items()}
        _atomic_write(self._path, data)

    def get(self, domain: str) -> Optional[SiteProfile]:
        return self._profiles.get(domain)

    def update(self, profile: SiteProfile) -> None:
        profile.last_verified = time.strftime("%Y-%m-%d")
        self._profiles[profile.domain] = profile
        self._save()

    def invalidate(self, domain: str) -> None:
        if domain in self._profiles:
            del self._profiles[domain]
            self._save()


# ═══════════════════════════════════════════════════════════════════════════
# Политика доменов «спроси один раз — запомни»
# ═══════════════════════════════════════════════════════════════════════════

class AllowedDomains:
    """Персистентный список разрешённых доменов."""

    def __init__(self, path: str = ALLOWED_DOMAINS_PATH) -> None:
        self._path = path
        self._domains: set[str] = set()
        self._load()

    def _load(self) -> None:
        data = _load_json(self._path, default=[])
        if isinstance(data, list):
            self._domains = set(data)
        elif isinstance(data, dict):
            self._domains = set(data.keys())

    def _save(self) -> None:
        _atomic_write(self._path, sorted(self._domains))

    def is_allowed(self, domain: str) -> bool:
        return domain in self._domains

    def allow(self, domain: str) -> None:
        self._domains.add(domain)
        self._save()

    def revoke(self, domain: str) -> None:
        self._domains.discard(domain)
        self._save()

    def all_domains(self) -> list[str]:
        return sorted(self._domains)


# ═══════════════════════════════════════════════════════════════════════════
# BrowserSession — постоянный контекст браузера
# ═══════════════════════════════════════════════════════════════════════════

class BrowserSession:
    """Управление жизненным циклом браузера и сохранением сессии."""

    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    _headless: bool = True
    _storage_state_path: str = STORAGE_STATE_PATH
    _idle_timeout: float = 300.0  # 5 минут неактивности → закрытие
    _last_activity: float = 0.0
    _steps_this_request: int = 0
    _sites_store: SiteProfilesStore
    _allowed_domains: AllowedDomains

    def __init__(
        self,
        headless: bool = True,
        storage_state_path: str = STORAGE_STATE_PATH,
        sites_path: str = SITE_PROFILES_PATH,
        allowed_path: str = ALLOWED_DOMAINS_PATH,
    ) -> None:
        self._headless = headless
        self._storage_state_path = storage_state_path
        self._sites_store = SiteProfilesStore(sites_path)
        self._allowed_domains = AllowedDomains(allowed_path)

    @property
    def headless(self) -> bool:
        return self._headless

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def allowed_domains(self) -> AllowedDomains:
        return self._allowed_domains

    @property
    def sites_store(self) -> SiteProfilesStore:
        return self._sites_store

    # ── Запуск / остановка ──────────────────────────────────────────────

    def ensure_browser(self) -> None:
        """Ленивый запуск браузера."""
        if self._context is not None:
            self._last_activity = time.time()
            self._bump_steps()
            return

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        # Загружаем сохранённое состояние сессии, если есть
        storage_state = None
        if os.path.exists(self._storage_state_path):
            try:
                with open(self._storage_state_path, "r") as fh:
                    storage_state = json.load(fh)
            except (json.JSONDecodeError, IOError):
                storage_state = None

        self._browser = self._playwright.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()
        self._last_activity = time.time()
        self._steps_this_request = 0

    def close(self) -> None:
        """Закрыть браузер и сохранить состояние сессии."""
        if self._context is not None:
            # Сохраняем состояние сессии атомарно
            try:
                state = self._context.storage_state()
                _atomic_write(self._storage_state_path, state)
            except PlaywrightError:
                pass
            try:
                self._context.close()
            except PlaywrightError:
                pass
            self._context = None
            self._page = None
        if self._browser is not None:
            try:
                self._browser.close()
            except PlaywrightError:
                pass
            self._browser = None

    # ── Вспомогательные ─────────────────────────────────────────────────

    def _bump_steps(self) -> None:
        self._steps_this_request += 1

    def _check_step_limit(self) -> Optional[str]:
        if self._steps_this_request > MAX_STEPS_PER_REQUEST:
            return f"Достигнут лимит шагов ({MAX_STEPS_PER_REQUEST}) за один запрос"
        return None

    def _extract_domain(self, url: str) -> str:
        """Извлечь домен из URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # убираем www. префикс
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname

    # ── Ресурсная блокировка ────────────────────────────────────────────

    def _setup_resource_blocking(self, allow_images: bool = False) -> None:
        """Блокировка ненужных ресурсов для ускорения загрузки."""
        if self._page is None:
            return

        blocked = {"font", "media", "ping", "beacon"}
        if not allow_images:
            blocked.add("image")

        def route_handler(route):
            if route.request.resource_type in blocked:
                route.abort()
            else:
                route.continue_()

        self._page.route("**/*", route_handler)

    # ── Устойчивые селекторы (self-healing) ─────────────────────────────

    def _try_selectors(
        self,
        selectors: list[str],
        timeout: int = 5000,
    ) -> Optional[Any]:
        """Пробует список селекторов, возвращает первый найденный."""
        if self._page is None:
            return None
        for sel in selectors:
            try:
                loc = self._page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                if loc.is_visible():
                    return loc
            except (PlaywrightTimeout, PlaywrightError):
                continue
        return None

    # ── Слой A: эвристики ───────────────────────────────────────────────

    def _heuristic_find_login_form(self) -> Optional[dict[str, str]]:
        """Найти форму логина на странице через универсальные эвристики."""
        if self._page is None:
            return None

        # Ищем поле пароля — главный маркер формы логина
        try:
            pwd_fields = self._page.locator("input[type='password']:visible")
            if pwd_fields.count() == 0:
                return None
            pwd = pwd_fields.first
        except PlaywrightError:
            return None

        # Ищем соседние поля и кнопку
        result: dict[str, str] = {}
        try:
            result["password"] = pwd.get_attribute("id") or pwd.get_attribute("name") or "input[type='password']"
        except PlaywrightError:
            result["password"] = "input[type='password']"

        # Поле логина: input[type=text], input[type=email] рядом с паролем
        for sel in [
            "input[type='email']:visible",
            "input[type='text']:visible",
            "input:not([type]):visible",
        ]:
            try:
                login_el = self._page.locator(sel).first
                if login_el.is_visible():
                    result["login"] = (
                        login_el.get_attribute("id")
                        or login_el.get_attribute("name")
                        or sel
                    )
                    break
            except PlaywrightError:
                continue

        # Кнопка submit
        for btn_sel in [
            "button[type='submit']:visible",
            "input[type='submit']:visible",
            "button:has-text('Войти')",
            "button:has-text('Вход')",
            "button:has-text('Login')",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "button:has-text('войти')",
            "[role='button']:visible",
        ]:
            try:
                btn = self._page.locator(btn_sel).first
                if btn.is_visible():
                    result["submit"] = (
                        btn.get_attribute("id")
                        or btn.get_attribute("name")
                        or btn_sel
                    )
                    break
            except PlaywrightError:
                continue

        return result if len(result) >= 2 else None

    def _heuristic_find_search_field(self) -> Optional[str]:
        """Найти поле поиска на странице через универсальные эвристики."""
        if self._page is None:
            return None

        # input[type=search] — самый надёжный маркер
        try:
            search_inputs = self._page.locator("input[type='search']:visible")
            if search_inputs.count() > 0:
                el = search_inputs.first
                return el.get_attribute("id") or el.get_attribute("name") or "input[type='search']"
        except PlaywrightError:
            pass

        # input с role='searchbox' или aria-label с поисковыми фразами
        try:
            all_inputs = self._page.locator("input:visible")
            for i in range(min(all_inputs.count(), 20)):
                el = all_inputs.nth(i)
                role = (el.get_attribute("role") or "").lower()
                aria = (el.get_attribute("aria-label") or "").lower()
                placeholder = (el.get_attribute("placeholder") or "").lower()
                name = (el.get_attribute("name") or "").lower()
                combined = f"{role} {aria} {placeholder} {name}"
                if _text_matches_any(combined, SEARCH_FIELD_HINTS):
                    return el.get_attribute("id") or el.get_attribute("name") or f"input[placeholder='{placeholder}']"
        except PlaywrightError:
            pass

        # Ищем input с иконкой лупы рядом
        for icon_sel in ["svg", "[data-icon='search']", ".icon-search", ".fa-search"]:
            try:
                icons = self._page.locator(icon_sel)
                if icons.count() > 0:
                    # Ищем ближайший input
                    for i in range(min(icons.count(), 5)):
                        icon_el = icons.nth(i)
                        nearby_input = icon_el.locator(".. input, ..//input").first
                        if nearby_input.count() > 0:
                            el = nearby_input
                            if el.is_visible():
                                return el.get_attribute("id") or el.get_attribute("name") or "input"
            except PlaywrightError:
                continue

        return None

    def _heuristic_find_add_to_cart_button(self) -> Optional[str]:
        """Найти кнопку добавления в корзину через эвристики."""
        if self._page is None:
            return None

        for phrase in ADD_TO_CART_PHRASES:
            try:
                btn = self._page.get_by_role("button", name=phrase)
                if btn.count() > 0 and btn.first.is_visible():
                    el = btn.first
                    return el.get_attribute("id") or f"button:text('{phrase}')"
            except PlaywrightError:
                pass

        # Поиск по тексту кнопок
        try:
            all_buttons = self._page.locator(
                "button:visible, [role='button']:visible, a.button:visible, a.btn:visible"
            )
            for i in range(min(all_buttons.count(), 30)):
                el = all_buttons.nth(i)
                text = (el.inner_text() or "").lower()
                for phrase in ADD_TO_CART_PHRASES:
                    if phrase.lower() in text:
                        return el.get_attribute("id") or f"button:text('{text[:40]}')"
        except PlaywrightError:
            pass

        return None

    # ── Селектор с кэшированием (Слой A + B) ────────────────────────────

    def _find_element_with_cache(
        self,
        domain: str,
        element_type: str,  # "search_input" | "add_to_cart_button" | "login_form"
    ) -> Optional[Any]:
        """
        Найти элемент: сначала пробуем кэш (Слой B),
        при неудаче — эвристики (Слой A), результат кэшируем.
        """
        profile = self._sites_store.get(domain)

        # Слой B — пробуем кэш
        if profile is not None:
            if element_type == "search_input" and profile.search_input:
                sel = self._try_selectors([profile.search_input], timeout=3000)
                if sel is not None:
                    return sel
                # кэш невалиден — удаляем и идём в эвристики
                profile.search_input = None

            if element_type == "add_to_cart_button" and profile.add_to_cart_button:
                sel = self._try_selectors([profile.add_to_cart_button], timeout=3000)
                if sel is not None:
                    return sel
                profile.add_to_cart_button = None

            if element_type == "login_form" and profile.login_form:
                form = profile.login_form
                all_found = True
                for key in ["login", "password", "submit"]:
                    if key in form:
                        sel = self._try_selectors([form[key]], timeout=3000)
                        if sel is None:
                            all_found = False
                            break
                if all_found:
                    return form
                profile.login_form = None

        # Слой A — эвристики
        result = None
        if element_type == "search_input":
            result = self._heuristic_find_search_field()
        elif element_type == "add_to_cart_button":
            result = self._heuristic_find_add_to_cart_button()
        elif element_type == "login_form":
            result = self._heuristic_find_login_form()

        # Кэшируем успешный результат
        if result is not None and domain:
            if profile is None:
                profile = SiteProfile(domain=domain)
            if element_type == "search_input":
                profile.search_input = result if isinstance(result, str) else str(result)
            elif element_type == "add_to_cart_button":
                profile.add_to_cart_button = result if isinstance(result, str) else str(result)
            elif element_type == "login_form" and isinstance(result, dict):
                profile.login_form = result
            self._sites_store.update(profile)

        return result

    # ── Проверка на чувствительные действия ─────────────────────────────

    def _is_sensitive_action(self, selector: str) -> bool:
        """Проверить, является ли селектор чувствительным действием."""
        if not selector:
            return False
        low = selector.lower()
        return _text_matches_any(low, SENSITIVE_ACTION_KEYWORDS)

    # ═══════════════════════════════════════════════════════════════════════════
    # Атомарные тулы
    # ═══════════════════════════════════════════════════════════════════════════

    def navigate(self, url: str, allow_images: bool = False) -> dict[str, Any]:
        """
        Открыть URL в браузере.
        Возвращает статус и базовую информацию о странице.
        """
        self.ensure_browser()
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        # Проверка домена
        domain = self._extract_domain(url)
        if domain and not self._allowed_domains.is_allowed(domain):
            return {
                "needs_confirmation": True,
                "domain": domain,
                "message": f"Домен '{domain}' не в списке разрешённых. Перейти?",
                "step": "domain_confirmation",
            }

        self._setup_resource_blocking(allow_images=allow_images)
        assert self._page is not None

        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self._page.wait_for_load_state("domcontentloaded")
            title = self._page.title()
            current_url = self._page.url
            return {
                "success": True,
                "url": current_url,
                "title": title,
                "domain": domain,
            }
        except PlaywrightTimeout:
            return {"error": f"Таймаут при загрузке {url}"}
        except PlaywrightError as e:
            return {"error": f"Ошибка перехода: {str(e)}"}

    def navigate_back(self) -> dict[str, Any]:
        """Вернуться на предыдущую страницу."""
        self.ensure_browser()
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        assert self._page is not None
        try:
            self._page.go_back(wait_until="domcontentloaded")
            return {"success": True, "url": self._page.url}
        except PlaywrightError as e:
            return {"error": str(e)}

    def get_page_state(self) -> dict[str, Any]:
        """Получить снапшот страницы: URL, заголовок, интерактивные элементы."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            url = self._page.url
            title = self._page.title()
            elements = _extract_interactive_elements(self._page)
            return {
                "url": url,
                "title": title,
                "interactive_elements": elements,
                "element_count": len(elements),
            }
        except PlaywrightError as e:
            return {"error": str(e)}

    def click(self, selector: str) -> dict[str, Any]:
        """
        Кликнуть по элементу.
        Перед кликом проверяет, не является ли действие чувствительным.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        # Проверка на чувствительное действие
        if self._is_sensitive_action(selector):
            return {
                "needs_confirmation": True,
                "selector": selector,
                "message": (
                    "Обнаружено чувствительное действие. "
                    "Подтвердите в чате выполнение клика."
                ),
            }

        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {
                    "error": f"Элемент не найден по селектору '{selector}'",
                    "suggestion": "Выполните get_page_state, чтобы увидеть доступные элементы.",
                }
            loc.click(timeout=10000)
            self._page.wait_for_load_state("domcontentloaded")
            return {"success": True, "selector": selector}
        except PlaywrightTimeout:
            return {"error": f"Таймаут при клике по '{selector}'"}
        except PlaywrightError as e:
            return {"error": f"Ошибка клика: {str(e)}"}

    def fill(self, selector: str, value: str) -> dict[str, Any]:
        """Заполнить поле формы."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Поле не найдено: '{selector}'"}
            loc.fill(value)
            return {"success": True, "selector": selector}
        except PlaywrightError as e:
            return {"error": f"Ошибка заполнения: {str(e)}"}

    def get_text(self, selector: str | None = None) -> dict[str, Any]:
        """Извлечь текст со страницы или конкретного элемента."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            if selector:
                loc = self._try_selectors([selector])
                if loc is None:
                    return {"error": f"Элемент не найден: '{selector}'"}
                text = loc.inner_text()
            else:
                text = _clean_page_text(self._page)
            return {
                "text": text,
                "length": len(text),
            }
        except PlaywrightError as e:
            return {"error": str(e)}

    def screenshot(self, full_page: bool = False) -> dict[str, Any]:
        """Сделать скриншот текущей страницы (base64)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            data = self._page.screenshot(full_page=full_page, type="png")
            import base64
            b64 = base64.b64encode(data).decode("utf-8")
            return {
                "screenshot": f"data:image/png;base64,{b64}",
                "format": "png",
            }
        except PlaywrightError as e:
            return {"error": str(e)}

    def wait_for(self, selector: str, timeout: int = 10000) -> dict[str, Any]:
        """Ожидать появления элемента на странице."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            self._page.locator(selector).first.wait_for(
                state="visible", timeout=timeout
            )
            return {"success": True, "selector": selector}
        except PlaywrightTimeout:
            return {"error": f"Таймаут ({timeout}ms): элемент '{selector}' не появился"}
        except PlaywrightError as e:
            return {"error": str(e)}

    def evaluate_js(self, script: str) -> dict[str, Any]:
        """Выполнить JavaScript в контексте страницы."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            result = self._page.evaluate(script)
            return {"success": True, "result": result}
        except PlaywrightError as e:
            return {"error": str(e)}

    def get_html(self) -> dict[str, Any]:
        """Получить полный HTML страницы."""
        if self._page is None:
            return {"error": "Браузер не запущен"}

        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}

        try:
            html = self._page.content()
            if len(html) > PAGE_TEXT_MAX_CHARS:
                html = html[:PAGE_TEXT_MAX_CHARS] + "\n<!-- HTML обрезан -->"
            return {"html": html, "length": len(html)}
        except PlaywrightError as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # Смарт-тулы (Слой A + B)
    # ═══════════════════════════════════════════════════════════════════════════

    def smart_login(
        self,
        url: str,
        credentials: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Универсальный вход на сайт.
        1. Переходит по URL
        2. Находит форму логина (Слой A + B)
        3. Заполняет поля (если переданы credentials)
        4. Отправляет форму
        5. Проверяет успех входа
        """
        # Шаг 1: переход
        nav = self.navigate(url)
        if "error" in nav:
            return nav

        domain = self._extract_domain(url)

        # Шаг 2: поиск формы логина
        form = self._find_element_with_cache(domain, "login_form")
        if form is None:
            return {
                "error": "Форма логина не найдена на странице",
                "suggestion": "Попробуйте найти форму вручную через get_page_state",
            }

        # Шаг 3: заполнение
        if credentials:
            login_sel = form.get("login")
            pwd_sel = form.get("password")
            if login_sel:
                self.fill(login_sel, credentials.get("login", ""))
            if pwd_sel:
                self.fill(pwd_sel, credentials.get("password", ""))

        # Шаг 4: отправка
        submit_sel = form.get("submit")
        if submit_sel:
            click_result = self.click(submit_sel)
            if "error" in click_result:
                return click_result
        else:
            # Пробуем нажать Enter в поле пароля
            if pwd_sel and self._page:
                try:
                    self._page.locator(pwd_sel).first.press("Enter")
                except PlaywrightError as e:
                    return {"error": f"Ошибка отправки формы: {str(e)}"}

        # Ждём навигацию
        if self._page:
            try:
                self._page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeout:
                pass

        # Шаг 5: проверка успеха
        if self._page:
            page_text = _clean_page_text(self._page).lower()
            success = _text_matches_any(page_text, LOGIN_SUCCESS_INDICATORS)
            return {
                "success": success,
                "url": self._page.url,
                "message": "Вход выполнен успешно" if success else "Не удалось подтвердить вход",
            }

        return {"success": False, "error": "Страница недоступна"}

    def smart_search(
        self,
        url: str,
        query: str,
    ) -> dict[str, Any]:
        """
        Универсальный поиск на сайте.
        1. Переходит по URL
        2. Находит поле поиска (Слой A + B)
        3. Вводит запрос и отправляет
        4. Извлекает структурированные результаты
        """
        # Шаг 1
        nav = self.navigate(url)
        if "error" in nav:
            return nav

        domain = self._extract_domain(url)

        # Шаг 2: поиск поля
        search_sel = self._find_element_with_cache(domain, "search_input")
        if search_sel is None:
            return {
                "error": "Поле поиска не найдено на странице",
                "suggestion": "Попробуйте найти поле вручную через get_page_state",
            }

        # Шаг 3: ввод и отправка
        if isinstance(search_sel, dict):
            search_sel = search_sel.get("search_input", "input[type='search']")

        self.fill(str(search_sel), query)
        if self._page:
            try:
                self._page.locator(str(search_sel)).first.press("Enter")
            except PlaywrightError:
                pass

        # Ждём результаты
        if self._page:
            try:
                self._page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeout:
                pass

        # Шаг 4: извлечение результатов (эвристический поиск карточек товаров)
        items: list[dict[str, str]] = []
        if self._page:
            items = self._extract_product_cards()

        return {
            "success": True,
            "query": query,
            "url": self._page.url if self._page else url,
            "results_count": len(items),
            "results": items[:20],  # ограничиваем вывод
        }

    def smart_add_to_cart(self, product_url: str) -> dict[str, Any]:
        """
        Универсальное добавление в корзину.
        1. Переходит по URL товара
        2. Находит кнопку «в корзину» (Слой A + B)
        3. Проверяет на чувствительность
        4. Кликает
        """
        nav = self.navigate(product_url)
        if "error" in nav:
            return nav

        domain = self._extract_domain(product_url)

        add_btn = self._find_element_with_cache(domain, "add_to_cart_button")
        if add_btn is None:
            return {
                "error": "Кнопка добавления в корзину не найдена",
                "suggestion": "Попробуйте найти кнопку вручную через get_page_state",
            }

        if isinstance(add_btn, str):
            selector = add_btn
        else:
            selector = str(add_btn)

        return self.click(selector)

    def _extract_product_cards(self) -> list[dict[str, str]]:
        """Эвристически извлечь карточки товаров со страницы результатов."""
        if self._page is None:
            return []

        items: list[dict[str, str]] = []
        # Ищем повторяющиеся элементы, похожие на карточки товаров
        product_selectors = [
            "[data-testid='product-card']",
            ".product-card",
            ".product-item",
            ".product",
            "article.product",
            "li.product",
            ".goods-item",
            ".catalog-item",
            "[class*='product']",
            "[class*='item']",
        ]

        for sel in product_selectors:
            try:
                cards = self._page.locator(sel)
                if cards.count() >= 2:
                    for i in range(min(cards.count(), 20)):
                        card = cards.nth(i)
                        if not card.is_visible():
                            continue
                        text = card.inner_text()
                        if len(text) < 10:
                            continue
                        # Извлекаем название, цену, ссылку
                        name = ""
                        price = ""
                        link = ""
                        try:
                            name_el = card.locator("h2, h3, h4, .title, .name, a").first
                            if name_el.count() > 0:
                                name = name_el.inner_text().strip()[:200]
                                link = name_el.get_attribute("href") or ""
                        except PlaywrightError:
                            pass
                        try:
                            price_el = card.locator(
                                ".price, [class*='price'], .cost, [class*='cost']"
                            ).first
                            if price_el.count() > 0:
                                price = price_el.inner_text().strip()[:100]
                        except PlaywrightError:
                            pass
                        items.append({
                            "name": name or text.strip()[:200],
                            "price": price,
                            "link": link,
                        })
                    break
            except PlaywrightError:
                continue

        return items

    # ── Управление доменами ─────────────────────────────────────────────

    def allow_domain(self, domain: str) -> dict[str, Any]:
        """Добавить домен в список разрешённых."""
        self._allowed_domains.allow(domain)
        return {
            "success": True,
            "domain": domain,
            "message": f"Домен '{domain}' добавлен в разрешённые",
        }

    def get_allowed_domains(self) -> dict[str, Any]:
        """Получить список разрешённых доменов."""
        return {
            "domains": self._allowed_domains.all_domains(),
            "count": len(self._allowed_domains.all_domains()),
        }

    def revoke_domain(self, domain: str) -> dict[str, Any]:
        """Удалить домен из разрешённых."""
        self._allowed_domains.revoke(domain)
        return {"success": True, "domain": domain, "message": f"Домен '{domain}' удалён"}

    def confirm_action(self) -> dict[str, Any]:
        """Подтвердить последнее чувствительное действие."""
        return {"success": True, "message": "Действие подтверждено"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 1: базовые примитивы взаимодействия
    # ═══════════════════════════════════════════════════════════════════════

    def scroll(self, amount: int = 300, direction: str = "down",
               selector: str = "") -> dict[str, Any]:
        """Прокрутка страницы на N пикселей или до элемента."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            if selector:
                loc = self._try_selectors([selector])
                if loc is None:
                    return {"error": f"Элемент не найден: '{selector}'"}
                loc.scroll_into_view_if_needed()
                return {"success": True, "selector": selector, "action": "scroll_to_element"}
            # Скролл на пиксели
            dx, dy = 0, 0
            if direction == "down":
                dy = amount
            elif direction == "up":
                dy = -amount
            elif direction == "right":
                dx = amount
            elif direction == "left":
                dx = -amount
            self._page.mouse.wheel(dx, dy)
            return {"success": True, "direction": direction, "amount": amount}
        except PlaywrightError as e:
            return {"error": f"Ошибка скролла: {str(e)}"}

    def hover(self, selector: str) -> dict[str, Any]:
        """Навести курсор на элемент (hover)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Элемент не найден: '{selector}'"}
            loc.hover()
            return {"success": True, "selector": selector}
        except PlaywrightError as e:
            return {"error": f"Ошибка hover: {str(e)}"}

    def double_click(self, selector: str) -> dict[str, Any]:
        """Двойной клик по элементу."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        if self._is_sensitive_action(selector):
            return {
                "needs_confirmation": True,
                "selector": selector,
                "message": "Обнаружено чувствительное действие. Подтвердите выполнение.",
            }
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Элемент не найден: '{selector}'"}
            loc.dblclick(timeout=10000)
            self._page.wait_for_load_state("domcontentloaded")
            return {"success": True, "selector": selector}
        except PlaywrightError as e:
            return {"error": f"Ошибка двойного клика: {str(e)}"}

    def right_click(self, selector: str) -> dict[str, Any]:
        """Правый клик по элементу (контекстное меню)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Элемент не найден: '{selector}'"}
            loc.click(button="right", timeout=5000)
            return {"success": True, "selector": selector}
        except PlaywrightError as e:
            return {"error": f"Ошибка правого клика: {str(e)}"}

    def type_text(self, selector: str, text: str, delay: int = 50) -> dict[str, Any]:
        """Постепенный ввод текста с эмуляцией нажатий клавиш."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Поле не найдено: '{selector}'"}
            loc.click()
            loc.fill("")  # очищаем
            loc.type(text, delay=delay)
            return {"success": True, "selector": selector, "text_length": len(text)}
        except PlaywrightError as e:
            return {"error": f"Ошибка ввода: {str(e)}"}

    def press_key(self, key: str, selector: str = "") -> dict[str, Any]:
        """Нажать клавишу (Enter, Escape, Tab, Ctrl+C и т.д.)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            if selector:
                loc = self._try_selectors([selector])
                if loc is None:
                    return {"error": f"Элемент не найден: '{selector}'"}
                loc.press(key)
            else:
                self._page.keyboard.press(key)
            return {"success": True, "key": key, "selector": selector or "page"}
        except PlaywrightError as e:
            return {"error": f"Ошибка нажатия клавиши: {str(e)}"}

    def drag(self, source_selector: str, target_selector: str) -> dict[str, Any]:
        """Перетащить элемент из source в target."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            src = self._try_selectors([source_selector])
            if src is None:
                return {"error": f"Исходный элемент не найден: '{source_selector}'"}
            tgt = self._try_selectors([target_selector])
            if tgt is None:
                return {"error": f"Целевой элемент не найден: '{target_selector}'"}
            src.drag_to(tgt)
            return {
                "success": True,
                "source": source_selector,
                "target": target_selector,
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка перетаскивания: {str(e)}"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 2: мульти-табы
    # ═══════════════════════════════════════════════════════════════════════

    def new_tab(self, url: str = "") -> dict[str, Any]:
        """Открыть новую вкладку. Если url передан — перейти по нему."""
        if self._context is None:
            self.ensure_browser()
        assert self._context is not None
        try:
            new_page = self._context.new_page()
            if url:
                new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self._page = new_page
            pages = self._context.pages
            index = pages.index(new_page)
            return {
                "success": True,
                "tab_index": index,
                "total_tabs": len(pages),
                "url": new_page.url,
                "title": new_page.title(),
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка создания вкладки: {str(e)}"}

    def switch_tab(self, index: int) -> dict[str, Any]:
        """Переключиться на вкладку по индексу (0-based)."""
        if self._context is None:
            return {"error": "Браузер не запущен"}
        pages = self._context.pages
        if index < 0 or index >= len(pages):
            return {"error": f"Индекс вкладки {index} вне диапазона [0, {len(pages)-1}]"}
        try:
            self._page = pages[index]
            self._page.bring_to_front()
            return {
                "success": True,
                "tab_index": index,
                "total_tabs": len(pages),
                "url": self._page.url,
                "title": self._page.title(),
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка переключения вкладки: {str(e)}"}

    def close_tab(self, index: int = -1) -> dict[str, Any]:
        """Закрыть вкладку по индексу. -1 = текущая."""
        if self._context is None:
            return {"error": "Браузер не запущен"}
        pages = self._context.pages
        if len(pages) <= 1:
            return {"error": "Нельзя закрыть последнюю вкладку"}
        if index < 0:
            index = pages.index(self._page) if self._page else 0
        if index < 0 or index >= len(pages):
            return {"error": f"Индекс вкладки {index} вне диапазона"}
        try:
            closed_url = pages[index].url
            pages[index].close()
            # Переключаемся на первую доступную
            remaining = self._context.pages
            self._page = remaining[0] if remaining else None
            return {
                "success": True,
                "closed_index": index,
                "closed_url": closed_url,
                "total_tabs": len(remaining),
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка закрытия вкладки: {str(e)}"}

    def list_tabs(self) -> dict[str, Any]:
        """Список всех открытых вкладок."""
        if self._context is None:
            return {"tabs": [], "count": 0}
        tabs = []
        for i, p in enumerate(self._context.pages):
            try:
                tabs.append({
                    "index": i,
                    "url": p.url,
                    "title": p.title(),
                    "is_current": p == self._page,
                })
            except PlaywrightError:
                tabs.append({"index": i, "url": "?", "title": "?", "is_current": False})
        return {"tabs": tabs, "count": len(tabs)}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 3: диалоги, загрузки, хранилище
    # ═══════════════════════════════════════════════════════════════════════

    def handle_dialog(self, action: str = "accept", prompt_text: str = "") -> dict[str, Any]:
        """Обработать диалог (alert/confirm/prompt)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            dialog = self._page.wait_for_event("dialog", timeout=5000)
            if action == "accept":
                if prompt_text:
                    dialog.accept(prompt_text)
                else:
                    dialog.accept()
            elif action == "dismiss":
                dialog.dismiss()
            else:
                return {"error": f"Неизвестное действие: '{action}'. Допустимы: accept, dismiss"}
            return {
                "success": True,
                "action": action,
                "dialog_type": dialog.type,
                "dialog_message": dialog.message,
            }
        except PlaywrightTimeout:
            return {"error": "Диалог не появился в течение 5 секунд"}
        except PlaywrightError as e:
            return {"error": f"Ошибка обработки диалога: {str(e)}"}

    def upload_file(self, selector: str, file_path: str) -> dict[str, Any]:
        """Загрузить файл в input[type=file]."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Поле загрузки не найдено: '{selector}'"}
            loc.set_input_files(file_path)
            return {"success": True, "selector": selector, "file": file_path}
        except PlaywrightError as e:
            return {"error": f"Ошибка загрузки файла: {str(e)}"}

    def cookies(self, action: str = "get",
                cookie_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Управление cookies: get — получить, set — установить, clear — очистить."""
        if self._context is None:
            return {"error": "Браузер не запущен"}
        try:
            if action == "get":
                all_cookies = self._context.cookies()
                return {"cookies": all_cookies, "count": len(all_cookies)}
            elif action == "set":
                if not cookie_data:
                    return {"error": "cookie_data обязателен для set"}
                # Обеспечиваем обязательные поля
                c = dict(cookie_data)
                if "url" not in c and "domain" not in c:
                    c["domain"] = self._page.url if self._page else ""
                self._context.add_cookies([{k: v for k, v in c.items()
                    if k in ("name", "value", "url", "domain", "path", "secure",
                             "httpOnly", "sameSite", "expires")}])
                return {"success": True, "action": "set"}
            elif action == "clear":
                self._context.clear_cookies()
                return {"success": True, "action": "clear"}
            else:
                return {"error": f"Неизвестное действие: '{action}'. Допустимы: get, set, clear"}
        except PlaywrightError as e:
            return {"error": f"Ошибка cookies: {str(e)}"}

    def local_storage(self, action: str = "get",
                      key: str = "", value: str = "") -> dict[str, Any]:
        """Управление localStorage: get, set, remove, clear, keys."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            if action == "get":
                if key:
                    val = self._page.evaluate(f"localStorage.getItem('{key}')")
                    return {"key": key, "value": val}
                else:
                    # Все ключи и значения
                    items = self._page.evaluate(
                        "() => { const r={}; for(let i=0;i<localStorage.length;i++)"
                        "{ const k=localStorage.key(i); r[k]=localStorage.getItem(k); } return r; }"
                    )
                    return {"items": items, "count": len(items)}
            elif action == "set":
                if not key:
                    return {"error": "key обязателен для set"}
                self._page.evaluate(f"localStorage.setItem('{key}', '{value}')")
                return {"success": True, "action": "set", "key": key}
            elif action == "remove":
                if not key:
                    return {"error": "key обязателен для remove"}
                self._page.evaluate(f"localStorage.removeItem('{key}')")
                return {"success": True, "action": "remove", "key": key}
            elif action == "clear":
                self._page.evaluate("localStorage.clear()")
                return {"success": True, "action": "clear"}
            elif action == "keys":
                keys = self._page.evaluate(
                    "() => { const r=[]; for(let i=0;i<localStorage.length;i++)"
                    " r.push(localStorage.key(i)); return r; }"
                )
                return {"keys": keys, "count": len(keys)}
            else:
                return {"error": f"Неизвестное действие: '{action}'"}
        except PlaywrightError as e:
            return {"error": f"Ошибка localStorage: {str(e)}"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 4: визуальный режим
    # ═══════════════════════════════════════════════════════════════════════

    def screenshot_element(self, selector: str) -> dict[str, Any]:
        """Скриншот конкретного элемента (не всей страницы)."""
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            loc = self._try_selectors([selector])
            if loc is None:
                return {"error": f"Элемент не найден: '{selector}'"}
            data = loc.screenshot(type="png")
            import base64
            b64 = base64.b64encode(data).decode("utf-8")
            return {
                "screenshot": f"data:image/png;base64,{b64}",
                "selector": selector,
                "format": "png",
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка скриншота элемента: {str(e)}"}

    def element_som(self, selector: str = "", max_elements: int = 30) -> dict[str, Any]:
        """
        Set-of-Marks: скриншот страницы с пронумерованными элементами.
        Возвращает скриншот и список элементов с координатами.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            elements = _extract_interactive_elements(self._page)[:max_elements]
            # Получаем координаты через JS
            coords_js = """
            (selectors) => {
                const results = [];
                for (const s of selectors) {
                    try {
                        const el = s.id ? document.getElementById(s.id)
                            : s.name ? document.querySelector(`[name='${s.name}']`)
                            : null;
                        if (el) {
                            const r = el.getBoundingClientRect();
                            results.push({x: r.x + r.width/2, y: r.y + r.height/2,
                                          width: r.width, height: r.height,
                                          visible: r.width > 0 && r.height > 0});
                        } else { results.push(null); }
                    } catch(e) { results.push(null); }
                }
                return results;
            }
            """
            element_info = [{"id": e.get("id"), "name": e.get("name"),
                           "tag": e.get("tag"), "text": e.get("text")[:80]}
                          for e in elements]
            coords = self._page.evaluate(coords_js, element_info)
            # Делаем скриншот
            data = self._page.screenshot(full_page=False, type="png")
            import base64
            b64 = base64.b64encode(data).decode("utf-8")
            # Привязываем координаты к элементам
            markers = []
            for i, (elem, coord) in enumerate(zip(elements, coords)):
                if coord and coord.get("visible"):
                    markers.append({
                        "index": i + 1,
                        "tag": elem.get("tag"),
                        "text": elem.get("text")[:80],
                        "x": round(coord["x"]),
                        "y": round(coord["y"]),
                        "selector": elem.get("selector"),
                    })
            return {
                "screenshot": f"data:image/png;base64,{b64}",
                "markers": markers,
                "marker_count": len(markers),
                "total_elements": len(elements),
                "hint": "Элементы пронумерованы. Используйте browser_click с marker_index.",
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка SOM: {str(e)}"}

    def visual_qa(self, question: str, selector: str = "") -> dict[str, Any]:
        """
        Визуальный вопрос по скриншоту.
        Делает скриншот и возвращает его вместе с вопросом.
        Анализ выполняется вызывающей стороной (multimodal LLM).
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            if selector:
                result = self.screenshot_element(selector)
                if "error" in result:
                    return result
                screenshot = result["screenshot"]
            else:
                data = self._page.screenshot(full_page=False, type="png")
                import base64
                screenshot = f"data:image/png;base64,{base64.b64encode(data).decode('utf-8')}"
            return {
                "screenshot": screenshot,
                "question": question,
                "url": self._page.url,
                "hint": "Передайте screenshot модели с поддержкой vision для анализа.",
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка visual_qa: {str(e)}"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 5: сеть и iframe
    # ═══════════════════════════════════════════════════════════════════════

    def network_requests(self, action: str = "list",
                         url_filter: str = "") -> dict[str, Any]:
        """
        Перехват сетевых запросов.
        action: list — показать перехваченные запросы,
               start — начать перехват, stop — остановить, clear — очистить.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            if action == "start":
                # Сохраняем запросы в атрибут страницы
                self._page.evaluate(
                    "() => { window.__termit_network_log = []; }"
                )
                def log_request(request):
                    self._page.evaluate(
                        f"() => {{ window.__termit_network_log.push("
                        f"{{url:'{request.url}', method:'{request.method}', "
                        f"status:0, type:'{request.resource_type}'}}); }}"
                    )

                def log_response(response):
                    try:
                        self._page.evaluate(
                            f"() => {{ const log = window.__termit_network_log;"
                            f"const r = log.find(x => x.url === '{response.url}' && x.status === 0);"
                            f"if(r) r.status = {response.status}; }}"
                        )
                    except Exception:
                        pass

                self._page.on("request", log_request)
                self._page.on("response", log_response)
                return {"success": True, "action": "start"}
            elif action == "list":
                log = self._page.evaluate(
                    "() => window.__termit_network_log || []"
                )
                if url_filter:
                    log = [r for r in log if url_filter.lower() in r.get("url", "").lower()]
                return {"requests": log[-50:], "count": len(log[-50:])}
            elif action == "stop":
                self._page.evaluate("() => { delete window.__termit_network_log; }")
                return {"success": True, "action": "stop"}
            elif action == "clear":
                self._page.evaluate("() => { window.__termit_network_log = []; }")
                return {"success": True, "action": "clear"}
            else:
                return {"error": f"Неизвестное действие: '{action}'"}
        except PlaywrightError as e:
            return {"error": f"Ошибка network_requests: {str(e)}"}

    def iframe_switch(self, selector: str = "",
                      action: str = "list") -> dict[str, Any]:
        """
        Навигация по iframe.
        action: list — показать все iframe на странице,
               switch — переключиться в iframe по селектору,
               main — вернуться в основной фрейм.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            if action == "list":
                frames = self._page.frames
                result = []
                for i, f in enumerate(frames):
                    try:
                        result.append({
                            "index": i,
                            "url": f.url,
                            "name": f.name or "",
                            "is_main": i == 0,
                        })
                    except PlaywrightError:
                        pass
                return {"frames": result, "count": len(result)}
            elif action == "switch":
                if not selector:
                    return {"error": "selector обязателен для switch"}
                # Ищем frame
                frame = self._page.frame(name=selector) or self._page.frame(url=selector)
                if frame is None:
                    # Ищем через frame_locator
                    loc = self._page.frame_locator(selector)
                    if loc is None:
                        return {"error": f"iframe не найден: '{selector}'"}
                return {
                    "success": True,
                    "action": "switch",
                    "selector": selector,
                    "hint": "Теперь все операции (click, fill, get_text) идут в контексте этого iframe. "
                           "Передавайте селектор iframe в параметре frame_context.",
                }
            elif action == "main":
                return {"success": True, "action": "main", "hint": "Контекст возвращён в основной фрейм."}
            else:
                return {"error": f"Неизвестное действие: '{action}'"}
        except PlaywrightError as e:
            return {"error": f"Ошибка iframe: {str(e)}"}

    def device_emulate(self, device: str = "iPhone 15") -> dict[str, Any]:
        """
        Эмуляция мобильного устройства.
        device: 'iPhone 15', 'iPhone 15 Pro', 'Pixel 7', 'iPad Pro', 'Galaxy S23'.
        """
        if self._context is None:
            self.ensure_browser()
        assert self._context is not None
        known = {
            "iPhone 15": {"width": 390, "height": 844, "device_scale_factor": 3,
                          "is_mobile": True, "has_touch": True},
            "iPhone 15 Pro": {"width": 393, "height": 852, "device_scale_factor": 3,
                              "is_mobile": True, "has_touch": True},
            "Pixel 7": {"width": 412, "height": 915, "device_scale_factor": 2.625,
                        "is_mobile": True, "has_touch": True},
            "iPad Pro": {"width": 1024, "height": 1366, "device_scale_factor": 2,
                         "is_mobile": True, "has_touch": True},
            "Galaxy S23": {"width": 360, "height": 780, "device_scale_factor": 3,
                           "is_mobile": True, "has_touch": True},
            "Desktop": {"width": 1280, "height": 800, "device_scale_factor": 1,
                        "is_mobile": False, "has_touch": False},
        }
        if device not in known:
            return {"error": f"Неизвестное устройство: '{device}'. Доступны: {', '.join(known)}"}
        cfg = known[device]
        try:
            self._page = self._context.new_page(
                viewport={"width": cfg["width"], "height": cfg["height"]},
                device_scale_factor=cfg["device_scale_factor"],
                is_mobile=cfg["is_mobile"],
                has_touch=cfg["has_touch"],
            )
            return {
                "success": True,
                "device": device,
                "viewport": f"{cfg['width']}x{cfg['height']}",
                "is_mobile": cfg["is_mobile"],
            }
        except PlaywrightError as e:
            return {"error": f"Ошибка эмуляции: {str(e)}"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 6: смарт-тулы v2
    # ═══════════════════════════════════════════════════════════════════════

    def smart_form(self, url: str,
                   fields: dict[str, str]) -> dict[str, Any]:
        """
        Универсальное заполнение форм.
        Анализирует label/placeholder/name полей и заполняет по словарю fields.
        """
        nav = self.navigate(url)
        if "error" in nav:
            return nav
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        filled = []
        errors = []
        for field_name, field_value in fields.items():
            # Ищем поле по разным атрибутам
            selectors = [
                f"#{field_name}",
                f"[name='{field_name}']",
                f"[placeholder*='{field_name}' i]",
                f"[aria-label*='{field_name}' i]",
                f"label:has-text('{field_name}') + input",
                f"label:has-text('{field_name}') >> input",
                f"label:has-text('{field_name}') >> textarea",
            ]
            found = False
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        tag = loc.evaluate("el => el.tagName?.toLowerCase() || ''")
                        if tag in ("input", "textarea"):
                            loc.fill(str(field_value))
                        elif tag == "select":
                            loc.select_option(str(field_value))
                        filled.append(f"{field_name}: {field_value}")
                        found = True
                        break
                except PlaywrightError:
                    continue
            if not found:
                errors.append(f"{field_name}: поле не найдено")
        return {
            "success": len(filled) > 0,
            "filled_fields": filled,
            "errors": errors,
            "url": self._page.url,
        }

    def smart_extract(self, extract_type: str = "tables",
                      selector: str = "") -> dict[str, Any]:
        """
        Извлечение структурированных данных со страницы.
        extract_type: tables, lists, cards, prices, links, headings.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        limit_err = self._check_step_limit()
        if limit_err:
            return {"error": limit_err}
        try:
            if extract_type == "tables":
                result = self._page.evaluate("""
                    () => {
                        const tables = [];
                        document.querySelectorAll('table').forEach((t, i) => {
                            const rows = [];
                            t.querySelectorAll('tr').forEach(tr => {
                                const cells = [];
                                tr.querySelectorAll('td, th').forEach(c => cells.push(c.innerText.trim()));
                                if (cells.length) rows.push(cells);
                            });
                            if (rows.length) tables.push({index: i, headers: rows[0] || [], rows: rows.slice(1), total_rows: rows.length});
                        });
                        return tables;
                    }
                """)
                return {"tables": result, "count": len(result)}
            elif extract_type == "lists":
                result = self._page.evaluate("""
                    () => {
                        const lists = [];
                        document.querySelectorAll('ul, ol').forEach((l, i) => {
                            const items = [];
                            l.querySelectorAll('li').forEach(li => items.push(li.innerText.trim()));
                            if (items.length && items.length <= 50) lists.push({index: i, tag: l.tagName, items});
                        });
                        return lists;
                    }
                """)
                return {"lists": result, "count": len(result)}
            elif extract_type == "prices":
                result = self._page.evaluate("""
                    () => {
                        const prices = [];
                        const re = /[¥$€£₽]\\s*\\d+[\\d\\s,.]*/g;
                        document.body.innerText.match(re)?.forEach(p => {
                            const clean = p.replace(/\\s+/g, ' ').trim();
                            if (!prices.includes(clean)) prices.push(clean);
                        });
                        return prices.slice(0, 50);
                    }
                """)
                return {"prices": result, "count": len(result)}
            elif extract_type == "links":
                result = self._page.evaluate("""
                    () => {
                        const links = [];
                        document.querySelectorAll('a[href]').forEach(a => {
                            const href = a.href;
                            const text = a.innerText.trim();
                            if (href && !href.startsWith('javascript:') && !href.startsWith('#'))
                                links.push({text: text.slice(0, 200), href});
                        });
                        return links.slice(0, 100);
                    }
                """)
                return {"links": result, "count": len(result)}
            elif extract_type == "headings":
                result = self._page.evaluate("""
                    () => {
                        const headings = [];
                        document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h =>
                            headings.push({tag: h.tagName, text: h.innerText.trim().slice(0, 500)})
                        );
                        return headings;
                    }
                """)
                return {"headings": result, "count": len(result)}
            else:
                return {"error": f"Неизвестный тип извлечения: '{extract_type}'. "
                         "Допустимы: tables, lists, prices, links, headings"}
        except PlaywrightError as e:
            return {"error": f"Ошибка извлечения: {str(e)}"}

    def smart_checkout(self, url: str, steps: Optional[list[dict[str, str]]] = None,
                       auto_continue: bool = False) -> dict[str, Any]:
        """
        Пошаговый чекаут с паузой на каждом шаге.
        steps: список шагов [{action, selector?, value?}] или None для автоопределения.
        """
        if steps is None:
            steps = [
                {"action": "detect", "hint": "Ищем кнопку 'оформить заказ'"},
                {"action": "fill", "hint": "Заполняем адрес доставки"},
                {"action": "fill", "hint": "Выбираем способ доставки"},
                {"action": "fill", "hint": "Выбираем способ оплаты"},
                {"action": "confirm", "hint": "Подтверждаем заказ"},
            ]
        nav = self.navigate(url)
        if "error" in nav:
            return nav
        if self._page is None:
            return {"error": "Браузер не запущен"}
        completed_steps = []
        for i, step in enumerate(steps):
            action = step.get("action", "")
            sel = step.get("selector", "")
            val = step.get("value", "")
            hint = step.get("hint", "")
            try:
                if action == "navigate":
                    self.navigate(val)
                elif action == "click":
                    if sel:
                        self.click(sel)
                    elif hint:
                        text_sel = f"button:has-text('{hint}'), a:has-text('{hint}')"
                        self.click(text_sel)
                elif action == "fill":
                    if sel and val:
                        self.fill(sel, val)
                elif action == "confirm":
                    self.click("button:has-text('Подтвердить'), button:has-text('Оформить'), "
                              "button:has-text('Заказать'), button[type='submit']")
                elif action == "detect":
                    # Автоопределение — возвращаем элементы для ручного выбора
                    return {
                        "step": i + 1,
                        "total_steps": len(steps),
                        "action": "pause_for_user",
                        "hint": hint or f"Шаг {i+1}: выберите элемент для взаимодействия",
                        "page_state": self.get_page_state(),
                        "message": "Авточекаут на паузе. Укажите селектор для следующего шага.",
                    }
                elif action == "pause":
                    return {
                        "step": i + 1,
                        "total_steps": len(steps),
                        "action": "pause_for_user",
                        "hint": hint,
                        "url": self._page.url,
                        "message": f"Чекаут на паузе на шаге {i+1}/{len(steps)}.",
                    }
                completed_steps.append({"step": i + 1, "action": action, "status": "done"})
            except Exception as e:
                completed_steps.append({"step": i + 1, "action": action,
                                       "status": "error", "error": str(e)})
                if not auto_continue:
                    return {"completed_steps": completed_steps, "error": str(e),
                            "hint": "Исправьте ошибку и продолжите с текущего шага."}
        return {
            "success": True,
            "completed_steps": completed_steps,
            "total_steps": len(steps),
            "url": self._page.url,
        }

    def smart_captcha_detect(self) -> dict[str, Any]:
        """
        Обнаружение капчи на странице.
        Ищет reCAPTCHA, hCaptcha, Cloudflare и текстовые капчи.
        """
        if self._page is None:
            return {"error": "Браузер не запущен"}
        try:
            detections = []
            # reCAPTCHA v2/v3
            recaptcha = self._page.locator(
                ".g-recaptcha, iframe[src*='recaptcha'], iframe[src*='google.com/recaptcha'], "
                "[data-sitekey], script[src*='recaptcha']"
            )
            if recaptcha.count() > 0:
                detections.append({"type": "reCAPTCHA", "provider": "Google"})
            # hCaptcha
            hcaptcha = self._page.locator(
                ".h-captcha, iframe[src*='hcaptcha'], script[src*='hcaptcha']"
            )
            if hcaptcha.count() > 0:
                detections.append({"type": "hCaptcha", "provider": "hCaptcha"})
            # Cloudflare Turnstile
            turnstile = self._page.locator(
                ".cf-turnstile, script[src*='challenges.cloudflare.com']"
            )
            if turnstile.count() > 0:
                detections.append({"type": "Turnstile", "provider": "Cloudflare"})
            # Текстовая / простая капча
            text_captcha = self._page.locator(
                "img[src*='captcha'], input[name*='captcha'], "
                "#captcha, .captcha, [id*='captcha']"
            )
            if text_captcha.count() > 0:
                detections.append({"type": "TextCaptcha", "provider": "site"})
            if detections:
                return {
                    "captcha_detected": True,
                    "detections": detections,
                    "count": len(detections),
                    "message": "Обнаружена капча. Требуется ручное решение.",
                    "action_required": "user",
                }
            return {"captcha_detected": False, "message": "Капча не обнаружена"}
        except PlaywrightError as e:
            return {"error": f"Ошибка обнаружения капчи: {str(e)}"}


# ═══════════════════════════════════════════════════════════════════════════
# Совместимость со старым API
# ═══════════════════════════════════════════════════════════════════════════

# Глобальная сессия для обратной совместимости
_global_session: Optional[BrowserSession] = None


def get_browser_session(
    headless: bool = True,
    storage_state_path: str = STORAGE_STATE_PATH,
) -> BrowserSession:
    """Получить или создать глобальную сессию браузера."""
    global _global_session
    if _global_session is None or not _global_session.is_running:
        _global_session = BrowserSession(
            headless=headless,
            storage_state_path=storage_state_path,
        )
    return _global_session


def dispose_browser_session() -> None:
    """Закрыть глобальную сессию браузера."""
    global _global_session
    if _global_session is not None:
        _global_session.close()
        _global_session = None


# PlaywrightBrowserService — обёртка над BrowserSession с API, совместимым с agent_service.py
class PlaywrightBrowserService:
    """Обёртка, предоставляющая интерфейс ожидаемый agent_service.py и chat_service.py."""

    _SESSION_KWARGS = {"headless", "storage_state_path", "browser_type"}

    def __init__(self, **kwargs) -> None:
        session_kwargs = {k: v for k, v in kwargs.items() if k in self._SESSION_KWARGS}
        self._session = BrowserSession(**session_kwargs)

    def available(self) -> bool:
        """Проверить, доступен ли Playwright (установлен ли пакет и браузер)."""
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            return False
        return True

    def close(self) -> None:
        self._session.close()

    def snapshot(self) -> dict:
        """Обратная совместимость: browser_snapshot → get_page_state()."""
        return self._session.get_page_state()

    def fetch_as_http(self, url: str, timeout_seconds: int = 30) -> tuple[int, str, str]:
        """Playwright-совместимый fetcher для BrowserWorkflowService."""
        try:
            nav = self._session.navigate(url)
        except PlaywrightUnavailableError:
            raise
        error = nav.get("error", "")
        if error:
            return 0, error, url
        html_result = self._session.get_html()
        html = html_result.get("html", "")
        final_url = str(nav.get("url", url))
        return 200, html, final_url

    # --- Прокси-методы с трансляцией параметров ---

    def navigate(self, url: str, timeout_seconds: int = 30, wait_until: str = "domcontentloaded", **kwargs) -> dict:
        # BrowserSession.navigate игнорирует timeout_seconds/wait_until (свои defaults)
        return self._session.navigate(url)

    def get_page_state(self, include_html: bool = False, max_elements: int = 50, **kwargs) -> dict:
        return self._session.get_page_state()

    def click(self, selector: str = "", text: str = "", index=None, confirmed: bool = False, **kwargs) -> dict:
        return self._session.click(selector or text)

    def fill(self, selector: str = "", value: str = "", index=None, clear_first: bool = True, **kwargs) -> dict:
        return self._session.fill(selector, value)

    def get_text(self, selector: str = "", max_chars: int = 10000, **kwargs) -> dict:
        result = self._session.get_text(selector or None)
        if max_chars and isinstance(result.get("text"), str):
            result["text"] = result["text"][:max_chars]
        return result

    def screenshot(self, selector: str = "", full_page: bool = False, project_id: str = "", **kwargs) -> dict:
        return self._session.screenshot(full_page=full_page)

    def evaluate_js(self, expression: str = "", **kwargs) -> dict:
        return self._session.evaluate_js(expression)

    def wait_for(self, selector: str = "", state: str = "visible", timeout_seconds: int = 10, **kwargs) -> dict:
        return self._session.wait_for(selector, timeout=timeout_seconds * 1000)

    def smart_login(self, url: str = "", username: str = "", password: str = "",
                    extra_fields=None, submit_text: str = "", **kwargs) -> dict:
        creds = {"username": username, "password": password}
        if isinstance(extra_fields, dict):
            creds.update(extra_fields)
        if submit_text:
            creds["submit_text"] = submit_text
        return self._session.smart_login(url, credentials=creds if any(creds.values()) else None)

    def smart_search(self, query: str = "", url: str = "", max_results: int = 10,
                     extract_cards: bool = True, **kwargs) -> dict:
        return self._session.smart_search(query, url=url or None)

    def smart_add_to_cart(self, product_name: str = "", confirmed: bool = False,
                          quantity=None, **kwargs) -> dict:
        return self._session.smart_add_to_cart(product_name)

    def manage_allowed_domains(self, add: str = "", remove: str = "",
                               list_domains: bool = False, **kwargs) -> dict:
        if add:
            return self._session.allow_domain(add)
        if remove:
            return self._session.revoke_domain(remove)
        if list_domains:
            return self._session.get_allowed_domains()
        return {"error": "Укажите add, remove или list_domains=True"}

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 1: базовые примитивы
    # ═══════════════════════════════════════════════════════════════════════

    def scroll(self, amount: int = 300, direction: str = "down",
               selector: str = "", **kwargs) -> dict:
        return self._session.scroll(amount=amount, direction=direction, selector=selector)

    def hover(self, selector: str = "", **kwargs) -> dict:
        return self._session.hover(selector)

    def double_click(self, selector: str = "", **kwargs) -> dict:
        return self._session.double_click(selector)

    def right_click(self, selector: str = "", **kwargs) -> dict:
        return self._session.right_click(selector)

    def type_text(self, selector: str = "", text: str = "",
                  delay: int = 50, **kwargs) -> dict:
        return self._session.type_text(selector, text, delay=delay)

    def press_key(self, key: str = "", selector: str = "", **kwargs) -> dict:
        return self._session.press_key(key, selector=selector)

    def drag(self, source_selector: str = "", target_selector: str = "", **kwargs) -> dict:
        return self._session.drag(source_selector, target_selector)

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 2: мульти-табы
    # ═══════════════════════════════════════════════════════════════════════

    def new_tab(self, url: str = "", **kwargs) -> dict:
        return self._session.new_tab(url)

    def switch_tab(self, index: int = 0, **kwargs) -> dict:
        return self._session.switch_tab(index)

    def close_tab(self, index: int = -1, **kwargs) -> dict:
        return self._session.close_tab(index)

    def list_tabs(self, **kwargs) -> dict:
        return self._session.list_tabs()

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 3: диалоги, загрузки, хранилище
    # ═══════════════════════════════════════════════════════════════════════

    def handle_dialog(self, action: str = "accept", prompt_text: str = "", **kwargs) -> dict:
        return self._session.handle_dialog(action, prompt_text=prompt_text)

    def upload_file(self, selector: str = "", file_path: str = "", **kwargs) -> dict:
        return self._session.upload_file(selector, file_path)

    def cookies(self, action: str = "get", cookie_data: dict = None, **kwargs) -> dict:
        return self._session.cookies(action, cookie_data=cookie_data)

    def local_storage(self, action: str = "get", key: str = "",
                      value: str = "", **kwargs) -> dict:
        return self._session.local_storage(action, key=key, value=value)

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 4: визуальный режим
    # ═══════════════════════════════════════════════════════════════════════

    def screenshot_element(self, selector: str = "", **kwargs) -> dict:
        return self._session.screenshot_element(selector)

    def element_som(self, max_elements: int = 30, selector: str = "", **kwargs) -> dict:
        return self._session.element_som(selector=selector, max_elements=max_elements)

    def visual_qa(self, question: str = "", selector: str = "", **kwargs) -> dict:
        return self._session.visual_qa(question, selector=selector)

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 5: сеть и iframe
    # ═══════════════════════════════════════════════════════════════════════

    def network_requests(self, action: str = "list", url_filter: str = "", **kwargs) -> dict:
        return self._session.network_requests(action, url_filter=url_filter)

    def iframe_switch(self, action: str = "list", selector: str = "", **kwargs) -> dict:
        return self._session.iframe_switch(selector=selector, action=action)

    def device_emulate(self, device: str = "iPhone 15", **kwargs) -> dict:
        return self._session.device_emulate(device)

    # ═══════════════════════════════════════════════════════════════════════
    # Фаза 6: смарт-тулы v2
    # ═══════════════════════════════════════════════════════════════════════

    def smart_form(self, url: str = "", fields: dict = None, **kwargs) -> dict:
        return self._session.smart_form(url, fields=fields or {})

    def smart_extract(self, extract_type: str = "tables",
                      selector: str = "", **kwargs) -> dict:
        return self._session.smart_extract(extract_type, selector=selector)

    def smart_checkout(self, url: str = "", steps: list = None,
                       auto_continue: bool = False, **kwargs) -> dict:
        return self._session.smart_checkout(url, steps=steps, auto_continue=auto_continue)

    def smart_captcha_detect(self, **kwargs) -> dict:
        return self._session.smart_captcha_detect()
