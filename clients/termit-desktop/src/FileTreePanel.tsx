import { useCallback, useEffect, useMemo, useState } from "react";
import type { TermitClient } from "@termit/client";

interface FileTreePanelProps {
  client: TermitClient;
  connected: boolean;
  selectedPath?: string | null;
  onSelectFile: (path: string) => void;
}

const SKIP_DIRS = new Set(["node_modules", ".git", ".venv", "dist", "release", "__pycache__"]);

function filterPaths(files: string[]): string[] {
  return files.filter((file) => {
    const parts = file.split("/");
    return !parts.some((part) => SKIP_DIRS.has(part));
  });
}

export function FileTreePanel({
  client,
  connected,
  selectedPath,
  onSelectFile,
}: FileTreePanelProps) {
  const [files, setFiles] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await client.listFiles({ path: ".", pattern: "*" });
      setFiles(filterPaths(response.files));
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    } finally {
      setLoading(false);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const visible = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) {
      return files.slice(0, 400);
    }
    return files.filter((file) => file.toLowerCase().includes(query)).slice(0, 400);
  }, [files, filter]);

  return (
    <aside className="file-tree" aria-label="Workspace files">
      <div className="file-tree-header">
        <strong>Файлы</strong>
        <button type="button" className="secondary compact" disabled={!connected || loading} onClick={() => void refresh()}>
          ↻
        </button>
      </div>
      <input
        className="file-tree-filter"
        placeholder="Фильтр…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      {error && <p className="hint error-text">{error}</p>}
      <div className="file-tree-list">
        {visible.length === 0 ? (
          <div className="muted file-tree-empty">{loading ? "Загрузка…" : "Нет файлов"}</div>
        ) : (
          visible.map((file) => (
            <button
              key={file}
              type="button"
              className={`file-tree-item ${selectedPath === file ? "selected" : ""}`}
              onClick={() => onSelectFile(file)}
              title={file}
            >
              {file}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
