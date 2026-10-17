---
name: runpod-comfyui
description: Develop Cine Toaster's RunPod/ComfyUI generation paths -- add or change a generation recipe and its provider adapter, wire a ComfyUI API-format workflow, prepare or diagnose the serverless endpoint and network volume it needs, and test it without paid jobs. Use when work touches src/cine_toaster/providers/ (runpod, comfyui, ltx, qwen_edit), providers/recipes.py, knowledge/providers/, or a RunPod endpoint. Development only -- never a runtime filmmaking skill.
---

# RunPod / ComfyUI generation paths (development)

This skill is for agents **building Cine Toaster**. It is not product context
and is never packaged for production agents (AGENTS.md, ADR 0034). Production
agents see generation through recipes (`toast recipes`, MCP
`list_generation_recipes`) and the Generation Operations role.

## Use what already exists first

This skill adds only Cine Toaster's boundaries and code paths. For RunPod
itself -- onboarding, account and API configuration, templates, endpoints,
volumes, GPU choice, the CLI -- load the **official RunPod plugin** skills,
installed for Claude Code and Codex: `runpod` (the router, with live-verified
golden paths such as `02-comfyui-pod`, `05-model-to-endpoint-pipeline`,
`09-custom-serverless-dev-loop`), `runpod-templates` (the official ComfyUI
template: what it ships, its ports and paths, what is missing on first boot,
repairing imported workflows), `runpodctl`, `runpod-usage`, `runpod-mcp`.

Measured, production-specific knowledge from SINGULAR lives in
`~/confyui/.claude/skills/` (`ltx`, `camera`, `diretor`, `previs3d`). It is
the source `knowledge/providers/ltx-2.5.md` was migrated from. **Read it,
never run its tools**, and treat it as evidence measured under its own
conditions, not as an oracle: it already contradicts itself (idle 1800 s
noted, 60 s found on 2026-09-21).

## Boundaries that do not move

- The product touches only the **data plane**: submit a job, poll it, read
  `/health` (`providers/runpod.py`, `providers/recipes.py`). Creating,
  scaling or changing endpoints, pods, volumes and templates is done with
  runpodctl, the RunPod console or the RunPod MCP tools -- by you, with the
  author's go, never by Cine Toaster code.
- **Money:** say the hourly price before creating anything billable and wait
  for the author's explicit yes. Do not delete or stop a resource you did not
  create in this session unless the author names it.
- **Never run SINGULAR's tools** (`~/confyui/singular`), not even modes that
  claim to be read-only: they have written into that production before.
- Secrets never appear in output, files or commits. Credentials come from the
  environment or an `--env-file` (`load_credentials`, never printed); store
  tokens on RunPod as secrets, not plain environment values.
- Tests never send a real job: every adapter takes a `transport`, and tests
  script it.

## Adding or changing a generation path

1. **Workflow.** Export the ComfyUI graph in **API format** into
   `providers/workflows/`. Overrides are applied **by node type**, never node
   id (`comfyui.patch_workflow`): ids change on every re-export.
2. **Adapter** in `providers/`: the narrowest protocol that the production
   uses (`ImageToVideoProvider`, `PictureProvider` in `providers/__init__.py`).
   Keep its numbers as module constants (rate, execution and cold-start
   seconds, limits): the recipe reads them, it does not copy them.
3. **Recipe** in `providers/recipes.py`: what it makes from what in a film's
   words, kind, transport, inputs, `endpoint_env`, `credentials_env`, the
   workflow path, the knowledge notes it cites, and a `numbers` function that
   imports the adapter's constants. `workflow_models()` derives the model
   files the endpoint's volume must hold -- check them against the volume.
4. **Doctor**: a `toast doctor` row per RunPod recipe (`doctor._recipe`).
   A capability that fails only when used is the failure AGENTS.md forbids.
5. **Knowledge**: measured behaviour goes in `knowledge/providers/<id>.md`
   claims (status, measured_on, evidence, impact, workaround). A claim
   describes the conditions it was measured under; it is not forever (see the
   roadmap's open design on knowledge that evolves, and its demotion rule).
6. **Tests** with a scripted transport: the patched graph, the payload, the
   state file refusing a different pending request, the result recorded with
   provenance. `tests/test_providers.py`, `tests/test_recipes.py`.

## Preparing an endpoint (outside the product)

- Follow the RunPod plugin's golden path for the case (a ComfyUI pod to
  build and try the graph; model-to-endpoint for serverless) and its
  `runpod-templates` skill for the official ComfyUI image; add the custom
  nodes the graph's `class_type`s need.
- Put the model files `toast recipes` lists on a network volume. A volume
  pins the endpoint to its data centre, where the GPU may be scarce.
- **Pin the allowed GPU types** (measured: the platform otherwise swaps to a
  slice where the LTX image fails at 0 s).
- Set the endpoint id in the environment variable the recipe names, then
  `toast recipes --health <recipe> --env-file <file>` reads workers and queue.

## Diagnosing a failing path

Read in this order: the job record (`error`, state file beside the take),
`toast recipes --health <recipe>`, the recipe's known failures (`toast
recipes`), then the worker logs with the RunPod tools. Measured patterns:

- a job that disappears returns 404: terminal, resubmit (`runpod.py` does);
- workers sharing one output directory overwrite each other unless each job
  has its own `filename_prefix` (`runpod._unique_output_prefix`);
- a first job after idle is a cold start of minutes (`cold_start_seconds`).

When you measure something new, add or update the claim with its conditions
and date, and record any limitation in the roadmap with how to solve it.
