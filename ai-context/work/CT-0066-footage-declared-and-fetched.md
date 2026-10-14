---
id: CT-0066
title: Footage from outside, declared in the breakdown and fetched
type: work
status: done
owner: unassigned
created_at: 2026-10-14
updated_at: 2026-10-14
tags:
  - demos
  - takes
  - provenance
  - footage
---

# What

A shot says which stretch of which public file its picture is (`footage:`),
and `toast footage fetch` brings that stretch in as the shot's take, with its
source, licence and credit beside it. Step 2 of the order in CT-0064.

# Why

The demos are to be made around open-licence footage (the user, 2026-10-13).
The sources are 20 MB to 6 GB each: they cannot be kept in the repository or
in a wheel, and `toast take add` (CT-0065) only copies a file someone already
has. A production must be able to say what it uses and get it again on
another machine.

# Done

- **`footage:` on a shot** (a core field, `vocabulary.CORE_SHOT_FIELDS`):
  `url`, `page`, `in`, `duration` (the shot's when left out), `licence`,
  `credit`. Parsed by `footage.read`.
- **`footage.fetch`** and **`toast footage fetch <project> [--scene]`**: for
  each shot that declares footage and has no take, FFmpeg reads the stretch
  straight from the address (it seeks in the remote file; the whole file is
  never downloaded), re-encodes it (x264 CRF 16, AAC), keeps it in
  `~/.cache/cine-toaster/footage/` and adds it through `commands.add_take` as
  an `archival` take. A shot with a take is kept as it is.
- **`height:`** on the declaration fetches the stretch at that many lines
  (a 4K original at 1080, say); the file's own size when left out. Added
  after the first commit, for the music piece: thirteen 4K stretches at
  1080 lines in 2 min 23 s.
- **The take records the excerpt**: `add_take(excerpt=...)` writes `{url, in,
  duration}` into the origin beside the take.
- **`toast footage list`**: what each shot declares and whether it is here.
- **Checks**, under the new practice `footage-carries-its-origin`:
  `footage_incomplete` (error: no address or no licence, or an address that
  cannot be fetched) and `footage_not_fetched` (advice).

# To do

- Fetching runs in the foreground, not as a job: no progress, no cancel.
- Only the picture's first audio track is taken; a stretch is not trimmed to
  frame boundaries of the source beyond what re-encoding gives.
- A changed declaration (another `in`, another file) does not replace the
  take that is there; the person removes the take and fetches again.

# Decisions

- **Declared on the shot, not in a file of sources.** The licence and the
  credit are facts about a picture in the film; the shot is where the film
  says what its picture is. The take's own record repeats them, as a
  generated take's provenance does.
- **Only the stretch is fetched.** A first version downloaded the whole file
  into the cache; the Earth footage's original is 6 GB for 6 s of use.
- **The cache is outside the production and disposable**, like every other
  cache (the invariant in `AGENTS.md`); the take inside the production is
  what the film keeps.
- **No licence, no fetch.** The address alone is not enough: footage nobody
  can account for is refused before anything is read.

# Validation

- `tests/test_footage.py` (3): advice until fetched and an error without a
  licence; nothing read when the declaration is incomplete; a stretch of a
  local `file://` clip becomes the take with its origin and excerpt, 2 s
  long, and a second fetch keeps it.
- For real, on a scratch production: 6 s at 47 s of NASA's Artemis I launch
  original (538 MB, 3840x2160) and 6 s at 240 s of "Earth Views from the ISS"
  (6 GB, 1280x720 at 59.94) fetched in 54 s together, 16 MB and 5 MB.
- Full suite: 621 tests pass (2026-10-14).
