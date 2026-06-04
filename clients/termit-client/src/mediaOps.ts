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
  },
): Promise<{ asset: MediaAsset }> {
  return client.requestMedia<{ asset: MediaAsset }>("/api/media/generate-image", {
    method: "POST",
    body: JSON.stringify({ ...body, confirmed: true, provider: body.provider ?? "stub" }),
  });
}

export async function runMediaStoryboard(
  client: TermitClient,
  body: {
    storyboard_path?: string;
    project_id?: string;
    brand_kit_id?: string;
    max_scenes?: number;
  },
): Promise<{ asset: MediaAsset; duration_sec: number }> {
  return client.requestMedia<{ asset: MediaAsset; duration_sec: number }>("/api/media/run-storyboard", {
    method: "POST",
    body: JSON.stringify({ ...body, confirmed: true }),
  });
}

export async function listBrandKits(client: TermitClient): Promise<BrandKit[]> {
  return client.requestMedia<BrandKit[]>("/api/media/brand-kits");
}

export function mediaAssetFileUrl(client: TermitClient, assetId: string): string {
  return `${client.baseUrl}/api/media/assets/${encodeURIComponent(assetId)}/file`;
}
