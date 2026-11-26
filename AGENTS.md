# RCM360 project instructions

Act as a rigorous research and analytics collaborator. Prefer correct, reproducible findings and maintainable code over artificial novelty. Separate verified facts from inference, disclose material limits, and never fabricate data, findings, citations, incidents, or test results.

## Project constraints

- Use only the Misata Hospital Encounters, Diagnoses and Claims dataset selected in `PLAN.md`. Preserve source files and verify them before analysis.
- PostgreSQL must be executed for relational design, analysis, validation, and reconciliation. The deployed dashboard reads validated JSON exports and requires no database connection.
- Keep claims, encounters, diagnoses, labs, and other table grains explicit. Prevent one-to-many joins from duplicating claim counts or dollars.
- Use exact decimal arithmetic for financial source totals where appropriate. Label payer payments separately from total collections. Do not call denied billed amounts losses or recoverable revenue.
- Keep original-data QA separate from deliberately corrupted QA test copies. Do not infer quality failures from unusual but valid values.
- Preserve the supplied `reference UI/rcm_dashboard_indigo.html` unchanged; use its indigo identity and verify every displayed metric against executed SQL.
- Build a focused analytics portfolio, not a production medical billing system. Avoid patient identifiers in exports and public output.

## Ownership and coordination

- The orchestrator owns shared contracts, project documentation, dependencies, integration, final analysis review, and communication with the user.
- Data analytics owns `data/`, `notebooks/`, `sql/`, `src/`, and `tests/data/`.
- Dashboard specialist owns `dashboard/`, `.streamlit/`, dashboard assets, and `tests/dashboard/`.
- Keep at most two subagents active at a time. Agents must not spawn other agents. Give each delegated task a bounded objective, file scope, dependencies, deliverables, and acceptance criteria.
- Do not run agents in parallel when they would edit the same file. Integrate against `docs/data_contract.md` and verify important results independently.

## Git workflow

- The primary orchestrator coordinates all Git operations. Subagents must not stage, commit, push, or change remotes.
- Inspect branch, status, and remotes before Git changes. Stage exact files and review the staged diff; run relevant checks before code commits.
- Create small, meaningful commits after each verified logical task, using descriptive Conventional Commit subjects (`feat`, `fix`, `test`, `docs`, `refactor`, or `chore`). Push verified commits regularly to the user-authorized GitHub repository.
- Never commit credentials, secrets, virtual environments, caches, or unnecessary large/source files. Never force-push or rewrite commit history.
- If GitHub authentication or environment restrictions prevent a push, retain the verified local work and provide exact manual `git add`, `git commit`, and `git push` commands, commit messages, staged file lists, and any remote/authentication setup needed. Continue independent work while Git operations are pending.
- Do not deploy the application yet; deployment requires a separate future user request.

## Working standards

- Read only relevant files and inspect samples or aggregate scripts for large data.
- Update `PROGRESS.md` at meaningful checkpoints. Keep `PLAN.md`, `docs/data_contract.md`, and `docs/decisions.md` canonical rather than duplicating project context.
- Run checks required by the project brief and report the command and outcome accurately. Never state a database, test, or deployment succeeded without evidence.
- Escalate only genuine manual work such as system software installation, personal credentials, authenticated browser steps, or external publishing. Continue independent work while a manual prerequisite is outstanding.
