---
id: CT-0068
title: A production says its frame
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - demos
  - assembly
  - formats
---

# What

Point D2 of the demos line: the size and rate every version is made in,
declared once in `project.yaml` (`frame: 1920x1080@29.97`).

# Why

A version took the size and rate of its first moving take. The music piece's
footage is 4K at the source; to get a 1080-line piece, every stretch had to be
fetched at 1080 lines by hand (CT-0064). A scene opening on a 4K take would
have made a 4K version beside 1080-line ones.

# Done

- `formats.parse_frame`: `WIDTHxHEIGHT@FPS`, `WIDTHxHEIGHT` (the rate is then
  the first moving take's), or `{width, height, fps}` with `fps` as a number
  or a ratio (`30000/1001`). Even sizes only, a rate between 1 and 240.
- `load_production` puts it on the production and on every scene; a frame that
  cannot be read goes to the production's attention list, and versions fall
  back to the first moving take's.
- `assembly.render` makes the version in it (`Plan.frame`); the sequence
  assembly too; a format's aspect is reframed from it as before.
- `toast footage fetch` fetches a stretch at the production's height when the
  declaration gives none.

# To do (solvable limitations, also in the roadmap's D7)

- A scene cannot set a frame of its own (a vertical insert in a wide film).
- `toast build` draws at a fixed size and ignores the frame.

# Decisions

- **`frame`, not `format`**: `format` is already the production's description
  ("Music piece · 41 seconds") and a style's format axis (CT-0049).
- **A bad frame does not stop the production loading**: it is put to the
  person, and versions are made as they were before.

# Validation

- `tests/test_frame.py` (4): the forms it is written in; refusals; every scene
  carries it; an unreadable one reaches the attention list.
- `tests/test_joins.py`: 160x90 takes at 24 fps make a 320x180 version at 25.
- `tests/test_footage.py`: footage with no height is fetched at the frame's.
- For real: a scene opening on a 3840x2160 take at 29.97 in a production
  declared `1280x720@25` gave a 1280x720 version at 25 fps; the music piece
  declared `1920x1080@29.97` gave v4 at that size and length (41.441 s).
- Full suite: 634 tests pass (2026-10-14).
