---
id: CT-0019
title: Two halves of the interface, and an address for each room
type: work
status: done
owner: unassigned
created_at: 2026-09-22
updated_at: 2026-09-22
tags:
  - interface
  - navigation
  - storyboard
---

# What

Split the interface into the half that asks what a scene is and the half that
asks whether a shot is good, give every room an address, and make a scene show
something other than text.

# Why

From using it: *"como eu opero isso... tenho um bocado de informação que não sei
bem o que fazer com ela"*. Three defects underneath that, each measurable.

The interface had no routing. `setView` swapped the workspace and toggled a
class; the file contained no `pushState`, `replaceState` or `popstate`. The back
button left the application, a reload lost the room, and a scene could not be
sent to anyone. The vocabulary already existed -- boot read `view`, `scene` and
`shot` from the URL -- and was never written.

The render was invisible. `toast build` wrote `renders/amiga-demo-reel.mp4` and
the only path by which the interface could show an assembled file was a
`sequences[].render` field nothing filled. The tool built something and did not
show it.

A composed scene had nothing to look at. Composed shots produce no takes, the
comparison room draws only takes, and the cards the build drew were written into
a scratch directory and deleted. The single image a scene could have had was
thrown away.

And the rooms were all one half. Scenes, shots, review, continuity, blockout,
decisions, transitions, knowledge: every one asks whether something is good.
Nothing asked what it was.

# Done

- Routing. `remember()` writes the address, `showAddress()` renders whatever it
  says, `popstate` calls it. Back, forward, reload and a shared link all work;
  the first entry replaces rather than pushes, so leaving the first screen exits
  cleanly.
- `discover_renders()` and `discover_stills()`: found on disk, never declared,
  on the rule already established for takes. No manifest field was added.
- `build` keeps its cards in `stills/<scene>/<shot>.png` instead of discarding
  them with the scratch directory, and reports how many it kept.
- `/api/writing` and `writing_room()`: the screenplay, the frames of each scene,
  every spoken line, and a cast counted from the lines themselves.
- Four rooms: **Script** (screenplay, direction, open questions), **Storyboard**
  (a filmstrip per scene), **Dialogue** (cast and a dialogue sheet), and **Cut**
  (what has been assembled, with a player).
- The sidebar is three blocks -- Writing, Production, Reference -- instead of one
  flat list.
- Every empty room says what to do rather than being blank.
- `tests/test_writing.py` (10), plus stills coverage in `test_build.py`. Suite
  at 187.

# To do

- The Last Signal has a screenplay and an open question but no stills, because
  its shots are `generated` and that build path does not exist.
- Editing from the writing rooms. They read today; committing a line or a
  storyboard decision goes through application commands like every other write.
- A storyboard frame that is authored art rather than a drawn card.

# Decisions

- **Renders and stills are discovered, not declared.** ADR 0010's reasoning
  applied again: a declaration is a second copy of a truth the filesystem holds,
  and the second copy drifts. It also meant no schema change for either.
- **Two halves, because attention is what they divide.** The data was never
  separable -- a scene's lines and its takes are the same file. What differs is
  the question being asked, and a room answers one question.
- **An empty room explains itself.** The reel has no screenplay; the Script room
  says to point `paths.script` at one and shows the scene direction meanwhile. A
  blank panel teaches nothing.
- **The cast is counted, never declared.** Until `cast` exists as an entity
  (SPEC-0003), the dialogue is the only statement of who speaks, so the room
  reads it rather than asking for a second list that could disagree.

# Validation

- Full suite: 187 passing, up from 177.
- Over HTTP against the built reel: `/api/writing` reported 4 scenes, 7 frames,
  7 stills, 1 line, 1 speaker; `/media/renders/amiga-demo-reel.mp4` served
  100,559 bytes and `/media/stills/SC-020/P1.png` served 15,793.
- The Last Signal exercises the other side: a real `story/screenplay.fountain`
  read into the Script room, one open question, and no stills.
