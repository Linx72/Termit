# Task Execution API Contract (v1)

## Goal

Provide a predictable lifecycle for long-running or multi-step tasks.

## Task States

- `queued`: task accepted, waiting for execution.
- `running`: task is being executed.
- `verifying`: output verification is in progress.
- `completed`: task finished successfully.
- `failed`: task finished with non-recoverable error.
- `cancelled`: task was cancelled by request.

## Endpoints (Implemented)

- `POST /api/tasks`
  - create task execution request
- `GET /api/tasks`
  - list recent tasks
- `GET /api/tasks/{task_id}`
  - retrieve task state and current report
- `POST /api/tasks/{task_id}/cancel`
  - cancel running task if supported
- `GET /api/tasks/{task_id}/events`
  - fetch execution events

## Request Shape (Create)

- `input`: user task description
- `context`: optional workspace/session context
- `mode`: optional (`auto`, `guided`)
- `constraints`: optional safety and budget constraints

## Response Shape (Create)

- `task_id`
- `state` (initially `queued` or `running`)
- `created_at`

## Event Model

Each event contains:
- `task_id`
- `event_type` (plan_step/tool_start/tool_end/verification/final)
- `state`
- `message`
- `timestamp`

## Failure Model

Stable error classes:
- `planning_error`
- `tool_error`
- `verification_error`
- `safety_block`
- `external_error`

Each failure includes:
- machine-readable class;
- concise human-readable reason;
- optional retry hint.
