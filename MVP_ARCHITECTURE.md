# MVP Architecture - Termit

## System Overview

Termit uses a layered architecture:

- `API Layer` - request handling, validation, streaming responses.
- `Orchestration Layer` - plan/execute/verify/report task loop.
- `Provider Layer` - model providers and routing policies.
- `Tools Layer` - file, shell, browser, and project-aware utilities.
- `Memory Layer` - short-term session memory and execution history.
- `Observability Layer` - traces, metrics, errors, and task outcomes.

## Core Components

### 1) API Layer

Responsibilities:
- receive chat and task execution requests;
- expose session/memory endpoints;
- expose tool discovery and safe execution endpoints.

Primary interfaces:
- `POST /api/chat`
- `GET /api/providers/status`
- `GET /api/tools`
- `POST /api/tools/*`

### 2) Orchestrator

Execution lifecycle:
1. Understand intent and classify task.
2. Plan minimal action graph.
3. Execute actions with policy checks.
4. Verify outputs (tests, static checks, expectations).
5. Return structured final report.

Required behavior:
- explicit step boundaries;
- resumable state;
- deterministic failure reasons.

### 3) Model Router

Routing policy:
- route by task type (`coding`, `review`, `debug`, `explain`, `general`);
- use fallback providers only when request is not pinned;
- optional dual-pass: fast draft model + strong validator model.

Non-functional constraints:
- protect latency SLO with budget-aware routing;
- collect cost metrics per completed task.

### 4) Tools Layer

Tool groups:
- `Workspace tools` (list/read/write files in sandbox scope);
- `Execution tools` (shell commands with safety gates);
- `Browser tools` (navigation, snapshot, action, evidence capture).

Safety model:
- allowlist + risk levels (`safe`, `confirm`, `blocked`);
- path restrictions and traversal protection;
- no destructive action without explicit confirmation.

### 5) Memory and State

- in-session memory for short-term coherence;
- execution event log for diagnostics and analytics;
- optional durable storage for long-running tasks.

### 6) Observability

Capture:
- request latency and p95;
- task success/failure by scenario;
- provider errors and fallback frequency;
- cost per task and cost per successful outcome.

## Deployment Topology (MVP)

- backend app server;
- Redis for queues and short-lived coordination;
- Postgres for durable task and telemetry state;
- optional vector store for retrieval.

## Architecture Decisions for This Cycle

- keep modules narrow and composable;
- prioritize reliability and safe automation over feature breadth;
- optimize for measurable iteration via eval-first workflow.
