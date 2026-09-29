---
id: CT-0035
title: Validation on a real production (SINGULAR) — what the demos did not catch
type: work
status: doing
owner: development agent
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - validation
  - real-production
  - screenplay
  - cuts
  - canvas
  - performance
---

# What

Plan steps 1–7 were validated only on the two demos. The user asked for a run
on SINGULAR (`~/confyui/singular`):

- a feature adaptation in the legacy Portuguese schema;
- 9 scenes, 242 shots, 208 takes, 5.7 GB;
- a screenplay in four arc files;
- LTX variants of the breakdowns.

Everything was run **read-only**: caches and job state went to a scratch
directory, and no file in the production changed.

# Results

Every step ran without an exception:

| Step | Result |
| --- | --- |
| `load_production` | 1.3 s |
| graph | 9 scenes, 242 shots, 208 takes |
| briefs | all 9 scenes |
| blocking frames | 136 frames (the 5 scenes with geometry) |
| FDX export | 615 elements |

It also exposed seven problems:

1. **Wrong screenplay, silently.**
   - `caminhos.roteiro: roteiro/v4` names a directory of four arc files, but
     only a single file is supported.
   - The loader fell back to the first `.fountain` anywhere in the project,
     which was `cenas/1-02/ltx/trabalho/Arco-I-antes-tripartida.fountain`,
     a work file.
   - Fix: accept a directory or an ordered list of files, and report a
     finding instead of guessing.
2. **No scene is linked to the screenplay**, so coverage (SPEC-0006) shows
   nothing. `toast script link` can propose links once item 1 is fixed.
3. **104 `shot_field_undeclared` findings.** These are legacy fields with no
   translation (CT-0016). The most common are:
   - `corte` (8), `quadro` (8), `seg` (8), `corpo` (7), `fade` (7),
     `cor_texto` (6);
   - `quem` (6), which is the list of who the shot is on;
   - `still` (6), `guias`, `variacao_clipe`, `pos`, `som_montagem`,
     `entra_sai`, `fala`.
4. **`corte` must not translate to `cut`.** Here it is a **trim**:
   - `{antes, depois}` are handles and `{inicio, fim}` are in and out points;
   - SPEC-0007's `cut` is the editorial join;
   - a naive mapping would break both. Trim needs its own field.
5. **Jump-cut false positives (most of the 11).**
   - 1-02 P16→P17 declare the same camera F. P16 is an insert of the
     emergency light; P17 is Claire's close-up (`quem: [CLAIRE]`).
   - The check sees only that one camera pose frames the placeholder subject
     "direita" in both shots.
   - Fix: when shots declare their subject, a jump needs the **same declared
     subject**; an insert is never a jump.
