---
id: CT-0054
title: Migrating SINGULAR to ~/films/singular in Cine Toaster's native format
type: work
status: doing
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - singular
  - migration
  - validation
  - layout
---

# What

The validation milestone (backlog "Next" item 1) becomes SINGULAR's
migration, at the user's direction (2026-10-03): a repeatable tool
(`toast migrate`) reads `~/confyui/singular` and writes **`~/films/singular`**
in Cine Toaster's native schema -- not aliases. The original is never
modified and its tools keep working; if nothing from SINGULAR is missed,
the new directory becomes the working folder. Its organisation must make
the versions easy to see during production.

# Survey of SINGULAR (read-only, 2026-10-03)

5.8 GB: `cenas/` 3.2 GB (9 scenes; a scene may have two breakdowns, the
Wan one and `ltx/`, the production's `variante: ltx`; `versoes/` with
`VERSOES.md` -- a table of version, date, duration, what changed, the
author's notes, approval -- and `decupagem-vN.yaml` per version;
`trabalho/` with clips `cNN.mp4`, word sidecars `cNN.palavras.json`,
voices, pictures `pNN*.png`, `_tomadas/` alternative takes, `_descartados/`,
`partes/` intermediates; `teste/`; review PDFs), `sons/` 1.3 GB (library
with `MANIFESTO.csv`), `arquivo/` (pilot, trailers, casting test),
`cenarios/` (5 locations), `elenco/` (sheets, LoRA, motion, objects,
voices), `estetica/` (LUTs, visual grammar, `mundos.yaml`), `livro/`,
`roteiro/` (V4 generated from the author's V3), `sequencias/`, `docs/`,
`knowledge/`. `project.yaml` declares 31 SINGULAR-only shot fields.

# Layout (decided)

The user (2026-10-03): the evaluation and the decision are mine -- the
structure must run the film's production and keep the history of its
evolution. Evaluation: SINGULAR has no git; its history is its `versoes/`
folders (cut + breakdown + notes table), `.orig` files and screenplay
versions. Cine Toaster kept versions away from scenes, without the
breakdown that made them, and truncated the decision history at 200.
Decided in ADR 0021; the layout below stands.

```
~/films/singular/
  project.yaml       README.md (generated: scenes, status, latest version, pending)
  story/book/  story/screenplay/        cast/<person>/   locations/<place>/
  look/   sounds/   docs/   archive/    deliveries/
  scenes/<id>-<slug>/
    scene.yaml       the active breakdown
    versions/        vN.mp4 + VERSIONS.md (regenerated from the records)
    takes/<shot>/    takes with word timings
    pictures/        master pictures, 3D boards
    review/          review PDFs, direction notes
    archive/         the other breakdown, discarded takes, tests
  sequences/<id>/versions/
```

- Versions inside each scene, with a human index regenerated on every
  version and verdict, in SINGULAR's own table format; its history moves
  over (3-01: v2-v12 with notes, v12 approved). Needs a Cine Toaster
  change (today: `renders/assemblies/<scene>/`), an ADR.
- The active breakdown becomes `scene.yaml`; the other goes to `archive/`.
- Media copied, not hard-linked (SINGULAR's tools overwrite files in place).
- Working files (`trabalho/` intermediates, logs) stay out: disposable.

# Done: ADR 0021 implemented (2026-10-03)

- Versions in `<scene>/versions/` (and `sequences/<id>/versions/`) with
  `vN.scene.yaml`, the breakdown that made the version; `versions.py`
  regenerates `VERSIONS.md` after `record_assembly`, `review_assembly`,
  `record_sequence_version`, `review_sequence_version`.
- `history.jsonl`: every decision, append-only, deduplicated by command
  id (`state._journal`, `read_history`).
- Tests: the snapshot and the index with a verdict (`test_assembly`), the
  journal beyond 200 decisions (`test_history`).

# Done: the migration, pass 1 (2026-10-03)

`migrate.py`, `toast migrate singular <source> <target> [--replace]
[--proposals] [--no-git]`. Trial runs into a scratch folder only;
`~/films/singular` not written yet.

- Layout as decided; 4,448 files, 4.9 GB copied (never hard-linked), in
  about 50 s; the source verified untouched (no file newer than the run).
- Scenes: the active breakdown becomes `scene.yaml` in the English schema
  (scene and shot keys renamed; `ambiente` to an ambience from the sound
  catalog, `som` lists and `som_montagem` to catalog sounds; `fala` to
  `lines`; the variant dropped and the scene's own title kept); paths
  rewritten (`trabalho/` to `work/`, `../trabalho/` to the archived main
  breakdown's work, `propostas/` to `story/proposals/`); work keeps takes,
  pictures, voices and sidecars (`_tomadas`/`_descartados` to
  `_takes`/`_rejected`), leaves a run's scratch (`partes/`, logs); the
  other breakdown archived whole.
- History: every surviving cut becomes a version record with its date,
  length, what changed, the author's note and a verdict read from the note
  (approved; `not_sent` for "não enviada"; rejected for a sent version's
  critique; pending without a note) -- 33 versions, 3-01 v2-v12 with v12
  approved; the breakdown snapshots kept as `vN.decupagem.yaml` (history is
  not translated); `history.jsonl` and `VERSIONS.md` per scene; the
  overview `README.md`; sequences' versions.
- Cast: 7 sheets gathered from every scene (variants from `fichas` with
  their face pictures, every wording of a variant's description and of a
  voice kept, the most used leading); plan names by pose tied to their
  person. Looks: 1 look definition per id from the scenes' descriptions.
  Sounds: SINGULAR's library copied and registered with licences (relative
  paths). The author's proposals brought in. Git started for the text.
- `MIGRATION.md`: converted, approximated, read through the legacy
  vocabulary, kept as written.
- **Equivalence** (`migrate.compare`): scenes, shots, durations, labels,
  sources, engines, lines and takes identical across the 9 scenes and 242
  shots; findings changed only by checks the cast switches on: 4
  `cast_reference_missing` (Narrador, Enfermeira, Diretor have no face --
  a real gap) and 2 `voice_identity_restated` (1-03 "very tired", 3-01
  "weak, hoarse": a state mixed into identity -- real, for the author).
- Found and fixed in Cine Toaster on the way: scene discovery read an
  archived breakdown as the scene (archives and versions folders now
  never compete, ADR 0021); `cast_label_drift` accused poses ("Kael
  (sentado)") -- SPEC-0003 amended: a pose or mark is not a name.
- Tests: `tests/test_migrate.py` (layout, schema, takes, archive, history
  with verdicts, index, journal, cast, looks, overview, report,
  equivalence, the source untouched, refusals); `tests/test_cast.py`.

# Done: pass 2a, sources (2026-10-03)

- SINGULAR's source fields as native relations, their meaning read from
  its own `cena_ltx.py` (`origem`, `ultimo_quadro`): `usa`/`usa_de` ->
  `picture_of`, `usa_arquivo` -> `file`, `usa_ultimo_de` ->
  `last_frame_of`, `reusa` -> `reuses` ("1-02/ltx c03" -> "1-02 c03":
  variants are gone); `deriva` -> the native `derive {from, with,
  request}` (16 shots: picture planning with cast faces now works for
  them); `ref: false` -> `cast_references: false` (it was never a source).
- Paths out of the scene rewritten: the sets (`../../../cenarios/` ->
  `../../locations/`, 1-02A's blockouts).
- `compare` now checks every shot's sources after the intended moves, and
  that every file a shot points at exists in the migrated film -- which
  found the blockout paths. Result: identical, the 6 real findings only.

# Done: pass 2b, locations (2026-10-03)

- Each set of `cenarios/` becomes a location (`location.yaml` beside its
  `FICHA.md`): id from the folder, label from the sheet's title, the set's
  first descriptive paragraph, its reference pictures and blockouts. The
  sheet names its scenes in bold ("Cena: **3-01**"): read, not guessed;
  1-02 joins Claire's room by having the same set fragments as 1-02C
  (approximated). 3-02's corridor and 1-01's prologue have no sheet.
  Scenes say `location:`; the comparison stays at the 6 real findings.
  SINGULAR's `cenario` (prompt fragments for parts of a set: CABECEIRA,
  JANELA...) stays on the scene: its generators read it.

# Done: pass 2c, montage and pictures (2026-10-03)

From SINGULAR's own `cena_ltx.py` (`cartela`, the clip's video and audio
filters), each operation to a native home:

- on-screen text (`texto_tela`, `corpo`, `cor_texto`, `pos`, `fade`,
  `texto_entra`, `espacado`) -> a `title` from the catalog (`card`);
- `escurece` -> the new VFX effect `fade-to-black`; `espelhar` -> `mirror`;
  `recorte` (pixels of a 1280x704 take) -> `crop` (fractions) -- three
  built-in effects added to the catalog, category `frame`;
- `silenciar` -> `mute` (take seconds) and `som_baixa_de` ->
  `sound_fades_at` (seconds into the shot as cut): two new core shot
  fields the assembly applies to a take's sound (test in `test_joins`);
- `quadro` -> `picture` (what the video model is told the starting
  picture shows): Cine Toaster's own prompts now carry it.

Kept and declared, for SINGULAR's generators: `still`, `guias`,
`variacao`, `variacao_clipe`, `cam`, `in_frame`, `lira`, `entra_sai`,
`so_a_luz`, `imagem_autor`, `cast_references`, `cenario`, `mundo`,
`custo_estimado`, `fonte`; and four bespoke one-offs (`apaga_luz`,
`sobrepor`, `montagem_pov`, `ajuste_imagem`). The comparison holds: the
6 real findings only.

# Done: validation by assembling 3-01 against SINGULAR's approved v12 (2026-10-04)

The migrated 3-01 assembled by Cine Toaster (CPU, ~95 s a run) compared
frame by frame with SINGULAR's v12. Each difference became a fix:

- **Black shots were dropped** ("composed, not part of a take cut yet"):
  Cine Toaster now holds a `black`/`white` shot (engine `solid`) on screen
  for its duration, its sounds laid over it.
- **Auxiliary pictures** (`imagem` shots, e.g. 3-01 P2c: Claire in Líra's
  place for the POV overlay) were reported as takeless: the migration marks
  them `out_of_cut`, as SINGULAR always treated them.
- **The frame**: SINGULAR crops every take to 1280x536. A built-in format
  style `feature-scope` (2.39:1; aka scope, cinemascope, longa-metragem)
  and the migration sets the production to it: 3-01 comes out 1280x536.
- **Subtitles**: SINGULAR burns Portuguese lines under the English speech
  while the author reviews, the clean cut travelling with an .srt. Native
  now: `subtitles: {burn: true}` (production or scene); each line timed by
  SINGULAR's method (as many of the take's words as the line has, +0.35 s;
  a line laid in the mix at its time); `vN.srt` beside every version;
  burned when asked, smaller and lower than a format's captions.
- **P2's POV montage** (focus coming and going, Claire fading into Líra;
  SINGULAR's own `pov_foco.py`): its result is in the work folder as the
  POV take; the migration selects it, as a decision of its own with the
  reason, reversible. And SINGULAR keeps such a shot's opening (`corte`:
  ini_min 0 for `montagem_pov`): the migration writes `trim.in: 0`.
- **A take made from another** (`c02-pov` from `c02`) uses the original's
  word timings when it has none of its own (`assembly.sidecar_for`), for
  the trim and the subtitles.
- SINGULAR's word sidecars (`[start, end, word]` triples) are read.

Result: the same 25 shots in the same order, lengths equal to the
hundredth except frame rounding (SINGULAR rounds each piece up a frame),
88.35 s against v12's 88.66 s; the same frame, the same subtitles at the
same moments, the same POV opening. Tests: subtitles (timing, the .srt,
burning), black shots, derived word timings, the migration's POV take,
trim and production format.

# Done: every scene assembled against SINGULAR's latest cut (2026-10-04)

| scene | Cine Toaster | SINGULAR | |
|---|---|---|---|
| 1-01 | 74.9 s | 75.1 s | equal; the narration was missing -- fixed |
| 1-02 | 222.0 s | 222.7 s | equal |
| 1-02A | 36.8 s | 85.3 s | SINGULAR's state, not a loss (below) |
| 1-02B | 67.5 s | 67.6 s | equal |
| 1-02C | 115.8 s | 116.1 s | equal |
| 1-03 | 86.4 s | 86.6 s | equal |
| 1-04 | 55.5 s | 55.6 s | equal |
| 3-01 | 88.4 s | 88.7 s | equal (frame by frame, above) |
| 3-02 | -- | -- | not produced in SINGULAR either |

Fixed on the way:

- **Narration** (`falas: [{montagem: {arquivo, em}}]`, SINGULAR's
  voice-over): a line with `mix: {file, at}` is not said in the take (the
  reader no longer looks for its words); the assembly lays its file at its
  time, brought to speech level, counted as speech (music ducks under it,
  the 5.1 puts it in the centre); its subtitle at its time, on a take, a
  card or a black shot. The migration writes `mix: {file, at}`.
- **Reused clips**: a shot with no take of its own and `from: {ref: "1-02
  c03", relation: reuses}` takes that clip from the other scene's work.
- **Reframe notes** summarised in one line per scene.

**1-02A**: its breakdown was rewritten after its last cut (its header:
"imagens-mestre em duas etapas, lição de 19/09"); 16 of its shots were
never generated since -- SINGULAR has no clip for them either (the last
cut's pieces in `partes/` are cropped, mixed intermediates, not takes).
Cine Toaster reports them as without a take: the truth. The last cut is in
the scene's versions.

**Word timings missing in SINGULAR** for the newer clips of 1-02C (8
shots) and 1-03 (10): both tools cut those shots by duration (the lengths
agree), but subtitles of those lines span their whole shot. Next: a job
that transcribes the takes that have no word timings (faster-whisper, in
the voice environment), so trims and subtitles follow the speech.

# Done: `toast transcribe` (2026-10-04)

A `transcribe` job (`words_worker.py`, faster-whisper small on the CPU in
the voice environment): the speaking shots' takes without word timings
(their own or their original's) are transcribed and their sidecars written
in the production's form; `toast doctor` now reports transcription as used
(it looked in the wrong environment). On the scratch copy: 1-02C (8 takes)
and 1-03 (10) in about 3 minutes each.

**A creative effect, the author's to decide**: with word timings, speaking
shots are cut around the speech (Cine Toaster's rule, SINGULAR's too when
it had the words): 1-02C 115.8 -> 110.6 s, 1-03 86.4 -> 71.8 s. SINGULAR
cut them by their declared durations only because the timings were
missing. So the migration does not transcribe; the author runs it when
they choose, and the subtitles of those shots span the shot until then.

# Pass 2 (next)

- `cenario` and the plans (`geografia`) into locations; `referencias_3d`.
- SINGULAR's montage operations (`silenciar`, `escurece`, `espelhar`,
  `recorte`, `apaga_luz`, `so_a_luz`, `sobrepor`, `fade`, `entra_sai`,
  `ajuste_imagem`) into effects and titles; screen text (`corpo`,
  `cor_texto`, `pos`, `texto_entra`) into titles.
- Generation prompts (`quadro`, `still`, `cam`, `variacao*`, `guias`,
  `in_frame`, `lira`) -- they feed SINGULAR's own generators.
- Then run into `~/films/singular` and validate there: assembling real
  scenes against SINGULAR's own cuts.

# Then

1. ~~ADR: per-scene versions and `VERSIONS.md`; implement.~~ Done.
2. `toast migrate`: field by field (SINGULAR's 31 keys to native fields or
   catalogs), with a report of converted / approximated / unhoused.
3. Validate in the new directory: checks, storyboard, assembling real
   scenes against SINGULAR's own versions.
