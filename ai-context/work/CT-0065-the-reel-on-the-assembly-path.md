---
id: CT-0065
title: The reel on the assembly path -- stills as takes, narration beside the scene
type: work
status: doing
owner: unassigned
created_at: 2026-10-13
updated_at: 2026-10-13
tags:
  - demos
  - assembly
  - narration
  - takes
---

# What

Step 1 of CT-0064: the Amiga Demo Reel is assembled like any film
(`toast assemble`, `toast assemble-sequence`), with the defects its probe found
closed.

# Why

`toast build` draws text cards only; titles, effects, sound and transitions
over moving video live in the assembly. Everything the reel is to become
(CT-0064) is built on that path, so the reel has to be on it first.

# Done

- **A still is a take.** A `.png`, `.jpg`, `.jpeg` or `.webp` take is held for
  the shot's duration (3 s, and said, when the shot gives none), with titles,
  effects and transitions like a clip (`assembly.STILL_SUFFIXES`,
  `Segment.still`). A moving take decides the version's frame and rate; a
  still does only when a scene has nothing else. Before, the assembly refused
  the scene with "The cut leaves nothing of the take (0.00-0.00 s of 0.00 s)".
- **`toast voice`** is now `narration.speak_lines`:
  - it writes a line's `mix.file` beside the scene's breakdown, where the
    assembly reads it. This closes CT-0063's "one convention for `mix.file`";
  - each line is spoken in its own voice (`voice: piper/<id>`), else `--voice`,
    else the default. A line in a voice that is not offline is refused;
  - what was spoken is recorded beside the audio (`<file>.provenance.json`:
    provider, model, text, who). A line whose words or voice changed is spoken
    again; audio with no such record is kept, since it may be a recording.
- **Checks.** `line_audio_missing` accepts the scene's folder only, and says
  when the file sits at the production root. New `line_audio_stale` (warning):
  audio spoken before the line changed. Both under the practice
  `every-line-is-filmed`.
- **The reel.**
  - Its cards are titles: a production-owned `titles/reel-card` (the catalog's
    card in the reel's palette, not faded, as its look asks), replacing `text:`.
  - A scene's first join is its `enter` (SC-020 by `amiga-copper-bars`, SC-040
    by `analog-scan`), which the sequence assembly renders; before, it sat on
    the first shot, where only `toast build` read it.
  - `toast assemble-sequence <project> <sequence> --scenes` assembles each
    scene, then the sequence; `make build` uses it.
  - README and `project.yaml` no longer say there is no TTS or that the reel
    exists to prove two projects stay independent.
- **Bringing material in**: `commands.add_take` and `toast take add <project>
  <scene> <shot> <file> [--name] [--kind captured|archival] [--source]
  [--licence] [--credit]`. The file is copied beside the scene (`work/cNN.ext`
  for a shot's first take, `work/_takes/cNN-<name>.ext` after), and its origin
  is written next to it (`<file>.provenance.json`: kind, source, licence,
  credit, the file's name and SHA-256, when and by whom), which the take
  already shows as provenance. Archival footage with no source or licence is
  refused; nothing already there is replaced. Emits `take.added`.
- **A trial on real pictures** (scratch copy, not in the repository): three
  NASA clips (Artemis I launch, Earth from the ISS, Orion's view of the Moon
  crossing the Earth) brought in with `toast take add --kind archival`, cut
  with `cube`, `inverted-page-curl` and `doorway` from gl-transitions, a
  lower third and `old-film`. 19.2 s, every join rendered by its shader over
  moving video. Kept for the user at
  `~/cine-toaster-references/trials/footage-trial-v1.mp4`; the downloads are in
  `~/cine-toaster-references/open-footage/`.
- **`toast build` kept** as the quick slideshow: it draws a titled card by its
  words, reads a scene's `enter`, and finds the narration beside the scene.

# To do

0. **Replace the reel's content whole.** The user saw the cards assembled
   (2026-10-14) and rejected them: nothing of the previous reel is to be
   kept. What is in `examples/amiga-demo-reel` now is a placeholder that
   keeps the fixture and its tests working. The footage trial was "a little
   better", not good: its sources were 720p and 360p, its titles defaults.
1. ~~Footage that is fetched rather than checked in~~ done as CT-0066.
2. ~~Decide whether `toast build` stays~~ -- removed in CT-0072. It now duplicates a poorer form of the
   assembly; removing it touches the `build` job, the control room and
   `docs/jobs.md`.
3. Not looked at: a title card taking its colours from the production's look
   rather than restating them in `titles/reel-card`; a first shot's
   `transition` that nothing renders is not reported by `toast check`.

# Decisions

- **The reel's cards became catalog titles**, rather than the assembly
  learning `text:` cards: one way to make a card, the one every film uses.
  `text:` stays in the schema; the reel no longer uses it.
- **The narration is not checked in.** CT-0017 decided it would be, when the
  tool could not make it; the repository never held it. Now the tool makes the
  same file from the same line, so the reel declares it and `make build`
  speaks it. CT-0017's Done list is wrong on this point.
- **Stale narration is remade without asking**, because it is offline, free and
  reproducible. Audio the tool did not record as its own is never overwritten
  without `--force`.
- **NASA footage is recorded as "Public domain (NASA media usage
  guidelines)"** with the item's page as its source and the credit NASA gives.
  That is this record's reading of NASA's guidelines (not copyrighted, no
  endorsement implied, third-party material excepted), not a legal review; an
  Envato Elements clip the user asked about was set aside because its
  subscription licence does not allow the files to be redistributed.
- **A file at the production root is left where it is.** `toast voice` says it
  is not read by the cut and makes the line beside the scene; it does not move
  or delete what it cannot prove it made.

# Validation

- `tests/test_narration.py` (4): audio beside the scene and one voice per line;
  a changed line stale, then respoken; a recording kept and a root file not
  heard; a non-offline voice refused.
- `tests/test_joins.py`: a still held 2 s after a clip, joined by a dissolve, in
  the clip's frame and rate.
- `tests/test_schema.py`, `tests/test_build.py`, `tests/test_jobs.py` pass with
  the reel's new form.
- By eye, on a scratch copy: `toast voice` then `assemble-sequence the-reel
  --scenes` gives 25.75 s, every card and all five transitions present.
- `tests/test_add_take.py` (4): the first take in the cut with its origin; a
  second as a named alternative, nothing replaced; archival without source
  and licence refused, nothing written; a file that is not media refused.
- Full suite: 621 tests pass (2026-10-14).
