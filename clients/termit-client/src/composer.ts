import type { ApplyPatchRequest } from "./types";

export interface ComposerFileContext {
  path: string;
  content: string;
}

export const COMPOSER_JSON_INSTRUCTION = `When proposing file edits, end your reply with exactly one fenced JSON block:

\`\`\`json
{"patches":[{"path":"relative/path.py","hunks":[{"old_text":"exact existing text","new_text":"replacement"}]}]}
\`\`\`

Rules:
- Use "hunks" for partial edits (old_text must match exactly once).
- Use "content" plus "create": true for new files.
- Paths are relative to the workspace root.
- If no file edits are needed, omit the JSON block.`;

export function buildComposerMessage(
  instruction: string,
  files: ComposerFileContext[]
): string {
  const fileBlocks = files
    .map((file) => `### ${file.path}\n\`\`\`\n${file.content}\n\`\`\``)
    .join("\n\n");
  return [
    instruction.trim(),
    "",
    "---",
    "Context files:",
    "",
    fileBlocks,
    "",
    "---",
    COMPOSER_JSON_INSTRUCTION,
  ].join("\n");
}

function normalizePatch(raw: Record<string, unknown>): ApplyPatchRequest | null {
  const path = typeof raw.path === "string" ? raw.path.trim() : "";
  if (!path) {
    return null;
  }
  const create = raw.create === true;
  if (typeof raw.content === "string") {
    return { path, content: raw.content, create };
  }
  if (Array.isArray(raw.hunks)) {
    const hunks = raw.hunks
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }
        const hunk = item as Record<string, unknown>;
        return {
          old_text: typeof hunk.old_text === "string" ? hunk.old_text : "",
          new_text: typeof hunk.new_text === "string" ? hunk.new_text : "",
        };
      })
      .filter((item): item is { old_text: string; new_text: string } => item !== null);
    if (hunks.length === 0) {
      return null;
    }
    return { path, hunks, create };
  }
  return null;
}

export function parseComposerPatches(text: string): ApplyPatchRequest[] {
  const patches: ApplyPatchRequest[] = [];
  const fencePattern = /```(?:json)?\s*([\s\S]*?)```/gi;
  let match: RegExpExecArray | null = fencePattern.exec(text);
  while (match) {
    try {
      const parsed = JSON.parse(match[1].trim()) as unknown;
      const list = Array.isArray(parsed)
        ? parsed
        : parsed && typeof parsed === "object" && Array.isArray((parsed as { patches?: unknown }).patches)
          ? (parsed as { patches: unknown[] }).patches
          : [];
      for (const item of list) {
        if (!item || typeof item !== "object") {
          continue;
        }
        const patch = normalizePatch(item as Record<string, unknown>);
        if (patch) {
          patches.push(patch);
        }
      }
    } catch {
      // Try next fenced block.
    }
    match = fencePattern.exec(text);
  }
  return patches;
}

export function stripComposerJsonBlock(text: string): string {
  return text.replace(/```(?:json)?\s*[\s\S]*?```/gi, "").trim();
}

export const INLINE_EDIT_JSON_INSTRUCTION = `Return exactly one fenced JSON block with a single hunk replacing the selection:

\`\`\`json
{"patches":[{"path":"RELATIVE_PATH","hunks":[{"old_text":"SELECTION","new_text":"REPLACEMENT"}]}]}
\`\`\`

old_text must equal the selection verbatim.`;

export function buildInlineEditMessage(
  instruction: string,
  filePath: string,
  languageId: string,
  selectedText: string
): string {
  return [
    instruction.trim(),
    "",
    "---",
    `File: ${filePath}`,
    `Language: ${languageId}`,
    "Selection to edit:",
    "```",
    selectedText,
    "```",
    "",
    "---",
    INLINE_EDIT_JSON_INSTRUCTION.replace("RELATIVE_PATH", filePath).replace(
      "SELECTION",
      "copy selection exactly"
    ),
  ].join("\n");
}

export function pickInlinePatch(
  patches: ApplyPatchRequest[],
  filePath: string,
  selectedText: string
): ApplyPatchRequest | undefined {
  const forFile = patches.filter((patch) => patch.path === filePath);
  const exact = forFile.find((patch) =>
    patch.hunks?.some((hunk) => hunk.old_text === selectedText)
  );
  if (exact) {
    return exact;
  }
  if (forFile.length > 0) {
    return forFile[0];
  }
  return patches[0];
}
