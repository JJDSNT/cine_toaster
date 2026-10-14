# Trials: what Cine Toaster could do, and when

A diary of the pieces made to judge Cine Toaster as a tool, newest first. Each
entry says what was made, what the tool did and what was done by hand, and
what the person who watched it said. The pieces are not in the repository:
their footage is fetched, and the files live with their productions. The
work records named here hold the detail.

| Date | Piece | Length | File | Published |
|---|---|---|---|---|
| 2026-10-14 | Heat v4, the warp wipe (a ball) | 42 s | `trials/organic-trial-v4.mp4` | not yet |
| 2026-10-14 | Heat v3, a displace wipe | 42 s | `trials/organic-trial-v3.mp4` | not yet |
| 2026-10-14 | Heat v2, joins through mattes | 42 s | `trials/organic-trial-v2.mp4` | not yet |
| 2026-10-14 | Matte prototype | 9 s | `trials/matte-prototype-v1.mp4` | not yet |
| 2026-10-14 | Heat, organic trial | 42 s | `trials/organic-trial-v1.mp4` | [YouTube](https://youtu.be/rI94S8FVFfQ) |
| 2026-10-14 | Orbit, music piece v2 | 41 s | `trials/music-piece-v2.mp4` | [YouTube](https://youtu.be/xm74luJSxqw) |
| 2026-10-13 | Footage trial | 19 s | `trials/footage-trial-v1.mp4` | [YouTube](https://youtu.be/4qRcbSUQfV4) |
| 2026-10-13 | The old reel's cards | 26 s | `trials/reel-cards-v1.mp4` | no |

`trials/` is `~/cine-toaster-references/trials/` on the machine they were made
on. A link is added when a piece is published.

## 2026-10-14 · Heat v4: the warp wipe

The same join, now a warp wipe as the user meant it: the launch, still
playing, wraps itself onto a ball -- the video applied to the effect's mesh --
spins, and flies off to the top right, uncovering the engine on its stand.
It is a recipe (`warp-ball`) of a new primitive, `warp.surface` (the picture
on a plane, ball, tube or page), drawn by the NumPy reference with a depth
buffer. Every part made by the tool. Slow: the scene took ten minutes, most of
it rasterising the mesh at twice the size; the GL renderer is where meshes
belong.

## 2026-10-14 · Heat v3: a displace wipe (not the warp wipe)

The join from the launch plume into the engine test stand: the outgoing
picture bends along a map while the incoming one opens from the centre, both
playing. It was made as the warp wipe the user asked for, and it is not one:
the user corrected it -- a warp wipe maps the playing picture onto a 3D
object, as the Toaster's warps did (the tape, 12:09-12:22). It is kept under
its right name, displace wipe. It is not a shader: it is a
recipe of compositing primitives (ADR 0022) -- a luma signal, a displacement,
a matte from a signal, a threshold, a merge -- drawn by the NumPy reference.
Every part made by the tool. Slow: the scene took six minutes; a fast
renderer of the same graph is next.

## 2026-10-14 · Heat v2: joins shaped by a picture

The organic trial assembled again by the tool, now able to take a matte
(SPEC-0011, CT-0069). The join into the engine's vapour goes through a splash
of water: the moving matte is the shape, and both pictures keep playing
through it. The join into the Sun goes through `luma`: the Sun opens from its
centre outward over the test stand.

- Tool: the whole join, matte included. By hand: the splash itself, rendered
  from the VFX catalog and cropped into a matte file of the production.
- The version said what it did: the matte was retimed to the join, did not
  start black (the falling drop already carries the next picture) and was
  completed to white.

## 2026-10-14 · Orbit in its declared frame (music piece v4)

The production now says its frame, `1920x1080@29.97` (CT-0068); v4 is made
in it whatever its takes are, and comes out as v3 did, 41.441 s.

## 2026-10-14 · Orbit, lengths in beats (music piece v3)

The music piece's first scene rewritten with every shot's length in beats of
its track, read from the beats `toast sound beats` heard and kept (CT-0067).
The cut came out identical to v2 to the millisecond (41.441 s): what had been
worked out by a script outside the tool is now written in the breakdown.

## 2026-10-14 · Matte prototype

The VFX catalog's `liquid-splash` (a Blender fluid simulation) rendered on its
own and used as the matte of a join between two playing clips: a drop
carrying the next picture falls, splashes and floods the frame.

- Tool: the effect, rendered by the catalog's own code.
- By hand: the join, composited with FFmpeg. Cine Toaster cannot yet take a
  matte in a transition (roadmap D3).
- Asked for by the user: could the effects catalog, fire for instance, drive a
  transition.

## 2026-10-14 · Heat, organic trial

Six stretches of NASA footage that move hard -- a solar flare, vapour off an
RS-25 engine, a launch plume slowed, exhaust across a test stand, a night
launch -- joined by transitions of almost three seconds whose shape is
procedural noise (`perlin`, `luminance-melt`, `water-drop`, `swirl`), on the
same track.

- Tool: everything -- footage declared and fetched, music, transitions,
  assembly. Shot lengths were computed from the beats by a script.
- Answering the user's note on v2: "what I missed was video with more movement
  inside an organic transition".
- Seen: both pictures play through each join. `undulating-burn-out` gave a
  jagged star, not anything organic.

## 2026-10-14 · Orbit, music piece v2

Thirteen stretches of four NASA 4K originals (the Earth from the ISS, the
Artemis I and II launches, Perseverance's descent) cut to "Circuit Synthwave"
by Doctor_Dreamchip (CC0, 123 BPM): four straight cuts in a burst and eight
catalog transitions, every join on a beat; a title, a credit, three effects.

- Tool: footage declared and fetched at 1080 lines (CT-0066), the track from
  Openverse, the assembly. By hand: the beats, heard by librosa in a script,
  and the shot lengths worked out from them.
- v1 was 0.24 s long: a transition after a one-second shot was shortened by
  the cut and moved every later join off the beat. v2 makes it one beat.
- The user: liked the montage; missed movement inside the transitions.

## 2026-10-13 · Footage trial

Three NASA clips brought in with `toast take add` and joined by `cube`,
`inverted-page-curl` and `doorway`, with a lower third and `old-film`. The
first time a shader transition was seen over moving footage in a Cine Toaster
version.

- The user: "a little better" than the cards. Its sources were 720p and 360p.
  Its lower third read "FOUR INPUTS", a limit of 1991 hardware the user did
  not want carried over.

## 2026-10-13 · The old reel's cards

The previous Amiga Demo Reel moved onto the assembly path unchanged in
content: seven text cards, five transitions, one line of narration.

- The user: "péssimo" -- nothing of it is to be kept. It is a placeholder in
  `examples/amiga-demo-reel` until the reel is written again (roadmap D9).
