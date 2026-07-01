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

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError,
)

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
        # Упрощённая версия: сбрасываем счётчик подтверждений
        return {"success": True, "message": "Действие подтверждено"}


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


# Для обратной совместимости: PlaywrightBrowserService — псевдоним
PlaywrightBrowserService = BrowserSession
