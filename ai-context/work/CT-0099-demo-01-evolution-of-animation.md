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

The first **complete, end-to-end demo**, replacing the hybrid VFX micro-scene
(CT-0097, paused) as the first one to be finished. The checked-in productions
such as `examples/demo-project` (The Last Signal) and Amiga Demo Reel are
fixtures and incomplete productions at the same portfolio level, not earlier
finished demos or quality authorities. A
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

- This is the first demo that must traverse the whole production flow and end
  as a complete, watchable film. Existing example productions may confirm file
  syntax and regress behavior, but do not define its creative standard or its
  done state.
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
- Generated pictures are never deleted or overwritten when a later attempt is
  preferred. Keep every pass with its prompt, lineage and review; version and
  reject with a reason instead of erasing production history (the user,
  2026-10-16).
- Left to the agent's judgment (the user, 2026-10-16), revisable at the
  screenplay: **seven eras**, one per beat of the journey -- 1910s ink on
  paper (age 6, waking), 1930s rubber hose (8, the meadow, fawn and
  butterfly), 1940s-50s classic colour (10, into the forest), 1960s graphic
  limited (12, the run accelerates), 1990s painted anime (14, waterfalls and
  the leap), 2000s-10s CG feature (16, the climb), painted 3D now and next
  (18, the summit). **The fawn** only in eras 2 and 3: it stays at the
  forest's edge as she starts to run -- childhood left behind, told by the
  action. Her name: **Lia**.

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
- Identity trial generated for all seven eras
  (`references/2026-10-16-identity-era-{1..7}/`) and reviewed as one
  sequence. The stable identity is presently the silhouette and performance:
  long dark moving hair, light linen dress, red-brown sash, bare feet and an
  eager forward motion. The face is recognisably related through eras 1--6,
  but this is not yet evidence that facial identity survives ageing.
- The director's original eleven-panel board was reviewed at full resolution,
  not only through its written record. Its essential continuity is spatial and
  kinetic: meadow to forest to water to mountain to a summit above the clouds;
  the last panel's planet-like luminous arc is the first glimpse of the
  "something new". The screenplay keeps that journey as one place and one
  action rather than reproducing the board's panel collage.
- Canonical screenplay: seven continuous exterior scenes, no dialogue, about
  100 seconds. Its linked breakdown is 24 shots in one sequence, `The Ascent`,
  with every screenplay unit covered. The planned duration is 103 seconds.
- A controlled late-age pass was generated as three new, immutable references,
  with no picture parent: `age-control-14`, `age-control-16` and
  `age-control-18`. No earlier generated picture was removed or overwritten.

## Identity-trial review, 2026-10-16

- The trial exposed a confound: eras 1--6 all use the same eight-year-old
  picture as their visual parent. The image condition dominates the textual
  ages. Eras 1--5 read as roughly the same child, and era 6 (declared sixteen)
  reads younger again. Era 7, generated without that picture after an image
  safety refusal, is the only one that reads clearly as a young adult.
- The ageing hypothesis therefore remains open. This is not fixed by calling
  one of the seven pictures Lia's master face: no face is approved yet.
- The style records are useful, but the stills show a second distinction the
  product must keep visible: historical craft versus a contemporary
  illustration that quotes its surface. Era 1 has the iris, ink and paper but
  a modern character design; era 2 has monochrome, grain and broad forms but
  not a convincing rubber-hose body or pie-cut eyes; era 3 is a lush modern
  cel/anime hybrid more than a 1940s--50s cel frame. Eras 4 and 5 communicate
  their intended graphic and painted-anime languages most clearly. Era 6
  communicates CG rendering, but not Lia at sixteen. Era 7 communicates the
  destination and age, while its facial continuity cannot be judged from the
  rear three-quarter view.
- Before another seven-picture pass, run a smaller controlled trial on the
  difficult bridge: Lia at fourteen, sixteen and eighteen, described from the
  cast sheet without the eight-year-old image as a parent. Compare that with a
  second pass conditioned by a newly approved older Lia only if the director
  chooses one. This separates age control from face-reference control.
