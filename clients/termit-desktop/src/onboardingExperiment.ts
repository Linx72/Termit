const DEVICE_ID_KEY = "termit-device-id";
const VARIANT_KEY = "termit-onboarding-variant";

export type OnboardingVariant = "A" | "B";

function stableVariant(deviceId: string): OnboardingVariant {
  let hash = 0;
  for (let i = 0; i < deviceId.length; i += 1) {
    hash = (Math.imul(31, hash) + deviceId.charCodeAt(i)) >>> 0;
  }
  return hash % 2 === 0 ? "A" : "B";
}

function getOrCreateDeviceId(): string {
  try {
    const existing = localStorage.getItem(DEVICE_ID_KEY);
    if (existing && existing.trim()) {
      return existing.trim();
    }
    const created = `dev_${Date.now().toString(36)}_${Math.random().toString(16).slice(2, 10)}`;
    localStorage.setItem(DEVICE_ID_KEY, created);
    return created;
  } catch {
    return "dev_fallback";
  }
}

export function getOrAssignOnboardingVariant(): OnboardingVariant {
  try {
    const stored = localStorage.getItem(VARIANT_KEY);
    if (stored === "A" || stored === "B") {
      return stored;
    }
    const variant = stableVariant(getOrCreateDeviceId());
    localStorage.setItem(VARIANT_KEY, variant);
    return variant;
  } catch {
    return "A";
  }
}

export function peekOnboardingVariant(): OnboardingVariant | null {
  try {
    const stored = localStorage.getItem(VARIANT_KEY);
    return stored === "A" || stored === "B" ? stored : null;
  } catch {
    return null;
  }
}
