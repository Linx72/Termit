import type { TermitClient } from "@termit/client";

export interface ContextSuggestion {
  path: string;
  reason: string;
}

export async function suggestContextFiles(
  client: TermitClient,
  options: {
    changedFiles: string[];
    workspacePrefix?: string;
    limit?: number;
  }
): Promise<ContextSuggestion[]> {
  const limit = options.limit ?? 8;
  const suggestions: ContextSuggestion[] = [];
  const seen = new Set<string>();

  for (const changed of options.changedFiles) {
    const parts = changed.replace(/\\/g, "/").split("/");
    if (parts.length > 1) {
      const folder = parts.slice(0, -1).join("/");
      try {
        const listed = await client.listFiles({ path: folder, pattern: "*" });
        for (const file of listed.files) {
          if (file.endsWith("/") || seen.has(file) || file === changed) {
            continue;
          }
          seen.add(file);
          suggestions.push({ path: file, reason: `same folder as ${changed}` });
          if (suggestions.length >= limit) {
            return suggestions;
          }
        }
      } catch {
        continue;
      }
    }
  }

  if (suggestions.length < limit && options.workspacePrefix) {
    try {
      const symbols = await client.searchSymbols({
        query: options.workspacePrefix,
        limit: 5,
        path_prefix: options.workspacePrefix,
      });
      for (const match of symbols.matches) {
        if (seen.has(match.path)) {
          continue;
        }
        seen.add(match.path);
        suggestions.push({ path: match.path, reason: `symbol ${match.name}` });
        if (suggestions.length >= limit) {
          break;
        }
      }
    } catch {
      return suggestions;
    }
  }

  return suggestions;
}
