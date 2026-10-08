# CT-0076 — Model-dependent mood and visual identity

Status: research / discovery, 2026-10-08. Parent research: contextual filmmaker UX (CT-0066–CT-0073). Related: CT-0074/75, moodboard visual style investigation.

## Production observation

In Singular master-image generation, the user observed a markedly different **texture and mood** between the Codex image generator and Qwen, despite an intended common visual direction. This is a first-hand qualitative observation, **not** a controlled benchmark or evidence that either model is universally superior. Capture the actual inputs, model versions, outputs, seeds/settings, conditioning and postprocessing before attributing differences to model alone.

## Separate the concepts

- **Authorial language**: recurring direction grammar (e.g. unsettling ambiguity, controlled symmetry, gothic stylization). Lynch, Kubrick and Burton are examples of distinct cinematic languages, not one fixed mood per director.
- **Visual style**: palette, lighting, contrast, lens, grain, material treatment, composition.
- **Scene mood**: intended audience atmosphere (unease, grief, tension), which can vary by scene.
- **Character performance/emotion**: acting and microexpression, not equivalent to visual mood.
- **Model/workflow rendering signature**: tendencies of a specific model + version + conditioning + settings + postprocess.
- **Continuity**: degree to which approved visual identity survives master image, image-to-video, VFX, edit and grading.

A moodboard supplies references; it is not a complete semantic mood specification. Do not force mood into one text field or collapse these axes into one hierarchy.

## Pipeline hypothesis

Creative intent and approved references -> capability-aware candidate model/workflow selection -> image masters -> human review/approval -> downstream shots, video, VFX, edit, grading -> continuity checks.

Blender can supply coherent spatial conditioning to generative models, not necessarily a filmmaker-facing navigation tool. Unreal is a **planned investigation** and may serve overlapping or complementary 3D/world/render roles; do not assume Blender is its mandatory upstream or that interchange is lossless. Model capability and spatial reference are independent axes.

## UX questions

1. Can the filmmaker state mood and visual direction without first choosing a provider?
2. Can the UI compare candidate master images **side by side**, including differences in texture, lighting, mood and continuity?
3. Does each candidate reveal its model/version, workflow, reference inputs, conditioning, settings and provenance on demand?
4. Can an approved master become a reference for subsequent environments and shots, without silently replacing creative intent?
5. When a new model/workflow is selected, can the user preview drift, explicitly approve it, or revert?
6. Can the user navigate intent -> approved master -> generated shot -> edit, while distinguishing original direction from model interpretation?

## Experiment: Codex vs Qwen

Use the same Singular hospital shot brief, spatial reference (if supported), approved style references, aspect ratio and target output. Record model/version, parameters and unsupported controls; do not claim equivalent conditioning where APIs differ. Generate multiple candidates per model to separate model signature from sampling variance. Review blinded where practical.

Evaluate: (a) narrative and spatial fidelity, (b) perceived mood, (c) material texture, (d) lighting/palette, (e) consistency with adjacent approved masters, (f) controllability and repeatability, (g) cost/latency. Human creative approval is primary; automated scores are advisory, not an objective mood truth.

## Open architectural decisions

- Whether a Visual Direction Profile should be a distinct concept or a projection over existing project/sequence/scene look/style and references.
- Whether provider capabilities are represented in the existing adapter registry or require extensions.
- How approved master-image provenance and continuity checks fit existing decisions and human gates.
- How spatial inputs from Blender or Unreal flow to model-specific conditioning.
- Which UX controls belong in each workspace; use progressive disclosure.

## Acceptance scenarios

- Same hospital brief, two image models, visibly different interpretations, both inspectable and comparable.
- Approve one master; generate corridor with a different model; flag possible aesthetic drift without automatically rejecting it.
- Preserve shared hospital geometry while permitting different moods between Claire's room and corridor.
- Execute a simpler project with no 3D source, and another with a future Unreal adapter.
- Trace decisions through master, video, VFX and final edit.

## Guardrails and next steps

Research first: inspect existing look/style/reference/decision/provenance APIs; inventory actual supported image model controls; validate experiment with real assets. No new schema, default model, director-style preset, or automated mood scoring is approved by this document. Maintain UX-first scope and complete end-to-end pipeline flexibility.
