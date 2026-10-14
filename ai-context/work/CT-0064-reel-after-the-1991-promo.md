---
id: CT-0064
title: The Amiga reel after the 1991 Video Toaster promo -- the capabilities it needs
type: work
status: ready
owner: unassigned
created_at: 2026-10-13
updated_at: 2026-10-13
tags:
  - demos
  - assembly
  - transitions
  - compositing
  - plan
---

# What

Rebuild the Amiga Demo Reel (Demo 2 in `docs/production-validation.md`) on the
structure of NewTek's 1991 promotional tape, and build the capabilities that
asks for. This record holds the reference, the gap between what the tape does
and what Cine Toaster renders today, and the order to close it. Nothing is
built or produced yet.

# Why

The user asked for it (2026-10-13). The reel today is four scenes of text
cards, about 31 s, rendered by `toast build`: a slideshow. Its two-act
structure (`production-validation.md`: establish what Cine Toaster does, then
show it doing so while producing the demo itself) was decided on 2026-10-04
and never written. The tape gives that structure a model, and it shows what
the Toaster did that the reel cannot: it worked on moving video, with several
sources at once.

# The reference

"NewTek Video Toaster (1991) - Amiga Promo VHS Demo & Showcase",
`https://www.youtube.com/watch?v=XDXv-wq3uDY`, 15 min 17 s. A copy for
observation, its chapter list, contact sheets (one frame every 4 s) and an
automatic transcript are in `~/cine-toaster-references/video-toaster-1991/`,
outside the repository. They are never committed and never used as material:
the rule is CT-0028's, recreate from observation, copy nothing.

Two pieces on one tape:

- **"Revolution" (0:00-10:30).** A narrator and a sceptical second voice
  ("Like what?", "What does that do?", "Hey, I can do that").
  - Opens on black with the claim: every transition, effect, graphic, title
    and animation you are about to see was made entirely with the Toaster.
  - Before and after: a room of expensive equipment against one box on a desk.
  - A tour, one module at a time, each named on a card, named again aloud,
    then seen working: four-input switcher (cuts, dissolves, organic wipes,
    digital video effects), ChromaFX, ToasterPaint, luminance keyer,
    character generator, LightWave 3D.
  - "All in one box"; "not evolution, revolution".
  - Credits as proof: "This video tape was created entirely with the Video
    Toaster's built-in: ..." and the list of modules.
- **"The Revolution Continues" (10:30-15:17).** No narration: short text cards
  cut against footage of each System 2.0 feature, on music.

Mapping: Act I follows "Revolution" (claim, before/after, a two-voice tour of
capabilities, each card entering on its own transition). Act II follows "The
Revolution Continues" (a montage on music of the reel's own records and
renders), closing on credits where every line must be true of this reel.

# The gap

Read from the code on 2026-10-13, then probed by running (see Done).

**There are two render paths, and the reel is on the poor one.**

- `toast build` (`build.py`) renders only `source: composed` shots, each as a
  PNG card (`draw_card`: headline, subhead, body) looped for its duration. A
  transition there only ever joins two still frames. Its audio is the first
  spoken line found on disk (`_production_audio`); no placement, no music.
  It ignores `title:`, `effects:`, `sounds:`, ambience and music.
- `toast assemble` and `assemble-sequence` (`assembly.py`, CT-0038/0050/0051)
  cut takes, which are video: transitions already run frame by frame over
  moving pictures there. They also render catalog title cards (`title:`),
  solid black or white, voice-over lines, effects, the sound catalog, music
  ducked under speech, formats and stems. A composed shot with `text:` and no
  catalog title is skipped with a note.

So most of what the reel lacks exists, on the path it does not use.

