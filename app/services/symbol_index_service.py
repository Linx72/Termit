from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class SymbolRecord:
    name: str
    kind: str
    path: str
    line: int


@dataclass(frozen=True)
class CallEdge:
    caller_name: str
    caller_path: str
    caller_line: int
    callee_name: str
    path: str
    line: int


class SymbolIndexService:
    _SKIP_DIRS = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
    }
    _PY_SUFFIX = {".py"}
    _JS_SUFFIX = {".ts", ".tsx", ".js", ".jsx"}

    def __init__(self, root_path: str = ".") -> None:
        self.root = Path(root_path).resolve()
        self._lock = Lock()
        self._symbols: list[SymbolRecord] = []
        self._imports_by_file: dict[str, list[str]] = {}
        self._call_edges: list[CallEdge] = []

    def reindex(self) -> int:
        symbols: list[SymbolRecord] = []
        imports_by_file: dict[str, list[str]] = {}
        call_edges: list[CallEdge] = []
        for file_path in self._iter_files():
            rel = str(file_path.relative_to(self.root)).replace("\\", "/")
            if file_path.suffix == ".py":
                file_symbols, imports, edges = self._index_python(file_path, rel)
            elif file_path.suffix.lower() in self._JS_SUFFIX:
                file_symbols, imports, edges = self._index_js_like(file_path, rel)
            else:
                continue
            symbols.extend(file_symbols)
            call_edges.extend(edges)
            if imports:
                imports_by_file[rel] = imports
        with self._lock:
            self._symbols = symbols
            self._imports_by_file = imports_by_file
            self._call_edges = call_edges
        return len(symbols)

    def search(self, query: str, *, limit: int = 10, path_prefix: str = "") -> list[SymbolRecord]:
        safe_limit = max(1, min(limit, 30))
        tokens = self._tokenize(query)
        if not tokens:
            return []
        prefix = path_prefix.strip().replace("\\", "/")
        if not self._symbols:
            self.reindex()
        with self._lock:
            candidates = list(self._symbols)

        scored: list[tuple[float, SymbolRecord]] = []
        for record in candidates:
            if prefix and not record.path.startswith(prefix):
                continue
            name_lower = record.name.lower()
            score = 0.0
            for token in tokens:
                if token == name_lower:
                    score += 10.0
                elif token in name_lower:
                    score += 4.0
                elif token in record.path.lower():
                    score += 1.0
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:safe_limit]]

    def callers_of(self, symbol_name: str, *, limit: int = 8) -> list[CallEdge]:
        if not self._call_edges:
            self.reindex()
        needle = symbol_name.strip().lower()
        with self._lock:
            edges = list(self._call_edges)
        matches = [edge for edge in edges if edge.callee_name.lower() == needle]
        return matches[: max(1, min(limit, 20))]

    def callees_of(self, symbol_name: str, *, limit: int = 8) -> list[CallEdge]:
        if not self._call_edges:
            self.reindex()
        needle = symbol_name.strip().lower()
        with self._lock:
            edges = list(self._call_edges)
        matches = [edge for edge in edges if edge.caller_name.lower() == needle]
        return matches[: max(1, min(limit, 20))]

    @staticmethod
    def format_graph_ref(path: str, line: int, name: str) -> str:
        return f"{path}:{line}:{name}"

    def neighbor_paths(self, seed_paths: list[str], *, limit: int = 8) -> list[str]:
        if not seed_paths:
            return []
        if not self._imports_by_file:
            self.reindex()
        with self._lock:
            imports_map = dict(self._imports_by_file)

        neighbors: list[str] = []
        seen = set(seed_paths)
        module_to_paths = self._module_path_index()

        for rel_path in seed_paths:
            for imported in imports_map.get(rel_path, []):
                for candidate in module_to_paths.get(imported, []):
                    if candidate not in seen:
                        seen.add(candidate)
                        neighbors.append(candidate)
            stem = Path(rel_path).stem
            for mod, paths in module_to_paths.items():
                if stem in mod.split("."):
                    for candidate in paths:
                        if candidate not in seen:
                            seen.add(candidate)
                            neighbors.append(candidate)
            if len(neighbors) >= limit:
                break
        return neighbors[:limit]

    def _module_path_index(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for file_path in self._iter_files():
            rel = str(file_path.relative_to(self.root)).replace("\\", "/")
            if file_path.suffix != ".py":
                continue
            module = rel[:-3].replace("/", ".")
            mapping.setdefault(module, []).append(rel)
            mapping.setdefault(Path(rel).stem, []).append(rel)
        return mapping

    def _index_python(self, file_path: Path, rel: str) -> tuple[list[SymbolRecord], list[str], list[CallEdge]]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            return [], [], []

        symbols: list[SymbolRecord] = []
        imports: list[str] = []
        call_edges: list[CallEdge] = []
        scope_stack: list[str] = []

        class _Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                scope_stack.append(node.name)
                symbols.append(SymbolRecord(node.name, "function", rel, node.lineno))
                self.generic_visit(node)
                scope_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                scope_stack.append(node.name)
                symbols.append(SymbolRecord(node.name, "async_function", rel, node.lineno))
                self.generic_visit(node)
                scope_stack.pop()

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                symbols.append(SymbolRecord(node.name, "class", rel, node.lineno))
                self.generic_visit(node)

            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    imports.append(alias.name)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    imports.append(node.module)

            def visit_Call(self, node: ast.Call) -> None:
                callee = self._call_name(node.func)
                if callee and scope_stack:
                    caller = scope_stack[-1]
                    call_edges.append(
                        CallEdge(
                            caller_name=caller,
                            caller_path=rel,
                            caller_line=node.lineno,
                            callee_name=callee,
                            path=rel,
                            line=node.lineno,
                        )
                    )
                self.generic_visit(node)

            @staticmethod
            def _call_name(node: ast.AST) -> str | None:
                if isinstance(node, ast.Name):
                    return node.id
                if isinstance(node, ast.Attribute):
                    return node.attr
                return None

        _Visitor().visit(tree)
        return symbols, imports, call_edges

    def _index_js_like(self, file_path: Path, rel: str) -> tuple[list[SymbolRecord], list[str], list[CallEdge]]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], [], []
        symbols: list[SymbolRecord] = []
        imports: list[str] = []
        for match in re.finditer(
            r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)",
            text,
            re.MULTILINE,
        ):
            symbols.append(SymbolRecord(match.group(1), "function", rel, text[: match.start()].count("\n") + 1))
        for match in re.finditer(
            r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)",
            text,
            re.MULTILINE,
        ):
            symbols.append(SymbolRecord(match.group(1), "class", rel, text[: match.start()].count("\n") + 1))
        for match in re.finditer(r"""from\s+['"]([^'"]+)['"]""", text):
            imports.append(match.group(1))
        return symbols, imports, []

    def _iter_files(self) -> list[Path]:
        files: list[Path] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in self._SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in self._PY_SUFFIX and path.suffix.lower() not in self._JS_SUFFIX:
                continue
            try:
                if path.stat().st_size > 200_000:
                    continue
            except OSError:
                continue
            files.append(path)
        return files

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", query)]
