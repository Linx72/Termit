import type { TermitClient } from "./client";

export interface MediaAsset {
  asset_id: string;
  project_id: string;
  rel_path: string;
  mime: string;
  width: number;
  height: number;
  provider: string;
  cost_usd: number;
  prompt: string;
  created_at: string;
}

export interface BrandKit {
  brand_kit_id: string;
  name: string;
  colors: string[];
  fonts: string[];
  logo_paths: string[];
  voice_id: string;
  music_mood: string;
  style_prompt_suffix: string;
}

export async function listMediaAssets(
  client: TermitClient,
  params: { project_id?: string; limit?: number } = {},
): Promise<MediaAsset[]> {
  const query = new URLSearchParams();
  if (params.project_id) {
    query.set("project_id", params.project_id);
  }
  if (params.limit) {
    query.set("limit", String(params.limit));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return client.requestMedia<MediaAsset[]>(`/api/media/assets${suffix}`);
}

export async function generateMediaImage(
  client: TermitClient,
  body: {
    prompt: string;
    width?: number;
    height?: number;
    project_id?: string;
    provider?: string;
    confirmed?: boolean;
  },
): Promise<{ asset: MediaAsset }> {
  return client.requestMedia<{ asset: MediaAsset }>("/api/media/generate-image", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      confirmed: body.confirmed ?? false,
      provider: body.provider ?? "stub",
    }),
  });
}

export function isMediaConfirmationRequired(error: unknown): boolean {
  const text = error instanceof Error ? error.message : String(error);
  return text.includes("Termit API 428:");
}

export async function runMediaStoryboard(
  client: TermitClient,
  body: {
    storyboard_path?: string;
    project_id?: string;
    brand_kit_id?: string;
    max_scenes?: number;
    confirmed?: boolean;
  },
): Promise<{ asset: MediaAsset; duration_sec: number }> {
  return client.requestMedia<{ asset: MediaAsset; duration_sec: number }>("/api/media/run-storyboard", {
    method: "POST",
    body: JSON.stringify({
      ...body,
      confirmed: body.confirmed ?? false,
    }),
  });
}

export async function listBrandKits(client: TermitClient): Promise<BrandKit[]> {
  return client.requestMedia<BrandKit[]>("/api/media/brand-kits");
}

export async function exportMediaLottie(
  client: TermitClient,
  body: {
    asset_ids: string[];
    project_id?: string;
    fps?: number;
    width?: number;
  },
): Promise<MediaAsset> {
  return client.requestMedia<MediaAsset>("/api/media/export-lottie", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function mediaAssetFileUrl(client: TermitClient, assetId: string): string {
  return `${client.baseUrl}/api/media/assets/${encodeURIComponent(assetId)}/file`;
}
