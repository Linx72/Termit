import type { TermitClient } from "@termit/client";
import type { ApplyPatchRequest, ApplyPatchResponse } from "@termit/client";

export interface SafeApplySummary {
  total: number;
  safeCount: number;
  confirmCount: number;
  blockedCount: number;
  canApplyAll: boolean;
  blockedPaths: string[];
}

export function summarizePatchRisk(
  patches: ApplyPatchRequest[],
  previews: Record<string, ApplyPatchResponse>
): SafeApplySummary {
  let safeCount = 0;
  let confirmCount = 0;
  let blockedCount = 0;
  const blockedPaths: string[] = [];

  for (const patch of patches) {
    const preview = previews[patch.path];
    const risk = preview?.risk_level ?? "confirm";
    if (risk === "blocked") {
      blockedCount += 1;
      blockedPaths.push(patch.path);
    } else if (risk === "safe") {
      safeCount += 1;
    } else {
      confirmCount += 1;
    }
  }

  return {
    total: patches.length,
    safeCount,
    confirmCount,
    blockedCount,
    canApplyAll: blockedCount === 0 && patches.length > 0,
    blockedPaths,
  };
}

export async function dryRunAllPatches(
  client: TermitClient,
  patches: ApplyPatchRequest[]
): Promise<Record<string, ApplyPatchResponse>> {
  const previews: Record<string, ApplyPatchResponse> = {};
  for (const patch of patches) {
    try {
      previews[patch.path] = await client.applyPatch({
        ...patch,
        dry_run: true,
        confirmed: false,
      });
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      previews[patch.path] = {
        path: patch.path,
        risk_level: "blocked",
        policy_reason: text,
        applied: false,
      };
    }
  }
  return previews;
}

export function formatSafeApplyHint(summary: SafeApplySummary, locale: "ru" | "en"): string {
  if (summary.total === 0) {
    return locale === "ru" ? "Нет патчей для preview." : "No patches to preview.";
  }
  if (summary.blockedCount > 0) {
    return locale === "ru"
      ? `Заблокировано ${summary.blockedCount}/${summary.total}. Apply all недоступен.`
      : `Blocked ${summary.blockedCount}/${summary.total}. Apply all disabled.`;
  }
  return locale === "ru"
    ? `Safe apply: ${summary.safeCount} safe, ${summary.confirmCount} confirm.`
    : `Safe apply: ${summary.safeCount} safe, ${summary.confirmCount} confirm.`;
}
