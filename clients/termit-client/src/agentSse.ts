import type { AgentRunStreamEvent } from "./types";

export async function* parseAgentRunSseStream(
  body: ReadableStream<Uint8Array> | null
): AsyncGenerator<AgentRunStreamEvent> {
  if (!body) {
    return;
  }

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const event = parseAgentRunSseBlock(block);
        if (event) {
          yield event;
        }
      }
    }

    if (buffer.trim()) {
      const event = parseAgentRunSseBlock(buffer);
      if (event) {
        yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseAgentRunSseBlock(block: string): AgentRunStreamEvent | null {
  const lines = block.split("\n");
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (eventName === "status" || eventName === "timeline" || eventName === "done" || eventName === "error" || eventName === "timeout") {
    let data: Record<string, unknown> = {};
    const raw = dataLines.join("\n");
    if (raw) {
      try {
        data = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        data = { raw };
      }
    }
    return { event: eventName, data };
  }

  return null;
}
