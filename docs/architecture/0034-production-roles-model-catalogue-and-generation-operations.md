# ADR 0034: Production roles are declared; models are described, not chosen; generation operations are a role, not an infrastructure agent

Status: accepted (2026-10-17). Extends ADR 0017, 0029-0033.

## Context

Four production roles (Inception, Art Direction with Visual Prevalidation,
Directing with Continuity) were added to the one CoAgent graph (ADR 0029-0032).
Each added its own prefixed fields to one shared state (about 35), its own
reset in the Coordinator, its own routing and its own copy of the reason/tool
loop. Every further role multiplies that. The model was one injected adapter
for every role, and visual input was detected by duck typing (`ask_images`
existed only on the Codex CLI adapter).

KDP Studio (a sibling tool by the same author, built on the same ADR 0017
pattern) faced the same growth with thirteen agents and resolved it with
*agents as manifests* (its ADR 0019) and *one flow for every agent's work*
(its ADR 0020): direction is data; checks are deterministic and named; landing
is a command; review is another agent; nothing is redone unasked; the wait is
checkpointed beside the job store and survives a restart.

The author also asked whether a RunPod/ComfyUI agent should exist, and stated
that Cine Toaster must be agnostic about models: it uses whatever model the
person makes available, and may keep a table of what models can do.

## Decision

1. **A production role is a declaration** (`agents/roles.py`): id, title,
   kind (`coordinator`, `author`, `reviewer`, `technical`), the model
   capabilities it needs, its per-turn budgets, and its scratch fields (reset
   each turn) and kept fields. The graph's state shape and the one reset are
   derived from the declarations.
   Roles whose behaviour is read-and-answer should become pure data (KDP
   Studio's rule: read-and-answer in a manifest, measure-and-build in code);
   roles that generate, wait or publish stay in code on the shared loop.
2. **Models are described, never chosen by Cine Toaster.** The person supplies
   the model (host flag, environment, or the CLI they are running, unchanged
   from ADR 0017). A **model catalogue** (`agents/model_catalog.yaml`, extended
   by `$XDG_CONFIG_HOME/cine-toaster/models.yaml`) records what each adapter's
   transport can carry (structured output, images, web) and, per known model,
   its context size, strengths and cost class, with the source of each claim.
   Capabilities are declared by the adapter (`Model.capabilities`); a role
   that needs one the configured model lacks stops honestly, and `toast doctor`
   names which roles the configured model can serve.
3. **A person may bind a role to another model they supplied** (for example
   an independent reviewer on a different provider), in the same user file.
   Absent a binding, every role uses the one model provided. Binding never
   triggers an executable or credential scan.
4. **Every adapter that can carry images does.** Claude CLI (stream-json
   input, as KDP Studio validated) and Claude API join Codex CLI.
5. **RunPod/ComfyUI is three layers, none of them an infrastructure agent:**
   - *Generation recipes* (data): registered, versioned descriptions of what
     a ComfyUI/endpoint graph does in filmmaking terms -- inputs, required
     models, VRAM, rate, endpoint variable -- with the graph itself kept
     inside the provider adapter (ADR 0025's "not bound to a model" holds).
   - *Generation Operations* (a `technical` production role, "render
     wrangler"): Cine Toaster-vocabulary tools only -- capability and
     endpoint health, estimates, job status, failure diagnosis, retry with the
     same quota consent rule, recipe validation against an endpoint. Mostly
     deterministic; the model explains and chooses among recipes. It owns
     continuation when a job finishes, which closes the "bounded wait" gap.
   - *A development skill* (`.agents/skills/runpod-comfyui/`) for development
     agents building worker images, endpoints and recipes with the RunPod
     tooling. It is never packaged as a runtime filmmaking skill.
   Creating pods, endpoints or volumes stays outside the product
   (runpodctl, the RunPod console or MCP, a person).

## Consequences

- Adding a role is one declaration plus its handler, not edits in four places.
- Durable continuation follows KDP Studio's measured shape: the human wait or
  job wait alone in its node, checkpointed on disk beside the job store, the
  work rebuilt from records on restart. It is still separate work.
- The typed resume of an approved decision (today encoded in a message id and
  page-context strings) is recorded as a follow-up of the same refactor.
- The catalogue's strengths are descriptive and editable; a wrong entry
  misleads a person, never routes work by itself.
