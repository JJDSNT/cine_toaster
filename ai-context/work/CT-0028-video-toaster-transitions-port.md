---
id: CT-0028
title: A separate project porting Video Toaster transitions to gl-transitions
type: work
status: ready
owner: unassigned
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - transitions
  - glsl
  - separate-project
  - future
---

# What

Start a **separate repository**, outside Cine Toaster, that recreates the
classic NewTek Video Toaster switcher transitions as gl-transitions shaders
(the contract in `docs/transition-library.md`). The finished shaders can be
proposed upstream to gl-transitions. Cine Toaster then receives them the same
way it receives every other shader: through the `vendor/gl-transitions`
submodule, reviewed with a manifest (`CT-0026`).

# Why

The user asked for it (2026-09-29). Cine Toaster is named after the Video
Toaster, and the Amiga reel already hand-writes two Toaster-like effects
(`switcher-flip`, `diamond-wipe`). A dedicated project keeps a bank of
effects, with its own licence and upstream path, out of the application
repository.

# Constraints

- The Video Toaster, its effects, and its assets are NewTek's, now Vizrt's.
  The port **recreates the look from observation**: footage, manuals, and
  descriptions. It never extracts or copies effect files, ROM data, or
  artwork from Toaster disks. This is the same rule ADR 0011 applies to
  copyleft code.
- Name the shaders descriptively (for example, `toaster-style-page-peel`).
  Use Video Toaster only in descriptions, as a reference to the style.
- MIT licence, so the shaders can go upstream and into the submodule.
- Effects that need a texture or a matte wait for a texture-input contract,
  which gl-transitions supports only in `luma` and `displacement`.

# To do

1. Create the repository. **Its name and location are still undecided.**
2. List the Toaster effects worth porting from public reference footage, with
   a source for each.
3. For each effect: write the shader, a preview, and a note on what it
   recreates.
4. Propose them upstream, or point `CINE_TOASTER_TRANSITIONS_PATH` at the
   repository until they are accepted.

# Decisions

- Separate repository, not a directory in Cine Toaster.

# Validation

- Not started.