| Capability the tape shows | Today | Gap |
|---|---|---|
| Cards and video in one cut | works in the assembly when the card is a catalog title (probed) | the reel's own `text:` cards are skipped; a scene made only of them is refused |
| A recording as a shot's picture | works: a file dropped in `work/cNN.mp4` is cut, titled and joined by transitions (probed) | no command brings it in; nothing records where it came from or its licence |
| A still as a shot's picture | `toast shots` lists a `.png` take as ready and `toast check` is silent | the assembly refuses the scene: "The cut leaves nothing of the take (0.00-0.00 s of 0.00 s)" (probed) |
| Several voices placed in time, music under them | lines on a card are heard and music is laid, when the files are in the scene's folder (probed) | three defects in `toast voice`, below |
| Organic wipes: an animated matte drives the change, often with a graphic over it | no renderer gives a shader a third input; `luma` and `displacement` are left out of the catalog for that reason | a matte input (still and moving) and an overlay with alpha in the transition contract (`docs/transition-library.md` foresees both) |
| Positional effects, as an ADO did them: the picture squeezed, flipped, tumbled, flown, **still playing** while it moves | inside a join, yes: both pictures keep playing through a shader transition in the assembly (measured 2026-10-14, below); 6 of 117 gl-transitions shaders are reviewed | review or write the shaders (CT-0028). Outside a join, no: a picture cannot be shrunk into a box and held there while another plays behind it, or flown on keyframes within a shot -- that is a move on a layer, not a transition (see layers) |
| Luminance keyer: a person over a graphic or over other video | `colorkey` only for VFX stock elements on green | a shot made of two pictures in layers, keyed by luminance or colour |
| Character generator | cards, lower third, roll, typewriter, 3D letters (CT-0031) | a horizontal crawl; drop shadow (neither found in `titles.py`) |
| ChromaFX colour effects | procedural VFX and LUT looks | catalog items: posterise, solarise, colour cycling |
| LightWave: a shot made from data in 3D or animation | `rig`, `remotion`, `hyperframes` are accepted composed engines; `build` draws them all as a text card | a renderer for each, or remove them from the vocabulary -- declared and called by nothing |
| A montage cut on the beat | no musical time in the project | Demo 4's subject; durations by hand are enough for the reel |

`toast voice`, found by the probe:

- it writes `mix.file` under the production root, and the assembly reads it
  under the scene's folder, so a spoken line is "not there; it is not heard"
  (CT-0063 left this open);
- it speaks every line in one voice (`--voice` or the default): a line's own
  `voice:` is ignored, so a second speaker sounds like the first;
- a line whose text changed keeps its old audio ("keep ... exists"), with
  nothing saying the recording no longer matches the words.

