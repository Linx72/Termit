export interface ContextAttachment {
  kind: "file" | "folder" | "symbol" | "docs" | "web";
  path: string;
  excerpt: string;
  label?: string;
}

export function excerptAroundLine(content: string, line: number, radius = 8): string {
  const lines = content.split("\n");
  const start = Math.max(0, line - 1 - radius);
  const end = Math.min(lines.length, line + radius);
  return lines.slice(start, end).join("\n");
}

export function buildMessageWithAttachments(message: string, attachments: ContextAttachment[]): string {
  if (attachments.length === 0) {
    return message;
  }
  const blocks = attachments.map((item) => {
    const tag =
      item.kind === "folder"
        ? `@folder ${item.path}`
        : item.kind === "symbol"
          ? `@symbol ${item.label ?? item.path}`
          : item.kind === "docs"
            ? `@docs ${item.label ?? item.path}`
            : item.kind === "web"
              ? `@web ${item.label ?? item.path}`
              : `@file ${item.path}`;
    return `${tag}\n\`\`\`\n${item.excerpt}\n\`\`\``;
  });
  return `${message.trim()}\n\n---\n${blocks.join("\n\n")}`;
}

export function attachmentPaths(attachments: ContextAttachment[]): string[] {
  return attachments.map((item) => item.path).filter(Boolean);
}
