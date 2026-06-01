export class TermitStartupError extends Error {
  readonly statusCode: number;
  readonly isRetryable: boolean;

  constructor(message: string, statusCode: number, isRetryable = false) {
    super(message);
    this.name = "TermitStartupError";
    this.statusCode = statusCode;
    this.isRetryable = isRetryable;
  }
}

export class TermitRunError extends Error {
  readonly runId: string;
  readonly state: string;

  constructor(message: string, runId: string, state: string) {
    super(message);
    this.name = "TermitRunError";
    this.runId = runId;
    this.state = state;
  }
}