**The video keeps playing inside the transition** (the user named this as
the Toaster's strength, 2026-10-14: what an Ampex ADO did). Measured: two
clips whose brightness says what time it is, joined by a 2 s `wipe-left`
shader in `assembly.render`. On the outgoing side the picture went from 139
to 167 between 2.1 s and 2.5 s of the cut, as its own clock predicts (134,
159); on the incoming side it fell from 252 to 208 between 2.3 s and 2.9 s.
Neither side is frozen. `toast build` is the exception: its shots are stills.

**Not known, and not to be assumed** (the user, 2026-10-14). The Toaster's
limits are not Cine Toaster's: four inputs was what 1991 hardware allowed, and
nothing here should be named or sized after it. An earlier draft of this
record ruled out live switching on the grounds that "Cine Toaster is not a
live system"; that was an assumption, and it is withdrawn. What Cine Toaster
can do with video and with streams has not been measured:

- how many pictures can be composed at once, and at what size and rate;
- whether a transition or an effect runs in real time (today a shader join is
  rendered frame by frame through pipes to FFmpeg, offline);
- whether a stream (a camera, RTSP, HLS, NDI, a screen) can be a source at
  all, and with what delay;
- whether anything can be switched while it plays.

ToasterPaint has no counterpart planned: `toast picture` edits a picture
another way.

# Done

- **The probe (2026-10-13)**, on a copy of the reel in a scratch directory,
  never in the checkout, with synthetic test pictures.
  - Unchanged, the reel assembles to 2 s of black: SC-010 keeps its solid
    shot and drops its card; SC-020, SC-030 and SC-040 are refused
    ("no shot with a take to assemble") and left out of the sequence.
  - With SC-010's card as a catalog title (`title: {id: card}`) and SC-020
    as three takes: the card is drawn, a lower third is drawn over moving
    video, `diamond-wipe` and `clock-wipe` run over moving video inside the
    scene, and the production's own `amiga-copper-bars` shader runs at the
    join between the two scenes (`enter`). Lengths agree with the overlaps
    (8.17 s, 9.17 s, 16.63 s for the sequence). Music is laid.
  - What it found is in the table and the `toast voice` list above.
  - Not probed: `effects:` on a take was accepted but not judged by eye;
    whether a title card takes the look's palette; stems of a card scene.

# The music piece, first version (2026-10-14)

Made so the user can judge what Cine Toaster does today; steps 3 and 4 of the
order below, done by hand where the tool has nothing yet.

- A production outside the repository, `~/cine-toaster-demos/music-piece`:
  one scene, thirteen shots, 41.4 s at 1920x1080.
- Footage: stretches of four NASA originals (Earth from the ISS in 4K, the
  Artemis I and II launches, Perseverance's descent), declared with
  `footage:` and fetched (CT-0066).
- Music: "Circuit Synthwave" by Doctor_Dreamchip, CC0, fetched with `toast
  sound fetch openverse` into the production's `sounds/`, laid as the scene's
  `music`.
- Joins: four straight cuts in a burst and eight catalog transitions
  (`cross-zoom`, `cube`, `swap`, `ripple`, `pixelate`, `inverted-page-curl`,
  `film-burn`, `dreamy-zoom`), each with its reason; two titles; `light-leak`,
  `glitch` and `fade-to-black`.
- Every cut and the middle of every transition was placed on a beat by
  computing the shot lengths from the track's beats (123 BPM).
- Kept for the user: `~/cine-toaster-references/trials/music-piece-v2.mp4`.

What making it showed is missing:

- **Beats are not in the tool.** They were detected with librosa in a scratch
  script, and the shot lengths written from them by another. Nothing in the
  project holds the beats, and nothing checks a cut against them.
- **A production cannot say its frame.** A version takes the size and rate of
  its first moving take; footage had to be fetched at 1080 lines to get a
  1080-line piece.
- **`toast sound search openverse` finds nothing for "synthwave"** with its
  music filter; the same query to Openverse without it returns 175 items.
- A transition is shortened to half the shorter shot it joins (said in a
  note). After a one-second shot that moved every later join off the beat;
  the first version was 0.24 s long until the transition was made one beat.
- The piece was checked by eye on sampled frames and by its length (41.44 s
  against 41.42 computed). Nobody has listened to it: whether the joins are
  felt on the beat is for the user to say.

# Where the line stands (2026-10-14)

One list of everything this line has found, so nothing lives only in a
conversation. The sections below hold the detail.

Done:

- the reel assembled like a film; a still as a take; `toast voice` beside the
  scene, in each line's voice, respeaking a changed line (CT-0065);
- `toast take add`: material brought in with source, licence, credit (CT-0065);
- `footage:` declared on a shot and fetched, at a chosen height (CT-0066);
- `toast sound search openverse` finds music Openverse does not categorise
  (Freesound's): it returned nothing for "synthwave", now five tracks;
- a first music piece and an organic trial, made by hand where noted below.

The point-by-point plan, with what each point is done by, is in
`development/roadmap.md` ("The demos line", D1-D9); the list below is its
summary.

To do, in the agreed order:

1. **Beats as a record**: detect a track's beats (librosa is in
   `.venv-voice`), keep them with the sound, and let a shot's length and a
   join's place be given in beats; a check for a join that is off the beat.
2. **A production's frame**: its size and rate declared once, instead of
   inherited from the first moving take.
3. **A matte and an overlay in the transition contract** (moved up: the user
   asked for organic transitions): a join shaped by a moving matte, a
   graphic riding it; `luma` and `displacement` back in the catalog.
   The matte may be an effect of the VFX catalog (fog, fire, smoke, liquid)
   rendered for the join: the user's idea, 2026-10-14.
4. **Layers and ADO-style moves**: a playing picture sized, placed, rotated
   in perspective on keyframes over another, held; borders, drop shadow,
   trails; a keyer (luminance, colour) with its key travelling with it.
5. **Measure video and streams**: sources at once, real time, a stream as a
   source, switching while playing.
6. **Toaster-style shaders** (CT-0028), and a review of the catalog's
   positional and organic shaders: 6 of 117 have a sheet, and
   `undulating-burn-out` is not what its name suggests.
7. **The music piece, finished**, then **the reel** written from scratch: a
   narrated first act, the piece as its second. The fixture in
   `examples/amiga-demo-reel` is a placeholder until then.

Smaller defects found on the way, not yet fixed:

- a transition shortened to half its shorter shot moves later joins off the
  beat; it is said in a note, nothing more;
- a first shot's `transition` that nothing renders is not reported by
  `toast check` (a scene's first join is its `enter`);
- a title does not take its colours from the production's look;
- `toast footage fetch` runs in the foreground: no progress, no cancel; a
  changed declaration does not replace the take that is there;
- `toast build` duplicates a poorer form of the assembly: keep or remove;
- `rig`, `remotion` and `hyperframes` are accepted engines nothing renders;
- title catalog: no horizontal crawl, no drop shadow; VFX catalog: no
  posterise, solarise or colour cycling;
- the piece's Mars shots are a small square in a black frame: choose others.

# What the user said of the first piece (2026-10-14)

He liked the montage. What he missed: **video with more movement inside an
organic transition**. The first piece joined slow pictures (the Earth
drifting) in one second, so nothing was seen to move inside a join.

A second scene, `SC-020 Heat`, in the same production answers with what
exists: pictures that move hard (a solar flare, vapour off an RS-25 engine, a
launch plume slowed, exhaust across a test stand) joined by 2.9 s transitions
whose shape is procedural noise (`perlin`, `luminance-melt`, `water-drop`,
`swirl`; `undulating-burn-out` turned out a jagged star, not organic). Kept at
`~/cine-toaster-references/trials/organic-trial-v1.mp4`.

What it cannot do yet, and the Toaster and an ADO could:

- **A join shaped by a moving matte** -- smoke, ink, liquid, fire, an
  animated object -- rather than by a formula. This is the matte input of
  step 6; the procedural shaders above are the nearest thing without it.
- **A graphic riding the join** (the Toaster's sheep and falling objects): the
  overlay with alpha, same step.
- **A picture flown while it plays, outside a join**: sized, placed, rotated
  in perspective on keyframes over another picture, held, then released. An
  ADO's whole purpose; here it needs layers (step 7).
- **Borders, drop shadows and trails on the flown picture.**
- **In real time.** Unmeasured (step 5).

The ADO list is from memory of the machine, not from its manual: a search
found no operator's guide for the ADO 1000 online.

# Order agreed (2026-10-14)

The music-driven piece (Demo 4 in `docs/production-validation.md`) comes
first, and the reel comes out of it: it is the tape's second piece, it uses
what already works best (pictures playing through transitions), and it needs
no script, narration or layers. The reel is then a short narrated first act
and the music piece, grown, as its second.

1. Close CT-0065.
2. Footage declared and fetched: a shot says which stretch of which public
   file it is; a command downloads and cuts it.
3. Music and beat: an open-licence track brought in with its licence, its
   beats detected and kept as a record of the project.
4. The music piece, first version (30-45 s): footage at 1080p or more,
   catalog transitions and effects on the beat. The user judges it.
5. Measure video and streams (the four questions under "Not known").
6. A matte and an overlay in the transition contract; then CT-0028.
7. Layers, the keyer and ADO-style moves within a shot.
8. The reel: act I narrated, act II the music piece with 6 and 7.
9. Catalog items; the composed engines nothing renders.

Live transmission is not what Cine Toaster is for, and nothing prevents
supporting it (the user, 2026-10-14): step 5 measures, it does not commit.

The numbered list below is the earlier order, kept for its detail.

# To do

In order. Each numbered step that changes code gets its own record.

0. ~~Probe~~ done 2026-10-13; see Done.
1. **One path for the reel.** In progress as `CT-0065`.
   - The reel's cards in the assembly (decide: teach the assembly `text:`
     cards, or express them as catalog titles and drop `text:` from the reel).
   - `toast voice`: `mix.file` in the scene's folder (per CT-0063), each
     line in its own voice, and a line whose words changed reported or
     remade.
   - A still as a take: held for the shot's duration, or refused by
     `check` and `shots` with a reason, never at the assembly.
   - A command that brings a recording or a still in as a `captured` or
     `archival` take with its source, licence and credit.
   - `toast build` becomes the whole-production form of the assembly, or is
     retired; `make build` follows. Decide after the probe.
   - Correct what is stale: the reel's README (says there is no TTS),
     `project.yaml`'s logline, CT-0017's note that the narration is checked in.
2. **Write the reel, first version**, with what step 1 gives: both acts, two
   Piper voices, catalog transitions with reasons, titles, music from the
   sound sources. The script goes to the user scene by scene before
   `examples/amiga-demo-reel` changes. Act II's shots are written to take
   pictures as they become available.
2b. **Measure video and streams** (a spike, its own record): the four
   questions under "Not known" above, answered by running, before any
   of them is designed for or ruled out.
3. **Transition inputs**: a specification for a matte and an overlay in the
   transition contract, then the renderers (shader and FFmpeg stand-in), the
   preview, and `luma`/`displacement` back in the catalog. This unblocks the
   organic wipes of CT-0028.
4. **CT-0028**: the separate repository of Toaster-style shaders, starting
   with the effects the reel's script names.
5. **Layers and the keyer**: a specification first -- a shot with two
   pictures is a Project Core concept (what is over what, and why), not an
   FFmpeg option.
   It includes the ADO-style move: a playing picture placed, sized,
   rotated and flown over another on keyframes, within a shot.
6. **Catalog items**: crawl, drop shadow, posterise, solarise, colour cycling.
7. **Composed engines**: a renderer or removal for `rig`, `remotion`,
   `hyperframes`; `toast doctor` reports whichever is kept.
8. **Second version of the reel**, using 3-7, replacing cards with what they
   describe.

Steps 3-7 do not depend on each other except 4 on 3. Step 2 can start as soon
as 1 is done, so there is a true reel before the Toaster-class work.

# Decisions

- **The tape is a model of structure, not a source.** No NewTek footage,
  sound, artwork, logo or wording. The second piece's music is a commercial
  recording and is not used either.
- **Capabilities before the reel, but a first reel early.** The user asked
  for the capabilities to be listed first (2026-10-13). Step 2 comes after
  only step 1 so the reel is not held back by the long steps.
- **A probe before a plan is trusted.** The first reading of the code said
  no path mixes cards and takes; the assembly already renders catalog title
  cards. The table above is corrected for that, and step 0 exists because it
  may be wrong elsewhere.
- **Nothing of the previous reel is kept** (the user, 2026-10-14). Its cards,
  wording and transition choices predate the catalogs and were judged poor
  when assembled; the reel is written from scratch around footage. CT-0065
  moved the old cards onto the assembly path only so the fixture kept
  working; that content is a placeholder to be replaced whole.
- **Its own line, not SINGULAR's** (the user, 2026-10-13). These are
  capabilities for the demo that become part of Cine Toaster; they are not
  ordered by SINGULAR's milestones.
- **Material for the reel**: open-licence video where footage is needed,
  each with its licence and credit recorded as the sound sources do, and
  sequences and animations Cine Toaster itself produced. Not chosen yet;
  the map of what is missing comes first.
- **The reel stays runnable with no API key**, as CT-0017 decided. Pictures
  that needed paid generation would be checked in as takes with lineage, or
  left out.

# Validation

- No code changed. The first four rows of the table and the `toast voice`
  list are from running the probe; the rest of the table is from reading `build.py`,
  `assembly.py`, `shader_render.py`, `transitions.py`, `takes.py`,
  `vocabulary.py` and the heads of `titles.py`, `vfx.py`, `sounds.py`.
- Not verified by running: drop
  shadow and crawl in the title catalog (searched by name only).
