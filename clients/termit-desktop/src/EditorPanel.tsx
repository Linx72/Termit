import { useCallback, useEffect, useRef, useState } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import {
  TermitClient,
  computePatchedContent,
  fetchInlineEditPatch,
  requestTabCompletion,
  type ApplyPatchRequest,
} from "@termit/client";
import { languageFromPath } from "./editorUtils";
import { FileTreePanel } from "./FileTreePanel";
import { WorkspaceFilePickerModal } from "./WorkspaceFilePickerModal";

interface EditorPanelProps {
  client: TermitClient;
  connected: boolean;
  workspace: string;
  selectedModel: string;
  sessionId: string;
  inlineCompletionEnabled?: boolean;
  onSessionId: (id: string) => void;
  openPath?: string | null;
  onOpenPathConsumed?: () => void;
}

type ModalKind = "inline-edit" | "diff-preview" | null;

export function EditorPanel({
  client,
  connected,
  workspace,
  selectedModel,
  sessionId,
  inlineCompletionEnabled = false,
  onSessionId,
  openPath,
  onOpenPathConsumed,
}: EditorPanelProps) {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("Open a workspace file to edit.");
  const [modal, setModal] = useState<ModalKind>(null);
  const [instruction, setInstruction] = useState("");
  const [inlineBusy, setInlineBusy] = useState(false);
  const [pendingPatch, setPendingPatch] = useState<ApplyPatchRequest | null>(null);
  const [previewOld, setPreviewOld] = useState("");
  const [previewNew, setPreviewNew] = useState("");
  const [patchDetail, setPatchDetail] = useState("");
  const [showFilePicker, setShowFilePicker] = useState(false);

  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const suppressDirtyRef = useRef(false);
  const completionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completionDisposableRef = useRef<{ dispose: () => void } | null>(null);

  const openFileAtPath = useCallback(
    async (relativePath: string) => {
      try {
        setStatus(`Loading ${relativePath}…`);
        const file = await client.readFile({ path: relativePath, max_bytes: 500_000 });
        suppressDirtyRef.current = true;
        setFilePath(relativePath);
        setContent(file.content);
        setDirty(false);
        setStatus(`Opened ${relativePath}`);
      } catch (error) {
        const text = error instanceof Error ? error.message : String(error);
        setStatus(text);
      }
    },
    [client]
  );

  const openFile = useCallback(async () => {
    if (!workspace) {
      setStatus("Choose a workspace folder first.");
      return;
    }
    setShowFilePicker(true);
  }, [workspace, openFileAtPath]);

  useEffect(() => {
    if (!openPath) {
      return;
    }
    void openFileAtPath(openPath).finally(() => {
      onOpenPathConsumed?.();
    });
  }, [openPath, openFileAtPath, onOpenPathConsumed]);

  const reloadFile = useCallback(async () => {
    if (!filePath) {
      return;
    }
    try {
      const file = await client.readFile({ path: filePath, max_bytes: 500_000 });
      suppressDirtyRef.current = true;
      setContent(file.content);
      setDirty(false);
      setStatus(`Reloaded ${filePath}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    }
  }, [filePath, client]);

  const saveFile = useCallback(async () => {
    if (!filePath || !connected) {
      return;
    }
    try {
      setStatus("Saving…");
      const result = await client.applyPatch({
        path: filePath,
        content,
        confirmed: true,
        dry_run: false,
      });
      if (!result.applied) {
        throw new Error(result.policy_reason ?? "Save was not applied.");
      }
      setDirty(false);
      setStatus(`Saved ${filePath}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    }
  }, [filePath, content, connected, client]);

  const startInlineEdit = useCallback(() => {
    const editor = editorRef.current;
    if (!editor || !filePath) {
      setStatus("Open a file and select code for inline edit.");
      return;
    }
    const selection = editor.getSelection();
    if (!selection || selection.isEmpty()) {
      setStatus("Select code, then press Cmd+K (Ctrl+K) for inline edit.");
      return;
    }
    const model = editor.getModel();
    if (!model) {
      return;
    }
    const selectedText = model.getValueInRange(selection);
    if (!selectedText.trim()) {
      setStatus("Selection is empty.");
      return;
    }
    setInstruction("");
    setModal("inline-edit");
  }, [filePath]);

  const runInlineEdit = useCallback(async () => {
    const editor = editorRef.current;
    if (!editor || !filePath || !instruction.trim() || inlineBusy) {
      return;
    }
    const selection = editor.getSelection();
    const model = editor.getModel();
    if (!selection || !model) {
      return;
    }
    const selectedText = model.getValueInRange(selection);
    const languageId = languageFromPath(filePath);

    setInlineBusy(true);
    setStatus("Running inline edit…");
    try {
      const { patch: patchRequest, sessionId: nextSessionId } = await fetchInlineEditPatch(client, {
        instruction: instruction.trim(),
        filePath,
        languageId,
        selectedText,
        sessionId: sessionId || undefined,
        model: selectedModel || undefined,
      });

      if (nextSessionId) {
        onSessionId(nextSessionId);
      }

      const patched = computePatchedContent(content, patchRequest);
      const dryRun = await client.applyPatch({
        ...patchRequest,
        dry_run: true,
        confirmed: false,
      });

      setPendingPatch(patchRequest);
      setPreviewOld(content);
      setPreviewNew(patched);
      setPatchDetail(
        [
          `path: ${filePath}`,
          `risk: ${dryRun.risk_level}`,
          dryRun.policy_reason ? `policy: ${dryRun.policy_reason}` : "",
          dryRun.preview_excerpt ? `preview:\n${dryRun.preview_excerpt}` : "",
        ]
          .filter(Boolean)
          .join("\n")
      );
      setModal("diff-preview");
      setStatus("Inline edit ready — review diff.");
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    } finally {
      setInlineBusy(false);
    }
  }, [
    filePath,
    instruction,
    inlineBusy,
    content,
    client,
    sessionId,
    selectedModel,
    onSessionId,
  ]);

  const applyPendingPatch = useCallback(async () => {
    if (!pendingPatch) {
      return;
    }
    try {
      setStatus("Applying patch…");
      const result = await client.applyPatch({
        ...pendingPatch,
        dry_run: false,
        confirmed: true,
      });
      if (!result.applied) {
        throw new Error(result.policy_reason ?? "Patch was not applied.");
      }
      setContent(previewNew);
      suppressDirtyRef.current = true;
      setDirty(false);
      setModal(null);
      setPendingPatch(null);
      setStatus(`Applied patch to ${pendingPatch.path}`);
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      setStatus(text);
    }
  }, [pendingPatch, previewNew, client]);

  const handleEditorMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    completionDisposableRef.current?.dispose();
    if (inlineCompletionEnabled && connected) {
      completionDisposableRef.current = monaco.languages.registerInlineCompletionsProvider(
        { pattern: "**/*" },
        {
          provideInlineCompletions: async (model, position, _context, token) => {
            const line = model.getLineContent(position.lineNumber);
            const prefix = line.slice(0, position.column - 1);
            if (prefix.trim().length < 12) {
              return { items: [] };
            }

            const startLine = Math.max(1, position.lineNumber - 25);
            const endLine = Math.min(model.getLineCount(), position.lineNumber + 8);
            const before = model.getValueInRange(
              new monaco.Range(startLine, 1, position.lineNumber, position.column)
            );
            const after = model.getValueInRange(
              new monaco.Range(
                position.lineNumber,
                position.column,
                endLine,
                model.getLineMaxColumn(endLine)
              )
            );

            return new Promise((resolve) => {
              if (completionTimerRef.current) {
                clearTimeout(completionTimerRef.current);
              }
              completionTimerRef.current = setTimeout(async () => {
                if (token.isCancellationRequested) {
                  resolve({ items: [] });
                  return;
                }
                try {
                  const insertText = await requestTabCompletion(client, before, after, {
                    model: selectedModel || undefined,
                    task_type: "coding",
                  });
                  if (!insertText || token.isCancellationRequested) {
                    resolve({ items: [] });
                    return;
                  }
                  resolve({
                    items: [
                      {
                        insertText,
                        range: new monaco.Range(
                          position.lineNumber,
                          position.column,
                          position.lineNumber,
                          position.column
                        ),
                      },
                    ],
                  });
                } catch {
                  resolve({ items: [] });
                }
              }, 400);
            });
          },
        }
      );
    }

    editor.addAction({
      id: "termit-inline-edit",
      label: "Termit Inline Edit",
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK],
      run: () => {
        startInlineEdit();
      },
    });

    editor.onDidChangeModelContent(() => {
      if (suppressDirtyRef.current) {
        suppressDirtyRef.current = false;
        return;
      }
      setDirty(true);
    });
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k" && !event.shiftKey && !event.altKey) {
        const target = event.target as HTMLElement | null;
        if (target?.closest(".monaco-editor")) {
          event.preventDefault();
          startInlineEdit();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [startInlineEdit]);

  useEffect(() => {
    return () => {
      completionDisposableRef.current?.dispose();
      if (completionTimerRef.current) {
        clearTimeout(completionTimerRef.current);
      }
    };
  }, []);

  const lang = filePath ? languageFromPath(filePath) : "plaintext";

  return (
    <div className="editor-layout">
      <FileTreePanel
        client={client}
        connected={connected}
        selectedPath={filePath}
        onSelectFile={(path) => void openFileAtPath(path)}
      />
      <div className="editor-panel">
      <div className="editor-toolbar">
        <div className="editor-path">
          {filePath ? (
            <>
              <strong>{filePath}</strong>
              {dirty && <span className="dirty-dot">●</span>}
            </>
          ) : (
            <span className="muted">No file open</span>
          )}
        </div>
        <div className="row editor-actions">
          <button type="button" className="secondary" disabled={!connected} onClick={() => void openFile()}>
            Open file
          </button>
          <button type="button" className="secondary" disabled={!filePath} onClick={() => void reloadFile()}>
            Reload
          </button>
          <button
            type="button"
            className="primary"
            disabled={!filePath || !connected || !dirty}
            onClick={() => void saveFile()}
          >
            Save
          </button>
          <button
            type="button"
            className="secondary"
            disabled={!filePath || !connected}
            onClick={startInlineEdit}
          >
            Inline edit (⌘K)
          </button>
        </div>
      </div>

      <p className="hint editor-hint">{status}</p>

      <div className="monaco-wrap">
        {filePath ? (
          <Editor
            height="100%"
            language={lang}
            theme="vs-dark"
            value={content}
            onChange={(value) => setContent(value ?? "")}
            onMount={handleEditorMount}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: "off",
            }}
          />
        ) : (
          <div className="editor-placeholder">
            Open a workspace file to use Monaco editor and Cmd+K inline edit.
          </div>
        )}
      </div>

      {modal === "inline-edit" && (
        <div className="modal-backdrop" role="presentation" onClick={() => setModal(null)}>
          <div className="modal" role="dialog" onClick={(event) => event.stopPropagation()}>
            <h3>Termit inline edit</h3>
            <p className="hint">Describe the change for the selected code.</p>
            <textarea
              autoFocus
              value={instruction}
              placeholder="Add error handling, rename vars, simplify…"
              onChange={(event) => setInstruction(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  void runInlineEdit();
                }
              }}
            />
            <div className="row">
              <button type="button" className="secondary" onClick={() => setModal(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={!instruction.trim() || inlineBusy}
                onClick={() => void runInlineEdit()}
              >
                {inlineBusy ? "Running…" : "Run"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modal === "diff-preview" && pendingPatch && (
        <div className="modal-backdrop" role="presentation" onClick={() => setModal(null)}>
          <div className="modal modal-wide" role="dialog" onClick={(event) => event.stopPropagation()}>
            <h3>Patch preview — {pendingPatch.path}</h3>
            <pre className="detail-box patch-detail">{patchDetail}</pre>
            <div className="diff-grid">
              <div>
                <div className="diff-label">Before</div>
                <pre className="detail-box diff-box">{previewOld}</pre>
              </div>
              <div>
                <div className="diff-label">After</div>
                <pre className="detail-box diff-box">{previewNew}</pre>
              </div>
            </div>
            <div className="row">
              <button type="button" className="secondary" onClick={() => setModal(null)}>
                Cancel
              </button>
              <button type="button" className="primary" onClick={() => void applyPendingPatch()}>
                Apply patch
              </button>
            </div>
          </div>
        </div>
      )}
      <WorkspaceFilePickerModal
        client={client}
        connected={connected}
        open={showFilePicker}
        title="Select workspace file"
        onClose={() => setShowFilePicker(false)}
        onSelect={(path) => void openFileAtPath(path)}
      />
      </div>
    </div>
  );
}
