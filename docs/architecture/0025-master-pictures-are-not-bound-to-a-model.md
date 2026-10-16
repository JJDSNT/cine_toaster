# ADR 0025: A master picture belongs to the film; the model that makes it is the adapter's

Status: accepted (2026-10-16, CT-0102, at the user's word: "master pictures,
by principle, should not be fixed to Qwen; each initiative could change the
model").

## Context

Master pictures (CT-0037) were made one way: SINGULAR's, a 3D render
repainted by Qwen Image Edit on Runpod. `pictures.py`, which is the Core's,
imported Qwen's price, prompt wording and sizing and wrote
`model: qwen-image-edit` into every record; the job built the Qwen adapter
directly; and `derive.from` was required, because Qwen can only repaint.
A production with no render to repaint -- an animated film whose pictures
come from a description, the cast and a style (Demo 01, CT-0099) -- had no
way to make a master picture. The architecture's invariants say the Core
holds filmmaking concepts, not provider logic.

## Decision

- A picture adapter answers one interface (`providers.PictureProvider`):
  whether it needs a source picture, how a request is worded, the size, how
  it is paid (`usd`, held by the budget, or `quota`, a subscription's:
  recorded, never priced), its estimate, and `make(...)`, which returns its
  provenance. Each model's rules stay in its adapter (Qwen's geometry
  clauses, padding and size; Codex's image roles).
- The adapter is chosen like a style, the nearest level winning:
  `pictures: {provider}` in `project.yaml`, then in a scene, then
  `derive.provider` on the shot. Default: `qwen-image-edit`, so a production
  that says nothing behaves as before.
- `derive.from` is required only by an adapter that `needs_source`. The edge
  score is the film's measure of fidelity to a source, whatever made the
  picture, computed when there is a source.
- The record names the provider, the level that chose it and the cost kind.
  The job keeps Qwen's remote-job and spend records; a quota-paid adapter
  writes neither and spends no dollars.

## Consequences

- Adapters today: `qwen-image-edit`, `codex-image` (CT-0101). A third (a
  Gemini adapter, roadmap) is one class and one entry in
  `picture_providers()`.
- Comparing models for the same shot is a matter of `derive.provider` and
  versions side by side, not a fork of the pipeline.
- Video generation (LTX) is still bound to one adapter; the same move applies
  when a second video model is wanted.
