# Trials: what Cine Toaster could do, and when

A diary of the pieces made to judge Cine Toaster as a tool, newest first. Each
entry says what was made, what the tool did and what was done by hand, and
what the person who watched it said. The pieces are not in the repository:
their footage is fetched, and the files live with their productions. The
work records named here hold the detail.

| Date | Piece | Length | File | Published |
|---|---|---|---|---|
| 2026-10-14 | Matte prototype | 9 s | `trials/matte-prototype-v1.mp4` | not yet |
| 2026-10-14 | Heat, organic trial | 42 s | `trials/organic-trial-v1.mp4` | [YouTube](https://youtu.be/rI94S8FVFfQ) |
| 2026-10-14 | Orbit, music piece v2 | 41 s | `trials/music-piece-v2.mp4` | [YouTube](https://youtu.be/xm74luJSxqw) |
| 2026-10-13 | Footage trial | 19 s | `trials/footage-trial-v1.mp4` | [YouTube](https://youtu.be/4qRcbSUQfV4) |
| 2026-10-13 | The old reel's cards | 26 s | `trials/reel-cards-v1.mp4` | no |

`trials/` is `~/cine-toaster-references/trials/` on the machine they were made
on. A link is added when a piece is published.

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
