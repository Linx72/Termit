export interface TermitDesktopApi {
  pickWorkspace(): Promise<string | null>;
  pickWorkspaceFile(workspace: string): Promise<string | null>;
}

declare global {
  interface Window {
    termitDesktop: TermitDesktopApi;
  }
}

export {};
