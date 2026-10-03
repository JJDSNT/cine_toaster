---
id: CT-0039
title: What Cine Toaster and SINGULAR can learn from each other
type: work
status: done
owner: development agent
created_at: 2026-09-29
updated_at: 2026-10-03
tags:
  - real-production
  - roadmap
  - assembly
  - generation
---

# What

Lessons from working on both. SINGULAR is ahead in phase 2 practice
(generation, montage). Cine Toaster is ahead in structure and verification
(phase 1, records, checks). Agreed with the user on 2026-09-29, including the
priority order below.

# Cine Toaster, from SINGULAR

1. **Speech-aware trims.** SINGULAR cuts a take around its declared speech,
   using word timings, and skips the generation's still opening (0.35 s). The
   assembly used the shot duration instead: 3-01 came out at 98 s against
   94.85 s.
2. **Loudness per clip**, measured on speech only. The target is −20 LUFS,
   with a smaller boost allowed for silent shots, so room tone is not
   amplified.
3. **Measured generation rules become knowledge.** SINGULAR has dated
   measurements buried in code comments:
   - the model's own cut rhythm;
   - a guide at frame 0;
   - frame counts in multiples of 8;
   - generations of 1–20 s.

   They belong in the provider adapter and in evidence-linked practices.
4. **Existing lineage and cost.** `<clip>.job.json` records the endpoint,
   worker, execution time and hash. Take discovery can read it.
5. **Master image from a blockout.** SINGULAR already renders a Blender
   blockout (`rA`) and turns it into a photograph (`mA`), with edit lineage
   (`base` → `mask` → `qwen`). This is CT-0025 step 4 with CT-0029 stage 2.
6. **Montage features**: subtitles, voice mixing, layers, overlays, muted
   stretches. They map to CT-0031 catalogs and an audio track.
7. **Review exports**: review PDFs and contact sheets.

# SINGULAR, from Cine Toaster

1. **Geometry with the real cast.** The subjects are the placeholders
   `ESQUERDA` and `DIREITA`, and 4 of 9 scenes have no geometry. Declaring
   shot subjects makes the axis, eyeline and jump checks meaningful, and
   gives every scene blocking frames and previs.
2. **Screenplay links written by the breakdown generators** (`script:`,
   `covers:`).
3. **Intentions as records, not prose**: `cut: {type: continuation, chain:
   frame}`, inserts, reverse shots.
4. **Never lose a version.** Regeneration overwrites `c08.mp4` and
   `cena-3-01.mp4`. Use takes in `_takes/` and assembly versions, and a
   storage policy for media, since git covers only text.
5. **Retire tools gradually.** Montage moves to Cine Toaster once items 1, 2
   and 6 above exist. Generation stays in SINGULAR's tools until the adapter
   exists.

# Order

1. Speech-aware trims and loudness in the assembly.
2. Read `.job.json` as take lineage and cost.
3. Measured LTX rules into knowledge and the future adapter.
4. SINGULAR: cast subjects and geometry; generators writing screenplay links.
5. Sequence assembly, then the generation adapter (needs a budget).

# Done

- **Item 1: speech-aware trims and loudness** (2026-09-29).
  - `assembly.py` cuts a take around its **declared** speech: 1.0 s before
    the first word and 0.9 s after the last, SINGULAR's margins. A line
    marked for the mix only (`mix: true`, SINGULAR's `montagem: true`) does
    not count. Detected words alone never decide.
  - It skips a generated take's still opening (0.35 s). An explicit `trim`
    (`in`, `out`, `head`, `tail`, `before`, `after`, `to_end`) wins.
  - Word timings come from a sidecar named by the production
    (`words_sidecar`, default `{stem}.words.json`).
  - Loudness per take: speech to −20 LUFS, measured on the speech; other
    sound to `level_db` (−34 by default). A silent take gets a boost of at
    most 3 dB.
  - The core gained `level_db` and `in_take` on lines, accepts a single line
    mapping, and `maps_to` can rename keys inside a value (`keys:`).
  - SINGULAR maps `fala`→`lines`, `corte`→`trim` (with its keys),
    `nivel`→`level_db`, and `words_sidecar: "{stem}.palavras.json"` (commit
    in its git).
  - **Validation:** on a copy of SINGULAR, Cine Toaster's cut points for
    3-01 equal those of SINGULAR's own `corte()` on **20 of 21 shots**, to
    the hundredth of a second. The exception is P2, a POV shot
    (`montagem_pov`), which SINGULAR does not trim at its opening; that is a
    production-specific rule, left as a known difference.
  - Tests: speech cuts, sidecars, `in_take`, key renaming. Full suite: 378
    OK.
- **Item 2: job lineage and cost** (2026-09-29).
  - Take discovery keeps a provider's `<take>.job.json` as it is, under
    `provenance.job`: the Core preserves it without interpreting it.
  - A block slice carries its block's generation record, marked `shared_by`.
  - `costs.py` and `toast costs <project>` report GPU time and estimated cost
    per scene. Time comes from the platform's record (queue, cold start and
    execution). The rate comes from the production's `generation_rates`, or
    the LTX adapter's assumed US$ 1.75/h, and the report says which. A shared
    block generation is counted once.
  - SINGULAR: 81 generations with records, 148.2 GPU minutes, about US$ 4.32
    at the assumed rate.
  - Endpoint check (read-only): `ltx25-i2v` runs on the ADA_48_PRO pool.
    **Its environment holds a HuggingFace token in plain text**, visible to
    anyone with read access to the endpoint. It should be rotated and moved
    to a RunPod secret. Reported to the user; the value was not recorded
    anywhere.