6. **A missing join type: continuation.**
   - 3-01 P3a→P3b is one continuous shot split across two generations ("exact
     continuation … from its last frame").
   - It is neither a cut nor a jump. SPEC-0007 needs
     `cut: {type: continuation}`: no visible cut, frame chaining expected, and
     the jump check off.
   - This is where the generation-unit question (CT-0022 step 4) first shows
     up in real data.
7. **The canvas does not scale.**
   - One scene has 62 shots in a single row. Fitting the view hits the
     minimum zoom, the cards are unreadable, and part of the film is off
     screen.
   - Every blocking-frame thumbnail reloads the whole production (1.3 s), and
     136 at once made **one request take 12.9 s**.
   - Fixes:
     - wrap long scenes into rows;
     - focus on a scene or sequence;
     - simplify cards when zoomed out;
     - cache the loaded production per request burst, keyed by file
       modification times.

Also noted: SINGULAR is not under version control. It is authored production
state with no history.

# Done (2026-09-29)

- **Safety first.**
  - Full backup: `~/backups/singular-2026-09-29`. The copy has 5,007 files and
    6.1 GB, and the checksum of every file matches the source.
  - `git init` in SINGULAR, tracking the 891 authored files. Media are
    ignored by its `.gitignore` and covered by the backup.
  - Every run since is read-only, and its `git status` stays clean.
- **Item 1 fixed.**
  - `paths.script` accepts a file, a directory (its `.fountain` files in name
    order), or an explicit list. Later files lose their title page.
  - A declared path that is missing, or several undeclared candidates, give
    no screenplay plus a `screenplay` attention item and `script_problem`.
    Nothing is guessed.
  - SINGULAR now reads `roteiro/v4`: four arcs, 112 scenes.
  - The Script room shows the file count, and `script export-fdx` uses the
    combined text. On SINGULAR it reports 62 sections, 14 synopses and 144
    `[[notes]]` that FDX does not carry.
- **Item 2.** `toast script link` on SINGULAR now proposes scene headings and
  per-shot coverage, for example 1-02 and 1-02A with exact line matches. It
  writes nothing; applying the links is the production's decision.
- **Item 3 re-diagnosed: not an application bug.** The legacy map in
  `vocabulary.py` is frozen ("nothing new is added here"). Pipeline fields
  such as `quadro`, `seg`, `corpo` and `cor_texto` belong in the production's
  own `shot_fields` declaration, and the finding asks for exactly that.
- **Item 5 re-diagnosed and improved.**
  - The breakdown declares the insert and Claire's close-up on the same
    camera F, with no lens or target of their own. On the declared data they
    *are* the same framing, so these are not pure false positives.
  - The check now skips pairs whose declared `subject`s differ.
  - The message says how to resolve it: give the insert its own camera, or
    declare each shot's subject.
  - SINGULAR declares no shot subjects (`quem` is not the core `subject`), so
    its 11 findings remain until the breakdown says whom each shot is on.
- **Item 7 fixed.**
  - The control room caches the loaded production for 2 s, and a command or
    an adoption clears it. A blocking-frame thumbnail went from 12.9 s under
    load to about 1 ms after the first load; 40 in parallel all finished
    within 10 ms.
  - The canvas:
    - wraps long scenes (8 shots per line), and a cut to the next line steps
      under the cards;
    - opens a large film on the active scene's sequence, with a selector for
      the whole film, a sequence or a scene;
    - fits the first scene in view;
    - renders only visible cards.

- **Decided with latitude from the user (2026-09-29):**
  - **Item 6:** `continuation` added to SPEC-0007 (amendment), with
    `continuation_unchained` and its practice.
  - **Item 4:** `trim` is recorded as a separate future field, specified when
    the assembly of generated takes exists. `corte` is never read as `cut`.
- **`seg` is duration, and SINGULAR's tools read it.**
  - `ferramentas/cena_ltx.py`, `revisao.py` and `trailer2.py` read `seg`, and
    several breakdowns are generated by scripts (1-02B, 1-02C, likely
    1-02A). Renaming keys in SINGULAR would break its pipeline, and the next
    generation would undo the change.
  - The legacy map stays frozen. Instead, a production declares what its
    fields mean: `shot_fields: {seg: {maps_to: duration}}`. The target must
    be a core shot field, and the alias applies only when the canonical key
    is absent.
  - Committed in SINGULAR's git: all 31 pipeline fields declared, `seg`
    mapped. The 104 undeclared findings are gone, and every scene now has
    its real duration (about 16 minutes in total).
- **Not applied, deliberately: screenplay links.** `script:` and `covers:`
  state what each shot films, which is an editorial decision of the
  production. The proposals match only identical lines and cover few shots.
  Generated breakdowns would lose them on regeneration, so their generators
  should emit them.

# To do

- In SINGULAR, as the production's decisions:
  - screenplay links, written by the generators for generated breakdowns;
  - shot subjects where one camera covers different framings;
  - `cut: {type: continuation, chain: frame}` on 3-01 P3b.

# Validation

- Probe script, server, and canvas screenshot on a read-only run.
- `find ~/confyui/singular -newer <probe>` returned no file; after the
  `git init`, `git status` stays clean.
- New tests:
  - `ScreenplayFilesTests` (5): directory order, list order, a missing
    declared path, ambiguous candidates, and a single undeclared file;
  - a jump test with different declared subjects;
  - a layout wrap test.
- Full suite: 337 tests OK; `frontend` has 5 tests and a clean typecheck.
