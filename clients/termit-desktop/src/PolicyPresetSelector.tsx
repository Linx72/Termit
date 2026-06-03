import type { AgentPolicyPreset } from "@termit/client";
import { t, type Locale } from "./i18n";

interface PolicyPresetSelectorProps {
  presets: AgentPolicyPreset[];
  value: string;
  locale: Locale;
  disabled?: boolean;
  onChange: (presetId: string) => void;
}

export function PolicyPresetSelector({
  presets,
  value,
  locale,
  disabled,
  onChange,
}: PolicyPresetSelectorProps) {
  return (
    <div className="field policy-preset-field">
      <label htmlFor="policyPreset">{t(locale, "policyPreset")}</label>
      <select
        id="policyPreset"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{t(locale, "policyPresetNone")}</option>
        {presets.map((preset) => (
          <option key={preset.preset_id} value={preset.preset_id}>
            {preset.name} ({preset.execution_mode})
          </option>
        ))}
      </select>
      {value ? (
        <p className="hint">
          {presets.find((item) => item.preset_id === value)?.[
            locale === "ru" ? "description_ru" : "description_en"
          ] ?? ""}
        </p>
      ) : null}
    </div>
  );
}