- **Item 3: measured rules as knowledge** (2026-09-29).
  - Built-in provider profiles: `knowledge/providers/ltx-2.5.md` (16 claims)
    and `runpod-serverless.md` (4 claims). Each claim has a status, a
    measurement date, evidence in SINGULAR, an impact and a workaround.
  - The sources are SINGULAR's production diary
    (`docs/SINGULAR-PROXIMOS-PASSOS.md`) and the dated comments in
    `cena_ltx.py`.
  - High-impact claims:
    - the model reads acting direction aloud;
    - an off-screen line comes out of the visible mouth;
    - the text must match the first frame;
    - multi-shot cuts follow the model's own rhythm;
    - frame 0 must be guided;
    - the platform can swap the GPU silently;
    - endpoint environments expose secrets.
  - The generation adapter (plan step 9) will read these profiles rather than
    re-encode them.
  - Tests: a built-in profile test; the coverage test now counts built-in
    claims. Full suite: 383 OK.
- **Geometry names fixed.** SINGULAR's plans already name their people
  (`{nome: Claire, rotulo: esquerda}`). Cine Toaster was reading the
  screen-side note as the name; the person's name now wins, and findings
  speak of Kael and Claire.
- **The user chose to keep production decisions in SINGULAR's own folder**
  while focusing on direction and production. They are recorded in
  `singular/docs/SINGULAR-CINE-TOASTER.md` (committed in its git), with a
  pointer from `SINGULAR-PROXIMOS-PASSOS.md`. The list covers screen flips,
  jump cuts, continuations, missing geography, screenplay links, Kael's
  voice, the endpoint token, and media backup.
- **Item 4 (SINGULAR geometry with cast subjects; generators writing screenplay
  links) is held for the user.** Placing cameras and characters and saying
  what each shot films are creative and editorial decisions of the
  production.
- **Item 5: sequence assembly as versions** (2026-09-29).
  - `sequence_state.py`: versions in `sequences.state.json`, beside the
    manifest that declares the sequences (ADR 0006: runtime state beside the
    authored file, written atomically by commands).
  - Commands `record_sequence_version` and `review_sequence_version` (with
    events); `POST /api/sequence-review`.
  - Job kind `assemble_sequence`. Each scene enters by its approved version,
    or else its latest, with a note either way. It is not re-levelled, since
    it was levelled when assembled. The result is adopted to
    `renders/sequences/<sequence>/<version>.mp4` and registered with the scene
    versions it holds.
  - `toast assemble-sequence <project> <sequence>`.
  - The Sequences room shows versions with player, verdict and "Assemble a
    new version".
  - Validation: `tests/test_sequence_versions.py` (3 tests); a headless run in
    which a version was assembled, adopted and approved from the Sequences
    room. Full suite: 386 OK.

# Validation

- Evidence gathered on SINGULAR, read-only or on scratch copies.
- Declared speech against detected words: in 2 of about 80 clips, words were
  detected in shots declared silent (3-01 P8, "Halts the reactor."; 1-02 P40,
  breathing). Trims must follow **declared** speech, not detected words.

# Closed (2026-10-03, close-out pass)

All of the Cine Toaster side of the order is delivered: speech-aware trims and loudness, `.job.json` lineage, LTX rules in knowledge, sequence assembly, the generation adapter.

What remains moved to the backlog (`development/roadmap.md` § Backlog): SINGULAR's side (cast subjects and geometry, generators writing screenplay links), for its author.
