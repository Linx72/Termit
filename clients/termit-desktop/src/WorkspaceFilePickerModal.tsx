import { useEffect, useMemo, useState } from "react";
import type { TermitClient } from "@termit/client";

interface WorkspaceFilePickerModalProps {
  client: TermitClient;
  connected: boolean;
  title: string;
  open: boolean;
  mode?: "file" | "folder";
  onClose: () => void;
  onSelect: (path: string) => void;
}

const SKIP_DIRS = new Set(["node_modules", ".git", ".venv", "dist", "release", "__pycache__"]);

function isSkippable(path: string): boolean {
  return path.split("/").some((part) => SKIP_DIRS.has(part));
}

export function WorkspaceFilePickerModal({
  client,
  connected,
  title,
  open,
  mode = "file",
  onClose,
  onSelect,
}: WorkspaceFilePickerModalProps) {
  const [files, setFiles] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !connected) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const listed = await client.listFiles({ path: ".", pattern: "*" });
        if (cancelled) {
          return;
        }
        setFiles(listed.files.filter((item) => !item.endsWith("/") && !isSkippable(item)));
      } catch (err) {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, connected, client]);

  useEffect(() => {
    if (!open) {
      setFilter("");
      setError("");
    }
  }, [open]);

  const visible = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (mode === "folder") {
      const dirs = new Set<string>(["."]);
      for (const file of files) {
        const parts = file.split("/");
        if (parts.length <= 1) {
          continue;
        }
        let current = "";
        for (const part of parts.slice(0, -1)) {
          current = current ? `${current}/${part}` : part;
          dirs.add(current);
        }
      }
      const values = [...dirs];
      if (!query) {
        return values.slice(0, 500);
      }
      return values.filter((item) => item.toLowerCase().includes(query)).slice(0, 500);
    }
    if (!query) {
      return files.slice(0, 500);
    }
    return files.filter((item) => item.toLowerCase().includes(query)).slice(0, 500);
  }, [files, filter, mode]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal workspace-picker-modal" role="dialog" onClick={(event) => event.stopPropagation()}>
        <h3>{title}</h3>
        <input
          className="file-tree-filter"
          autoFocus
          placeholder={mode === "folder" ? "Filter folders…" : "Filter files…"}
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        {error ? <p className="hint error-text">{error}</p> : null}
        <div className="workspace-picker-list">
          {visible.length === 0 ? (
            <div className="file-tree-empty muted">{loading ? "Loading…" : mode === "folder" ? "No folders" : "No files"}</div>
          ) : (
            visible.map((path) => (
              <button
                key={path}
                type="button"
                className="file-tree-item"
                title={path}
                onClick={() => {
                  onSelect(path);
                  onClose();
                }}
              >
                {path}
              </button>
            ))
          )}
        </div>
        <div className="row">
          <button type="button" className="secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
