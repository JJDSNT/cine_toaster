---
id: CT-0035
title: Validation on a real production (SINGULAR) — what the demos did not catch
type: work
status: ready
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

# To do

Fix items 1, 3 (translations only; `corte` stays untranslated), 5 and 7
before plan step 8. Items 4 and 6 are specification changes for the user to
confirm.

# Validation

- Probe script, server, and canvas screenshot on a read-only run.
- `find ~/confyui/singular -newer <probe>` returned no file.
