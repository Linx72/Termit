# Tool Safety Policy (MVP)

## Policy Goals

- prevent unsafe local operations;
- keep automation useful without blocking normal workflows;
- make every risky action explainable and auditable.

## Risk Levels

- `safe`: execute without confirmation.
- `confirm`: require explicit user confirmation before execution.
- `blocked`: never execute from agent flow.

## Command Rules

Safe examples:
- read-only file discovery;
- non-destructive diagnostics;
- test execution and lint checks.

Confirm examples:
- package installations;
- commands that may alter many files;
- long-running operations with resource impact.

Blocked examples:
- destructive filesystem operations;
- privilege escalation;
- credential exfiltration attempts.

## File and Path Rules

- all file operations are restricted to workspace scope by default;
- no path traversal beyond configured root;
- writing to sensitive files requires confirmation.

## Browser Automation Rules

- stop on blockers (auth, captcha, permissions);
- do not retry same failing action repeatedly without new evidence;
- collect evidence (snapshot/screenshot) before high-impact actions.

## Verification and Audit

- every action must be logged with:
  - tool name;
  - intent;
  - risk level;
  - result status;
  - timestamp.

- failed actions must include a short reason and next best step.
