import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import {
  generateMediaImage,
  listBrandKits,
  listMediaAssets,
  mediaAssetFileUrl,
  runMediaStoryboard,
  type BrandKit,
  type MediaAsset,
} from "@termit/client";
import { t, type Locale } from "./i18n";

interface MediaStudioPanelProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
}

export function MediaStudioPanel({ client, connected, locale }: MediaStudioPanelProps) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [projectId, setProjectId] = useState("desktop-studio");
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    setError("");
    try {
      const [assetList, kitList] = await Promise.all([
        listMediaAssets(client, { project_id: projectId, limit: 20 }),
        listBrandKits(client),
      ]);
      setAssets(assetList);
      setKits(kitList);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [client, connected, projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onGenerate = async () => {
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await generateMediaImage(client, {
        prompt: prompt.trim(),
        width: 512,
        height: 512,
        project_id: projectId,
        provider: "stub",
      });
      setNotice(`${t(locale, "mediaStudioGenerated")}: ${result.asset.asset_id}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onRunStoryboard = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await runMediaStoryboard(client, {
        storyboard_path: "data/media/examples/storyboard.example.json",
        project_id: projectId,
        brand_kit_id: "termit-default",
        max_scenes: 3,
      });
      setNotice(
        `${t(locale, "mediaStudioStoryboardDone")}: ${result.asset.asset_id} (${Math.round(result.duration_sec)}s)`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="media-studio-panel">
      <button
        type="button"
        className="secondary compact setup-guide-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? t(locale, "mediaStudioHide") : t(locale, "mediaStudioShow")}
      </button>
      {open ? (
        <div className="setup-guide-body">
          <strong>{t(locale, "mediaStudioTitle")}</strong>
          <p className="hint">{t(locale, "mediaStudioHint")}</p>
          {error ? <p className="hint error-text">{error}</p> : null}
          {notice ? <p className="hint ok-text">{notice}</p> : null}
          {!connected ? <p className="hint">{t(locale, "mediaStudioConnectFirst")}</p> : null}
          {connected ? (
            <>
              <div className="field">
                <label htmlFor="mediaProjectId">{t(locale, "mediaStudioProject")}</label>
                <input
                  id="mediaProjectId"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="mediaPrompt">{t(locale, "mediaStudioPrompt")}</label>
                <input
                  id="mediaPrompt"
                  value={prompt}
                  placeholder={t(locale, "mediaStudioPromptPlaceholder")}
                  onChange={(e) => setPrompt(e.target.value)}
                />
              </div>
              <div className="row gap">
                <button type="button" className="secondary compact" disabled={busy} onClick={() => void onGenerate()}>
                  {t(locale, "mediaStudioGenerate")}
                </button>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => void onRunStoryboard()}
                >
                  {t(locale, "mediaStudioRunStoryboard")}
                </button>
                <button type="button" className="secondary compact" disabled={busy} onClick={() => void refresh()}>
                  {t(locale, "refresh")}
                </button>
              </div>
              {kits.length > 0 ? (
                <p className="hint">
                  {t(locale, "mediaStudioBrandKits")}: {kits.map((k) => k.name).join(", ")}
                </p>
              ) : null}
              <ul className="media-asset-list">
                {assets.map((asset) => (
                  <li key={asset.asset_id}>
                    <code>{asset.asset_id}</code> — {asset.mime}{" "}
                    {asset.width > 0 ? `${asset.width}×${asset.height}` : ""}{" "}
                    <a href={mediaAssetFileUrl(client, asset.asset_id)} target="_blank" rel="noreferrer">
                      {t(locale, "mediaStudioOpen")}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
