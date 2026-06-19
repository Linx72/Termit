/** Deep links для beta invite: #beta, #beta-onboard */

export type BetaDeepLinkAction = "beta" | "beta-onboard" | null;

export function parseBetaDeepLink(): BetaDeepLinkAction {
  const hash = (window.location.hash || "").replace(/^#/, "").trim().toLowerCase();
  if (hash === "beta-onboard") {
    return "beta-onboard";
  }
  if (hash === "beta") {
    return "beta";
  }
  const params = new URLSearchParams(window.location.search);
  const query = (params.get("beta") || "").trim().toLowerCase();
  if (query === "onboard" || query === "beta-onboard") {
    return "beta-onboard";
  }
  if (query === "1" || query === "true" || query === "beta") {
    return "beta";
  }
  return null;
}

export function applyBetaDeepLink(action: BetaDeepLinkAction): {
  openSettings: boolean;
  openWizard: boolean;
} {
  if (!action) {
    return { openSettings: false, openWizard: false };
  }
  return {
    openSettings: true,
    openWizard: action === "beta-onboard",
  };
}

export function scrollToBetaPanel(): void {
  window.requestAnimationFrame(() => {
    document.getElementById("beta-invite-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
