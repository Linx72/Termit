import type { ApplyPatchHunk, ApplyPatchRequest } from "./types";

function applyHunksLocally(content: string, hunks: ApplyPatchHunk[]): string {
  let next = content;
  for (const [index, hunk] of hunks.entries()) {
    const occurrences = next.split(hunk.old_text).length - 1;
    if (occurrences !== 1) {
      throw new Error(
        `Hunk ${index + 1} must match exactly once in file (found ${occurrences}).`
      );
    }
    next = next.replace(hunk.old_text, hunk.new_text);
  }
  return next;
}

export function computePatchedContent(
  current: string,
  request: Pick<ApplyPatchRequest, "content" | "hunks">
): string {
  if (request.content !== undefined) {
    return request.content;
  }
  if (!request.hunks || request.hunks.length === 0) {
    throw new Error("Patch must include hunks or content.");
  }
  return applyHunksLocally(current, request.hunks);
}
