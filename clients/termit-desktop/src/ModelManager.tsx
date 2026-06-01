import { useCallback, useEffect, useState } from "react";
import type { TermitClient } from "@termit/client";
import { t, type Locale } from "./i18n";

interface ModelManagerProps {
  client: TermitClient;
  connected: boolean;
  locale: Locale;
  missingModels: string[];
  onRefreshStatus: () => void;
}

export function ModelManager({
  client,
  connected,
  locale,
  missingModels,
  onRefreshStatus,
}: ModelManagerProps) {
  const [installed, setInstalled] = useState<string[]>([]);
  const [pulling, setPulling] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!connected) {
      return;
    }
    try {
      const response = await client.listLocalModels();
      setInstalled(response.models.map((item) => item.name));
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    }
  }, [client, connected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const pull = async (model: string) => {
    if (!connected || pulling) {
      return;
    }
    setPulling(model);
    setError("");
    try {
      await client.pullOllamaModel(model);
      await refresh();
      onRefreshStatus();
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err);
      setError(text);
    } finally {
      setPulling(null);
    }
  };

  return (
    <div className="model-manager">
      <strong>{t(locale, "modelsTitle")}</strong>
      {error && <p className="hint error-text">{error}</p>}
      {missingModels.length > 0 && (
        <div className="model-missing">
          <span className="hint">{t(locale, "missingModels")}:</span>
          <ul>
            {missingModels.map((model) => (
              <li key={model}>
                {model}
                <button
                  type="button"
                  className="secondary compact"
                  disabled={!connected || pulling === model}
                  onClick={() => void pull(model)}
                >
                  {pulling === model ? "…" : t(locale, "pullModel")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {installed.length > 0 && (
        <p className="hint muted">{installed.length} installed: {installed.slice(0, 4).join(", ")}{installed.length > 4 ? "…" : ""}</p>
      )}
    </div>
  );
}
