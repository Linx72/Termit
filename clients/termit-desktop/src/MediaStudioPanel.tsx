import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import {
  generateMediaImage,
  isMediaConfirmationRequired,
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

type PendingMediaAction =
  | { kind: "generate"; prompt: string; provider: string }
  | { kind: "storyboard" };

export function MediaStudioPanel({ client, connected, locale }: MediaStudioPanelProps) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState<"stub" | "openai">("stub");
  const [projectId, setProjectId] = useState("desktop-studio");
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingMediaAction | null>(null);
  const [confirmDetail, setConfirmDetail] = useState("");

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

  const onGenerate = async (confirmed = false) => {
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    setPendingAction(null);
    try {
      const result = await generateMediaImage(client, {
        prompt: prompt.trim(),
        width: 512,
        height: 512,
        project_id: projectId,
        provider,
        confirmed,
      });
      setNotice(`${t(locale, "mediaStudioGenerated")}: ${result.asset.asset_id}`);
      await refresh();
    } catch (err) {
      if (!confirmed && isMediaConfirmationRequired(err)) {
        setConfirmDetail(err instanceof Error ? err.message : String(err));
        setPendingAction({ kind: "generate", prompt: prompt.trim(), provider });
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onRunStoryboard = async (confirmed = false) => {
    setBusy(true);
    setError("");
    setNotice("");
    setPendingAction(null);
    try {
      const result = await runMediaStoryboard(client, {
        storyboard_path: "data/media/examples/storyboard.example.json",
        project_id: projectId,
        brand_kit_id: "termit-default",
        max_scenes: 3,
        confirmed,
      });
      setNotice(
        `${t(locale, "mediaStudioStoryboardDone")}: ${result.asset.asset_id} (${Math.round(result.duration_sec)}s)`,
      );
      await refresh();
    } catch (err) {
      if (!confirmed && isMediaConfirmationRequired(err)) {
        setConfirmDetail(err instanceof Error ? err.message : String(err));
        setPendingAction({ kind: "storyboard" });
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onConfirmPending = async () => {
    if (!pendingAction) {
      return;
    }
    if (pendingAction.kind === "generate") {
      await onGenerate(true);
    } else {
      await onRunStoryboard(true);
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
          {pendingAction ? (
            <div className="media-confirm-box">
              <p className="hint">{t(locale, "mediaStudioConfirmTitle")}</p>
              <p className="hint muted">{confirmDetail}</p>
              <div className="row gap">
                <button type="button" className="primary compact" disabled={busy} onClick={() => void onConfirmPending()}>
                  {t(locale, "mediaStudioConfirmApprove")}
                </button>
                <button
                  type="button"
                  className="secondary compact"
                  disabled={busy}
                  onClick={() => {
                    setPendingAction(null);
                    setConfirmDetail("");
                  }}
                >
                  {t(locale, "mediaStudioConfirmCancel")}
                </button>
              </div>
            </div>
          ) : null}
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
                <label htmlFor="mediaProvider">{t(locale, "mediaStudioProvider")}</label>
                <select
                  id="mediaProvider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as "stub" | "openai")}
                >
                  <option value="stub">{t(locale, "mediaStudioProviderStub")}</option>
                  <option value="openai">{t(locale, "mediaStudioProviderOpenai")}</option>
                </select>
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
