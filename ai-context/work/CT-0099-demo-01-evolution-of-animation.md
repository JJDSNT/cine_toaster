---
id: CT-0099
title: Demo 01 -- the evolution of animation, as a production and a trial of the tool
type: work
status: doing
owner: claude-code
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - demos
  - animation
  - style
  - cast
  - providers
---

# What

The first demo, replacing the hybrid VFX micro-scene (CT-0097, paused). A
girl crosses the wild -- grass, a run, waterfalls, a climb, the summit --
while the animation evolves from its early days toward the contemporary and
what comes next, ending on "Something new is coming". 90-150 s. The style
changes during the action, never by stopping it. Cinematic quality over a
catalogue of features.

The film is `~/films/demo-01` (`toast new`, CT-0098). The user (2026-10-16):
"at once the demo's production and a test bed of Cine Toaster" -- every step
is also a trial, and every time the work leaves the tool is a finding.

# Why

It tests the product's central promise on screen: the film's identity and
decisions hold while the instruments change. Here the instrument (the
technique of animation) changes inside the film, and the character must
remain herself.

# Hypotheses (the validation of this record)

1. **Identity holds across styles.** One cast sheet: who she is, with a
   variant per era and age; the face and drift checks work across very
   different techniques.
2. **Style is a recorded decision.** Each era is a style record a scene or
   shot names; changing an era shows what is stale.
3. **Phase 1 costs nothing.** Screenplay, a 3D blockout of the landscape,
   camera moves and an animatic, approved before any paid generation.
4. **The change happens inside a movement.** One era to the next during a
   single action, by generation between frames, by compositing, or both.
5. **The director decides.** Masters per era and takes are the user's; an
   agent works through MCP within the gates.

# Decisions (the user's, 2026-10-16)

- She **matures** with the animation, child to young woman -- intended.
- The evolution is of the **language of animation**, not toward
  photorealism.
- Deer and butterflies are characteristic of some eras: they may stay as
  era motifs (the fawn came from the draft's prompt, not the concept).
- Three prompts, apart and continuous: her **identity**, the **aesthetic
  evolution**, each **shot's cinematography**. In Cine Toaster terms, to be
  verified: the cast sheet, the style records, the breakdown's shots.
- The user's ChatGPT/Codex subscription quota may be used for images.
- Script, breakdown, final look and model choices belong to pre-production.

# Done

- Film created: `toast new ~/films/demo-01 --id demo-01` (working title
  "Something New Is Coming").
- The ChatGPT draft board filed as a reference
  (`references/2026-10-16-chatgpt-draft/`: image, prompt, the user's notes
  on it, observations: her face drifts within an era, the costume carries
  her identity, Disney-like designs to avoid).
- Codex probe (`references/2026-10-16-codex-probe-1930s/`): one image from
  the board as reference. Findings:
  - `codex exec "<prompt>" -i <image>` -- the prompt must come before `-i`,
    which takes several files and otherwise swallows it; stdin closed.
  - The built-in `image_gen` saves to
    `~/.codex/generated_images/<thread>/exec-<id>.png` (1536x1024 here);
    no destination argument. About two minutes.
  - The model is not reported; the cost is subscription quota, reported only
    as the agent's tokens -- `toast finops` cannot see it.
  - Identity from the reference came through (hair, dress, sash); the era did
    not (a modern storybook pencil, not 1930s technique).

# To do

1. ~~A `codex-image` provider adapter~~ done (CT-0101). Its first run, the
   1930s era trial (`references/2026-10-16-era-trial-1930s`, 57 s): her
   identity held strongly, the era only partly (period background, grain,
   flat greys; no rubber-hose limbs or pie-cut eyes). Asking to keep her face
   exactly fights redrawing her in an era's technique -- identity and era
   pull apart, which is what hypotheses 1 and 2 must settle: identity as
   features and costume, not as a drawn face to copy.
2. The cast sheet: identity prompt, ages, a variant per era.
3. The eras: choose 4-6 and write each as a style record (technique, not
   characters).
4. Identity trial: her in every era, through the adapter.
5. Transformation trial: one era to the next inside one run.
6. Screenplay, breakdown, blockout, animatic; storyboard approval.

# Frictions (work that left the tool)

- No place for film-level references: made by hand first, then built as a
  capability on the user's word (CT-0100); demo-01's two references
  converted to it. Writing the first record by hand produced invalid YAML
  (a colon in a note) -- the command's dumper avoids that.
- Image generation through Codex is outside the tool. Solve: the adapter
  (To do 1).

# Validation

- Not run yet: the hypotheses above are checked as the film is made.
