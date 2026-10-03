# The 3D storyboard

The scene's plan (room, set pieces, people, one camera per shot) is built
in 3D from the USD export and rendered by Blender in a board's look:
grey clay by default (`--look colour` for the plan's colours), studio
light, shadows, outlines, mannequins for people.

```bash
toast board frames <project> SC-030 [--shot P3] [--end]   # renders/boards/SC-030/P3-start.png (+ -depth.png)
toast board sheet <project> SC-030                       # the boards on one labelled grid
toast board animatic <project> SC-030                    # renders/boards/SC-030/animatic.mp4
```

## Two products, kept apart

- **Boards are composition.** One still per shot -- its start, and its end
  if asked -- with a depth map (near is bright). A board fixes where the
  camera stands, the lens, and where people and things are. It is a
  starting picture for a master image:

  ```yaml
  derive: {from: board, with: [MARA], request: The mannequin becomes her, in the station's light.}
  ```

  (`board:end` for the last moment.) A board drawn before the plan last
  changed is reported when the picture is planned.

- **The animatic is for checking.** The whole scene played through each
  shot's camera, the people moving as the plan moves them: timing, sides of
  the axis, who is in frame -- the screenplay and the breakdown, checked by
  eye. It is not given to any model.

**No animation controls generation.** Mannequins have no rig and no pose;
motion curves and timing never reach a video model, whose movement stays
described in words (the camera-move catalog, the action). The 3D fixes
composition at the start, nothing about how the shot moves.

## One scale of framing

Every shot is named by the same rule, measured on its plan: how much of the
frame's height the followed subject fills.

extreme close-up · close-up · medium close-up · medium · full · wide · extreme wide

Beside the size, a kind when it applies: **two shot** and **over shoulder**
are seen in the plan (two people in frame; someone near the camera at the
frame's edge); **insert** and **pov** are declared (`framing: insert`).
A shot may declare its size (`size: close-up`, or `cu`, `mcu`, `ws`...);
the checks report a size not on the scale (`shot_size_unknown`) and one more
than a step from what the camera frames (`shot_size_mismatch`). `toast board
sheet` labels each board `3 · MEDIUM CLOSE-UP · PUSH IN`: number, kind or
size, and the catalog move.

## How it relates to the other levels

blocking frame (2D, computed, instant) → **3D board** (rendered, with depth)
→ master picture (generated, with the cast) → video. Like the blocking
frame, boards are derived: redrawn on request, never the record.

The same direction as ScreenWeaver's: clay 3D boards first (a grid of
labelled shots: wide, close-up, insert...), the generated film after them.
Where Cine Toaster adds something is the plan under the boards -- the 180°
line, marks and continuity are checked before anything is drawn. Where
ScreenWeaver is ahead is the 3D itself: detailed characters, creatures and
sets, where these boards have mannequins and boxes.
