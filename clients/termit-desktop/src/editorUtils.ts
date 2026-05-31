export { computePatchedContent } from "@termit/client";

const EXT_TO_LANG: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  py: "python",
  json: "json",
  md: "markdown",
  css: "css",
  html: "html",
  yaml: "yaml",
  yml: "yaml",
  sh: "shell",
  rs: "rust",
  go: "go",
  sql: "sql",
};

export function languageFromPath(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TO_LANG[ext] ?? "plaintext";
}
