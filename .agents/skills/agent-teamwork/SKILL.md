---
name: agent-teamwork
description: Coordinate bounded multi-agent work in this repository, including role routing, file ownership, handoffs, and integration checkpoints.
---

# Agent Teamwork

Use this skill for substantive work in RCM360 that benefits from parallel investigation or implementation. Keep short or tightly dependent tasks with the orchestrator.

## Roles and scope

- The orchestrator owns `AGENTS.md`, `PLAN.md`, `PROGRESS.md`, shared contracts, dependencies, integration, final analytical review, and user communication.
- Data and analytics owns `data/`, `notebooks/`, `sql/`, `src/`, and `tests/data/`.
- Dashboard and visualization owns `dashboard/`, `.streamlit/`, dashboard assets, and `tests/dashboard/`.
- Do not assign concurrent writers to the same files. Agree on a data contract before integrating producers and consumers.
- Keep no more than two subagents active at once. Agents must not spawn or delegate to other agents.

## Task routing and model effort

Delegate independent work only. Give each task an ID, objective, relevant inputs, writable paths, dependencies, deliverables, and observable acceptance criteria. Prefer a read-only discovery pass before parallel implementation when dependencies are unclear.

- Use GPT-6.2 Sol at medium effort for ordinary analysis and implementation; use high for architecture, financial logic, SQL correctness, reconciliation, or integration reviews.
- Use GPT-6 Luna for small, repeatable tasks. Set effort to the lowest level that meets the need; use `xhigh` only for clearly bounded work that materially benefits from deeper reasoning.
- The current Codex interface accepts model IDs and `low`, `medium`, `high`, `xhigh`, or `max` effort values. Do not claim a model switch unless the spawn/runtime confirms it.
- If a requested model or effort is unavailable, use the parent model and report the limitation accurately.

## Handoffs and integration

Require concise completion reports: files changed, work completed, checks actually run and results, remaining issues, and next action. Review changes against the task acceptance criteria and shared contracts before integrating. Resolve dependencies sequentially and validate important calculations independently in PostgreSQL and Python where applicable.

Keep outputs reproducible, evidence-based, and limited to assigned scope. Do not invent dataset fields, findings, data-quality failures, or test results. Escalate only genuine blockers requiring user access, credentials, installation, or a material project decision; continue independent work and update `PROGRESS.md` for recovery.

## Git workflow

- The orchestrator alone runs Git operations; agents never stage, commit, push, or edit Git remotes.
- Before Git changes, inspect the current branch, status, and remotes. Stage exact files, inspect the staged diff, and run relevant checks before committing.
- Make small commits for completed logical tasks using descriptive Conventional Commit subjects (`feat`, `fix`, `test`, `docs`, `refactor`, or `chore`). Push verified commits regularly to the authorized project remote.
- Never commit secrets, credentials, virtual environments, caches, or unnecessary source data; never force-push or rewrite history.
- If authentication or environment limits block GitHub operations, keep verified local commits, report the blocker, and give exact manual staging/commit/push commands. Continue independent development.
- Do not deploy the app unless the user separately asks.
