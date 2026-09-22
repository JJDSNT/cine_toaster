---
id: CT-0018
title: A clone that installs, reports, builds, and plays
type: work
status: done
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - onboarding
  - providers
  - render
---

# What

Make a fresh clone reach a watchable file without borrowing anything: install,
a truthful capability report, offline narration the tool owns, and a render.

# Why

The repository had no installation instructions at all, and nothing in it
produced a pixel or a sound. `toast demo` copied files; the interface read YAML;
the checked-in takes were hand-made stubs.

The transition catalog was the same shape of gap as the interface: a real GL
Transition v1 contract with editorial metadata and three override layers, and
no scene or shot able to name an item in it, and no renderer able to execute
one.

The narration made the point sharply. It had been generated with another
project's Piper installation and committed here — an asset this repository could
not reproduce, which is worse than not having one. Cine Toaster is the tool; a
demo built with tools the tool does not have proves nothing about the tool.

# Done

- `doctor.py` and `toast doctor`: every capability with what it enables and the
  exact command that installs it. Leads with what works.
- `Makefile`: `setup`, `demo`, `build`, `voice`, `serve`, `check`, `test`,
  `doctor`. `setup` ends by running the doctor, so the last thing an install
  prints is the truth about that machine.
- `README.md`: an installation section, the three commands, the two demo
  productions, and **Toward a complete studio** — the toolchain the project
  grows into, separated into what is in use and what is not called yet.
- `AGENTS.md`: how to get the repository running, and the rule that a new
  capability which can be absent is added to the doctor.
- `providers/piper.py`: offline narration. The voice model downloads once into
  the production, not into a home directory, so a film carries the voice it was
  narrated with.
- `toast voice`: speaks the lines the production already cast and placed. It
  refuses a destination it cannot write rather than writing a different file.
- `build.py` and `toast build`: cards drawn from the look, cut together on the
  declared transitions, audio mixed, mp4 written to `renders/`.
- `[render]` in every transition manifest: how that item renders on each engine
  that can execute it, declared by the item.
- The look cascade is applied at load: every shot carries its look and the level
  that decided it.
- `tests/test_doctor.py` (8) and `tests/test_build.py` (6). Suite at 177.

# To do

- Run GLSL through ModernGL, so a shader is executed rather than approximated.
  `amiga-copper-bars` currently renders as `wiperight` and says so.
- Wire SoX, Blender and transcription, each currently detected and reported as
  not called.
- The remaining shot families from CT-0017: sound and image operations.
- The Last Signal as the dramatic half, and the screenplay, storyboard and
  dialogue rooms it gets built against.

# Decisions

- **The borrowed narration was removed, then remade by this tool.** Committing
  a file the repository cannot reproduce gives an asset no provenance and no way
  to be remade.
- **A transition declares how it renders; the renderer never guesses.** An item
  with no rendering for the engine in use is refused, with the two ways out
  named. `amiga-copper-bars` declares `wiperight` and a note saying the copper
  bars are lost — a substitution nobody chose is a substitution nobody can argue
  with, which is ADR 0007's rule about the axis applied to editing.
- **`toast voice` refuses a non-WAV destination** rather than writing a WAV next
  to the name that was asked for. Silently writing a different file is the same
  failure as a command that does nothing and succeeds.
- **The doctor separates what is in use from what is merely present.**
  Reporting Blender as working when nothing calls it would be a lie told by the
  one command whose job is to tell the truth.
- **The demos are created outside the checkout.** The first Makefile put them in
  `./local-projects` and CT-0007's guard refused it. The guard was right; the
  override exists for fixture development, not for working around the rule.
- **An existing environment is not assumed usable.** `uv venv` without `--seed`
  creates one with no pip, and every install into it then fails while appearing
  to succeed. `make` now verifies and repairs it.

# Validation

- From a clean copy with no `.venv`: `make setup` reported every capability
  present, `make demo` created both productions outside the checkout and
  checked them, `make test` passed.
- `toast voice` spoke the reel's line: 3.8 s of WAV, `$0.00`, offline, with the
  voice model downloaded into the production.
- `toast build` rendered the reel: 7 shots, 5 transitions, 15.7 s, h264 +
  aac, 1280x720 at 30 fps, verified with `ffprobe`. A sampled frame shows the
  look's palette applied to the card.
- The refusal path was observed rather than assumed: building against a
  materialised demo predating the `[render]` blocks failed with the message
  naming the transition and both remedies.
- Suite: 177 passing, up from 145 at the start of this work.
