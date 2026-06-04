/** Detect website/app build tasks for auto web-app-vite agent (mirrors backend BuildWorkflowService). */
export function isBuildTask(text: string): boolean {
  const stripped = text.trim();
  if (stripped.length < 8) {
    return false;
  }
  return /\b(сайт|website|web\s*app|landing|лендинг|программ|приложен|react|vite|api|backend|fix|bug|refactor|implement|тест|test|frontend|сделай|создай|собери|напиши|исправь|добавь|реализуй|create\s+(a\s+)?(app|site|program|website|api))\b/i.test(
    stripped
  );
}

export function executionModeLabel(locale: "ru" | "en", mode: string): string {
  if (locale === "ru") {
    switch (mode) {
      case "local":
        return "Локально";
      case "online":
        return "Online";
      case "ssh":
        return "SSH";
      case "hybrid":
      default:
        return "Hybrid (local + online)";
    }
  }
  switch (mode) {
    case "local":
      return "Local";
    case "online":
      return "Online";
    case "ssh":
      return "SSH remote";
    case "hybrid":
    default:
      return "Hybrid (local + online)";
  }
}
