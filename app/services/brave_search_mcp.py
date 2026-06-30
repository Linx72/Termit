"""
BraveSearch MCP Client — Python STDIO-клиент для brave-search-mcp-server.

Запускает Node.js subprocess, общается через JSON-RPC поверх STDIO.
Использует тот же подход, что и whisperManager.ts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger("termit.brave_search_mcp")

# ── Конфигурация ──────────────────────────────────────────────────

DEFAULT_MCP_PACKAGE = "@brave/brave-search-mcp-server"
DEFAULT_NODE_BIN = "node"
REQUEST_TIMEOUT_SEC = 30.0
STARTUP_TIMEOUT_SEC = 15.0


@dataclass
class BraveSearchResult:
    """Результат поиска (унифицированный)."""
    title: str
    url: str
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ── MCP STDIO Client ──────────────────────────────────────────────


class BraveSearchMcpError(Exception):
    """Ошибка взаимодействия с MCP-сервером."""


class BraveSearchMcpClient:
    """
    Python MCP-клиент поверх STDIO для brave-search-mcp-server.

    Использование:
        client = BraveSearchMcpClient()
        await client.start()
        results = await client.web_search("python async tutorial")
        await client.stop()
    """

    def __init__(
        self,
        api_key: str | None = None,
        node_bin: str = DEFAULT_NODE_BIN,
        mcp_package: str = DEFAULT_MCP_PACKAGE,
    ):
        self._api_key = api_key or os.getenv("BRAVE_API_KEY", "")
        self._node_bin = node_bin
        self._mcp_package = mcp_package
        self._proc: subprocess.Popen | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._initialized = False

    # ── Управление жизненным циклом ────────────────────────────

    async def start(self) -> None:
        """Запустить MCP-сервер и инициализировать соединение."""
        if self._proc is not None:
            return

        bin_path = self._find_binary()
        env = os.environ.copy()
        env["BRAVE_API_KEY"] = self._api_key

        _logger.info("Запуск MCP-сервера: %s", bin_path)

        self._proc = subprocess.Popen(
            [self._node_bin, bin_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=False,  # bytes mode
        )

        # Запускаем reader
        self._reader_task = asyncio.create_task(self._read_responses())

        # Инициализация MCP
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "TermitPro", "version": "1.0.0"},
        })
        self._initialized = True
        _logger.info("MCP-сервер инициализирован")

    async def stop(self) -> None:
        """Остановить MCP-сервер."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.stdout.close()
            except Exception:
                _logger.debug("Cleanup: closing MCP stdin/stdout failed", exc_info=True)
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(BraveSearchMcpError("Сервер остановлен"))
        self._pending.clear()
        self._initialized = False

    # ── Инструменты поиска ─────────────────────────────────────

    async def web_search(
        self,
        query: str,
        count: int = 10,
        offset: int = 0,
        country: str = "",
        search_lang: str = "",
    ) -> list[dict[str, Any]]:
        """Веб-поиск через brave_web_search."""
        args = {"query": query, "count": count}
        if offset:
            args["offset"] = offset
        if country:
            args["country"] = country
        if search_lang:
            args["search_lang"] = search_lang
        return await self._call_tool("brave_web_search", args)

    async def local_search(
        self,
        query: str,
        count: int = 5,
        country: str = "",
    ) -> list[dict[str, Any]]:
        """Локальный поиск (бизнес/POI) через brave_local_search."""
        args = {"query": query, "count": count}
        if country:
            args["country"] = country
        return await self._call_tool("brave_local_search", args)

    async def image_search(
        self,
        query: str,
        count: int = 10,
        country: str = "",
        safe_search: str = "moderate",
    ) -> list[dict[str, Any]]:
        """Поиск изображений через brave_image_search."""
        args = {"query": query, "count": count, "safe_search": safe_search}
        if country:
            args["country"] = country
        return await self._call_tool("brave_image_search", args)

    async def video_search(
        self,
        query: str,
        count: int = 10,
        country: str = "",
    ) -> list[dict[str, Any]]:
        """Поиск видео через brave_video_search."""
        args = {"query": query, "count": count}
        if country:
            args["country"] = country
        return await self._call_tool("brave_video_search", args)

    async def news_search(
        self,
        query: str,
        count: int = 10,
        freshness: str = "",
        country: str = "",
    ) -> list[dict[str, Any]]:
        """Поиск новостей через brave_news_search."""
        args = {"query": query, "count": count}
        if freshness:
            args["freshness"] = freshness
        if country:
            args["country"] = country
        return await self._call_tool("brave_news_search", args)

    async def place_search(
        self,
        query: str,
        country: str = "",
        search_lang: str = "",
    ) -> list[dict[str, Any]]:
        """Поиск мест через brave_place_search."""
        args = {"query": query}
        if country:
            args["country"] = country
        if search_lang:
            args["search_lang"] = search_lang
        return await self._call_tool("brave_place_search", args)

    # ── Внутренние методы ──────────────────────────────────────

    def _find_binary(self) -> str:
        """Найти бинарник brave-search-mcp-server."""
        # 1. npx (глобально)
        # 2. node_modules в desktop-клиенте
        # 3. node_modules в корне проекта
        
        candidates = [
            Path(__file__).resolve().parent.parent.parent
            / "clients/termit-desktop/node_modules/.bin/brave-search-mcp-server",
            Path(__file__).resolve().parent.parent.parent
            / "node_modules/.bin/brave-search-mcp-server",
        ]
        
        for p in candidates:
            if p.exists():
                return str(p)

        # Пробуем npx
        try:
            result = subprocess.run(
                ["npx", "which", self._mcp_package],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

        raise BraveSearchMcpError(
            "brave-search-mcp-server не найден. "
            "Установите: cd clients/termit-desktop && npm install @brave/brave-search-mcp-server"
        )

    async def _read_responses(self) -> None:
        """Читать JSON-RPC ответы из STDOUT процесса."""
        assert self._proc and self._proc.stdout
        
        buffer = b""
        while True:
            try:
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, self._proc.stdout.read, 4096
                )
                if not chunk:
                    break
                buffer += chunk
                
                # Обработка всех полных JSON-строк
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            self._handle_message(msg)
                        except json.JSONDecodeError:
                            _logger.warning("Невалидный JSON от MCP: %s", line[:200])
            except asyncio.CancelledError:
                break
            except Exception:
                _logger.warning("Unexpected error in MCP reader loop, stopping", exc_info=True)
                break

    def _handle_message(self, msg: dict) -> None:
        """Обработать одно JSON-RPC сообщение."""
        msg_id = msg.get("id")
        
        if msg_id is not None and msg_id in self._pending:
            fut = self._pending.pop(msg_id)
            if "error" in msg:
                fut.set_exception(BraveSearchMcpError(
                    f"MCP Error {msg['error'].get('code', '?')}: {msg['error'].get('message', 'unknown')}"
                ))
            else:
                fut.set_result(msg.get("result", {}))
        elif "method" in msg:
            # Серверное уведомление (не запрос) — игнорируем
            pass
        else:
            _logger.debug("MCP: неизвестное сообщение id=%s", msg_id)

    async def _send_request(self, method: str, params: dict) -> Any:
        """Отправить JSON-RPC запрос и дождаться ответа."""
        assert self._proc and self._proc.stdin
        
        self._request_id += 1
        msg_id = self._request_id
        
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        }) + "\n"
        
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        
        try:
            self._proc.stdin.write(request.encode())
            self._proc.stdin.flush()
        except BrokenPipeError as e:
            raise BraveSearchMcpError("Сервер MCP не отвечает (broken pipe)") from e
        
        try:
            return await asyncio.wait_for(fut, timeout=REQUEST_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise BraveSearchMcpError(f"Таймаут запроса {method} ({REQUEST_TIMEOUT_SEC}с)")

    async def _call_tool(self, name: str, arguments: dict) -> list[dict[str, Any]]:
        """Вызвать MCP-инструмент."""
        if not self._initialized:
            await self.start()

        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        
        # MCP возвращает content array
        content = result.get("content", [])
        if not content:
            return []
        
        # Первый элемент обычно текст (JSON-строка с результатами)
        text = content[0].get("text", "[]") if content else "[]"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return [{"raw": text}]


# ── Синглтон ──────────────────────────────────────────────────────

_client: BraveSearchMcpClient | None = None
_lock = asyncio.Lock()


async def get_brave_search_client() -> BraveSearchMcpClient:
    """Получить или создать singleton MCP-клиент."""
    global _client
    
    async with _lock:
        if _client is None:
            _client = BraveSearchMcpClient()
            await _client.start()
        return _client


async def shutdown_brave_search_client() -> None:
    """Остановить MCP-клиент (graceful shutdown)."""
    global _client
    if _client:
        await _client.stop()
        _client = None