- The controlled 14/16/18 trial confirms that the eight-year-old visual parent,
  not an inability to express age, caused the first pass's age collapse. The
  new fourteen-year-old reads as an adolescent in the painted-anime language;
  the sixteen-year-old reads as a strong older teenager in CG; the
  eighteen-year-old reads as a young woman in the final painted-3D language.
  Their faces are related but not locked -- appropriate style-dependent
  redesign remains mixed with uncontrolled facial drift. Hair, linen dress,
  sash, bare feet and forward bearing remain the more reliable identity.
- `age-control-18` is the strongest adult-anchor candidate because it shows her
  face and full silhouette, unlike the earlier rear three-quarter summit still.
  It remains a candidate, not an approved master face: that decision is the
  director's.

## First screenplay treatment

One continuous ascent, approximately 100 seconds, without dialogue. Each era
changes while Lia is already moving; no shot exists only to display a style.

1. **Wake (6, ink on paper):** an unfinished ink line finds Lia asleep in tall
   grass. Sunlight touches her eyelids. She sits, sees a butterfly and follows.
2. **Discover (8, rubber hose):** her first running step lands in a meadow whose
   curves bounce to the score. A fawn joins the chase. Lia chooses the path into
   the trees rather than catching the butterfly.
3. **Leave (10, classic colour):** colour blooms as she enters the forest. The
   fawn stops at its edge. Lia notices, hesitates for one beat, then runs on;
   childhood is left behind by action, not exposition.
4. **Accelerate (12, graphic limited):** trunks, shadows and Lia's stride reduce
   to rhythmic shapes. The path climbs and tightens. Repeated cycles shorten
   until one stride breaks the pattern.
5. **Leap (14, painted anime):** that stride becomes a leap across a waterfall
   chasm. For the first time she nearly falls, catches the far ledge, laughs at
   the fear and pulls herself up.
6. **Climb (16, CG feature):** the landing continues into a steep rock face.
   Volume, hair, cloth and light arrive with the effort. Near the summit she
   slips, steadies herself with the sash, and chooses the last hold.
7. **Arrive (18, painted 3D):** her hand crosses the lip already changing into
   the final language. She reaches the summit at sunrise. The landscape holds
   every earlier world far below, not as a montage but as one continuous place.
   She looks beyond the horizon, where the faint arc of another world catches
   the new light. Title: **SOMETHING NEW IS COMING.**

# To do

**Process correction:** [CT-0103](CT-0103-demo-01-process-and-gui-incident.md)
records the director's discovery that the visual storyboard stage was skipped
and the launched GUI lacked the assistant. The 24-shot breakdown is textual;
the visual storyboard is incomplete. Validate the screenplay/storyboard GUI
path before expanding the blockout. Existing render experiments remain useful
evidence, not proof that the upstream stage was completed.

1. ~~A `codex-image` provider adapter~~ done (CT-0101). Its first run, the
   1930s era trial (`references/2026-10-16-era-trial-1930s`, 57 s): her
   identity held strongly, the era only partly (period background, grain,
   flat greys; no rubber-hose limbs or pie-cut eyes). Asking to keep her face
   exactly fights redrawing her in an era's technique -- identity and era
   pull apart, which is what hypotheses 1 and 2 must settle: identity as
   features and costume, not as a drawn face to copy.
2. ~~The cast sheet~~: `cast/lia/character.yaml` -- identity as features
   and costume, a variant per age (6..18) with `face_changes`; no master
   face until the director approves one from the trial.
