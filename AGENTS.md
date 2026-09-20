# Cine Toaster development

Before changing architecture, the project model, persistence, jobs, agents, or
external integrations, read:

- `ai-context/architecture.md`
- `ai-context/project-model.md`
- `ai-context/agent-architecture.md`
- `ai-context/development/roadmap.md`
- `ai-context/project-status.md`
- `ai-context/specs/README.md` and any specification relevant to the change
- `ai-context/work/README.md` and the relevant active work record

Project-specific development context belongs in `ai-context/`. Accepted
architecture decisions belong in `docs/architecture/`. Keep both concise and
update them when an implementation changes an established boundary.

Every non-trivial change must have an `ai-context/work/` record that states what
is being changed, why, what is done, what remains, decisions made, and the
validation performed. Update it during the work, not only at the end.

Keep `ai-context/project-status.md` synchronized when work changes the current
phase, active queue, delivered capabilities, risks, or next recommended action.
All `ai-context/` content is written in English.

## Architectural invariants

- The filesystem project is authoritative for production state.
- Caches and operational state must be disposable without destroying the film.
- The Project Core contains filmmaking concepts, not provider-specific logic.
- Mutations from GUI, CLI, APIs, and agents use the same application commands.
- The active UI project does not own or limit background work.
- Agent roles are independent from AI providers.
- Orchestration, agent, generation, media, and UI protocol integrations remain
  behind distinct adapter boundaries.
- AG-UI is for agent interaction, not general application telemetry.
- Human gates and creative decisions are production records, not chat state.
- Development-agent guidance and runtime filmmaking skills remain separate.

Development agents modify the Cine Toaster repository and use `AGENTS.md` and
`ai-context/`. Production agents are product features that operate on a user's
film through the Agent Runtime. Never expose repository development memory as a
runtime filmmaking skill or production context.

## Current implementation direction

- Preserve the working Python runtime and CLI while boundaries are extracted.
- The next write milestone is selecting a take as an atomic canonical decision.
- React, Vite, and Tauri are strong UI/shell candidates, not permission to
  rewrite the Project Core.
- CopilotKit, AG-UI, editors, playback engines, and orchestrators require focused
  spikes before adoption.
- Use `Agent Runtime` in technical documentation. `AI Crew` is optional product
  language and is not an architectural component.

## Validation

Run the smallest relevant tests. The current repository-wide check is:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Code, comments, and repository documentation are written in English.
