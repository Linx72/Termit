export type StoredChatBlock =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string }
  | { id: string; kind: "meta" | "error"; text: string };

export interface StoredChatSession {
  localId: string;
  sessionId: string;
  title: string;
  summary: string;
  blocks: StoredChatBlock[];
  updatedAt: number;
}

const SESSIONS_KEY = "termit-chat-sessions-v1";
const ACTIVE_KEY = "termit-active-chat-local-id";

export function newLocalId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function loadChatSessions(): StoredChatSession[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as StoredChatSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveChatSessions(sessions: StoredChatSession[]): void {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export function loadActiveLocalId(): string {
  return localStorage.getItem(ACTIVE_KEY) ?? "";
}

export function saveActiveLocalId(localId: string): void {
  localStorage.setItem(ACTIVE_KEY, localId);
}

export function deriveSessionTitle(blocks: StoredChatBlock[]): string {
  const user = blocks.find((block) => block.kind === "user");
  if (!user) {
    return "Новый чат";
  }
  const line = user.text.trim().split("\n")[0] ?? "";
  if (!line) {
    return "Новый чат";
  }
  return line.length > 48 ? `${line.slice(0, 45)}…` : line;
}

export function deriveSessionSummary(blocks: StoredChatBlock[]): string {
  for (let index = blocks.length - 1; index >= 0; index -= 1) {
    const block = blocks[index];
    if (block.kind === "user" || block.kind === "assistant") {
      const text = block.text.trim().replace(/\s+/g, " ");
      if (!text) {
        continue;
      }
      return text.length > 80 ? `${text.slice(0, 77)}…` : text;
    }
  }
  return "";
}

export function createEmptySession(): StoredChatSession {
  const localId = newLocalId();
  return {
    localId,
    sessionId: "",
    title: "Новый чат",
    summary: "",
    blocks: [],
    updatedAt: Date.now(),
  };
}

export function upsertSession(
  sessions: StoredChatSession[],
  session: StoredChatSession
): StoredChatSession[] {
  const next = sessions.filter((item) => item.localId !== session.localId);
  next.unshift(session);
  return next.slice(0, 50);
}

export function renameSession(
  sessions: StoredChatSession[],
  localId: string,
  title: string
): StoredChatSession[] {
  const trimmed = title.trim();
  if (!trimmed) {
    return sessions;
  }
  return sessions.map((session) =>
    session.localId === localId ? { ...session, title: trimmed, updatedAt: Date.now() } : session
  );
}