3. ~~The eras~~: `styles/era-1..7/style.toml` (kind animation, craft words
   only, no studio's characters); `pictures: {provider: codex-image}`.
4. Identity trial: generated through the adapter from the records
   (`--cast LIA@age-N --style era-N`); first pass and controlled 14/16/18 pass
   reviewed above. Left: the director's decision about a master face.
5. ~~Turn the treatment into the production screenplay and breakdown~~: seven
   scenes, one sequence, 24 covered shots, 103 seconds.
6. Transformation trial: one era to the next inside one run.
7. Complete and review the visual storyboard, refine with geography/blockout
   and animatic as needed, then request human storyboard approval.

## Opening blockout pass, 2026-10-16

- Added the shared location `THE-ASCENT`, the production look `ascent-light`,
  and original butterfly and fawn cast sheets. The location records the
  connected landscape; individual scene patches still need measured layout.
- SC-010 has its first measured patch, three start cameras, camera end poses,
  Lia and butterfly marks, subject movement and the intended exit state. The
  opening camera move is a crane down, as the measured poses require.
- Rendered the first six 640x360 boards (each shot's start and end), their
  depth maps, a board sheet and the 12-second animatic through `toast board`.
  These are the initial outputs in `renders/boards/SC-010/`. Preserve this
  pass before requesting another render: these commands use fixed filenames.
- Inspected P1-start, P2-start, P3-end and video samples at 2, 6 and 10 seconds.
  The frames validate camera scale and a tracked subject. The nearly empty
  patch does not provide enough parallax to judge the running speed well.
- The mannequin remains upright during the scripted waking action. The USD
  exporter explicitly supports no pose or rig, so these frames cannot validate
  sleeping, sitting or standing performance.
- The butterfly is represented as a small cube at ground level. The exporter
  places object subjects at half their object height; `eye_height` is not a
  flight elevation. Flying height and the later vertical climb therefore need
  an actual representational solution before the complete animatic can claim
  to validate them. No fake elevation was encoded into another field.
- `toast brief` still reports a missing aesthetic despite `look: ascent-light`
  on the project and a valid look record. Record this inheritance mismatch for
  diagnosis before duplicating the look declaration throughout the scenes.
- Next: preserve this first render pass, give the measured patches readable
  landscape landmarks, and resolve elevation/pose requirements in proportion
  to what the animatic must prove. Complete the remaining six scene layouts.
  Storyboard approval and master-face choice remain open human decisions.

# Frictions (work that left the tool)

- `toast new` starts no git; the film's history was started by hand
  (migrate's `.gitignore`, `git init`). In the roadmap.
- The three prompts (who, how, what) had to be pasted together by hand:
  `references generate --cast --style` now composes them from the records.

- No place for film-level references: made by hand first, then built as a
  capability on the user's word (CT-0100); demo-01's two references
  converted to it. Writing the first record by hand produced invalid YAML
  (a colon in a note) -- the command's dumper avoids that.
- Image generation through Codex is outside the tool. Solve: the adapter
  (To do 1).

# Validation

- Inception GUI review (2026-10-16, CT-0105): the director clarified that the
  second age-control pass corrects insufficient maturation in the first
  identity pass. `creation/state.json` now records both exploration rounds
  and the three explicit earlier/current correction pairs for ages 14/16/18,
  with the director's statement as source and Codex as recording agent. The
  13 reference records/images remain unchanged; correction intent is not a
  master selection, storyboard approval or proof of a successful fix.
- The seven identity pictures were inspected together at original resolution;
  their prompts, visual parents, cast variant and style record were compared.
- The original board and the three controlled age pictures were also inspected
  at original resolution. The latter were generated through the production's
  `codex-image` adapter, each without a picture parent and as a new reference.
- `toast references list ~/films/demo-01`: all thirteen reference records load with
  no findings.
- `toast script show ~/films/demo-01`: seven linked scenes, 24 shots, every
  screenplay unit shown under a shot.
- `toast status ~/films/demo-01`: `The Ascent`, 24 shots awaiting generation,
  zero of seven storyboards approved.
- `toast check ~/films/demo-01`: no continuity findings; geography has not been
  authored yet, so spatial continuity is not validated by this check.
- Opening blockout: `toast check` now reports only the expected
  `cast_reference_missing` warning for Lia in SC-010; the earlier move-name
  mismatch and unknown butterfly cast entry are resolved. Six scenes still
  have no geometry, so this is not a whole-film spatial validation.
- `toast board frames ... SC-010 --end --width 640 --height 360`,
  `toast board sheet ... SC-010` and `toast board animatic ... SC-010 --width
  640 --height 360 --step 2` succeeded. FFprobe confirms H.264, 640x360,
  12 fps, 144 frames and exactly 12 seconds. This pass has no sound or character
  performance animation.
- `git diff --check` passes for the development-repository changes.
- The five hypotheses remain production validations; none is marked complete
  merely from this still-image trial.
