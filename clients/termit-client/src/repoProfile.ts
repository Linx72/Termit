import type { RepoModelProfile } from "./types";

export const DEFAULT_REPO_PROFILES: RepoModelProfile[] = [
  {
    profile_id: "termit-core",
    title: "Termit core backend",
    path_prefix: "app/",
    task_type: "coding",
    preferred_model: "ollama:termit-core-ft",
    description: "Primary Python orchestrator codebase.",
  },
  {
    profile_id: "termit-tests",
    title: "Termit test suite",
    path_prefix: "tests/",
    task_type: "debug",
    preferred_model: "ollama:qwen2.5-coder",
    description: "Unit and integration tests.",
  },
];

/** Normalize path for prefix matching (forward slashes). */
export function normalizePathPrefix(value: string): string {
  return value.trim().replace(/\\/g, "/");
}

/** Infer retrieval prefix like app/ from workspace (+ optional repo root). */
export function inferRetrievalPathPrefix(workspace: string, repoRoot?: string): string {
  const normalized = normalizePathPrefix(workspace);
  if (!normalized) {
    return "";
  }
  if (repoRoot) {
    const root = normalizePathPrefix(repoRoot).replace(/\/$/, "");
    if (normalized.startsWith(root)) {
      const relative = normalized.slice(root.length).replace(/^\//, "");
      if (!relative) {
        return "";
      }
      const top = relative.split("/")[0] ?? relative;
      return top.endsWith("/") ? top : `${top}/`;
    }
  }
  const segments = normalized.split("/").filter(Boolean);
  const known = ["app", "tests", "clients", "scripts", "data"];
  for (const segment of segments) {
    if (known.includes(segment)) {
      return `${segment}/`;
    }
  }
  const last = segments[segments.length - 1] ?? "";
  return last ? `${last}/` : normalized;
}

/** Infer repo profile id from workspace path using backend profile prefixes. */
export function inferRepoProfileId(
  workspacePath: string,
  profiles: RepoModelProfile[] = DEFAULT_REPO_PROFILES,
  explicitProfileId?: string,
  defaultProfileId?: string
): string | undefined {
  const explicit = explicitProfileId?.trim();
  if (explicit) {
    return explicit;
  }
  const normalized = normalizePathPrefix(workspacePath);
  if (normalized) {
    let best: RepoModelProfile | undefined;
    for (const profile of profiles) {
      const prefix = normalizePathPrefix(profile.path_prefix);
      if (!prefix || !normalized.startsWith(prefix)) {
        continue;
      }
      if (!best || prefix.length > normalizePathPrefix(best.path_prefix).length) {
        best = profile;
      }
    }
    if (best) {
      return best.profile_id;
    }
  }
  const fallback = defaultProfileId?.trim();
  return fallback || undefined;
}

export interface AgentRunScopeOptions {
  workspace?: string;
  repoRoot?: string;
  repoProfile?: string;
  profiles?: RepoModelProfile[];
  defaultRepoProfile?: string;
  projectId?: string;
}

/** Build agent run payload fields for workspace-scoped routing. */
export function buildAgentRunScope(options: AgentRunScopeOptions): {
  workspace_scope?: string;
  retrieval_path_prefix?: string;
  repo_profile?: string;
  project_id?: string;
} {
  const workspace = options.workspace?.trim();
  const prefix = workspace
    ? inferRetrievalPathPrefix(workspace, options.repoRoot)
    : "";
  const repoProfile = inferRepoProfileId(
    prefix,
    options.profiles ?? DEFAULT_REPO_PROFILES,
    options.repoProfile,
    options.defaultRepoProfile
  );
  return {
    ...(workspace ? { workspace_scope: workspace } : {}),
    ...(prefix ? { retrieval_path_prefix: prefix } : {}),
    ...(repoProfile ? { repo_profile: repoProfile } : {}),
    ...(options.projectId ? { project_id: options.projectId } : {}),
  };
}

export function primaryAttemptedModel(run: {
  model?: string;
  attempted_models?: string[];
}): string | undefined {
  const attempted = run.attempted_models?.find((item) => item.trim());
  if (attempted) {
    return attempted;
  }
  return run.model?.trim() || undefined;
}

export const resolvedAgentModel = primaryAttemptedModel;
