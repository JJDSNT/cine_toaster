---
id: CT-0048
title: Sound effects, music, and a catalog of emotional expression (later)
type: work
status: review
owner: unassigned
created_at: 2026-09-30
updated_at: 2026-10-03
tags:
  - sound
  - music
  - emotion
  - acting
  - catalog
  - future
---

# What

Noted at the user's request (2026-09-30), to take up later.

## 1. Sound effects and music

- **Sound effects**: SINGULAR already mixes its own (`som_montagem`, the
  `EFEITOS` table of its cena scripts: ambiences and effects generated with
  FFmpeg sources, placed at a time). Cine Toaster should have a sound
  catalog like transitions and titles: ambiences, hard effects, Foley, each
  with a source (a file the production brings, a generated one, or a
  library pack with its licence), placed on a shot at a time, levelled with
  the scene's loudness (the assembly already sets speech to −20 LUFS and
  other sound to `level_db`).
- **Music**: cues on the cut (start, end, fades, ducking under speech), from
  files the production brings or generated; the version records which cue.
- Start from what SINGULAR does, so its practice becomes the product's
  (CT-0039 did the same for trims and loudness).

## 2. A catalog of emotional expression

A catalog in three parts, the user's framing: how to **describe** a
feeling, how to **ask** a video model to act it, and how to **express** it
in a 3D character. The user's references, in order of usefulness:

| Priority | Reference | What the catalog would take from it |
|---|---|---|
| 1 | Viddo — Micro-Expression Prompts | Prompt templates, intensity of the expression, how the emotion evolves over time. The closest to AI video generation. |
| 2 | The Emotion Thesaurus (Ackerman & Puglisi) | A wide vocabulary of feelings, gestures, behaviours and acting cues to describe each entry. |
| 3 | FACS / EM-FACS for Unity | Expressions as executable combinations of blendshapes (action units): facial animation beside the prompts. |
| 4 | BEAT — PantoMatrix | Gesture and body-expression data tied to speech and emotion. |
| 5 | HeadBox — Microsoft Research | Tools to prepare facial controls and transfer blendshapes between avatars. |
| 6 | ShotDeck | Cinematic references of acting, framing, lighting and composition to illustrate entries. |

The first two are descriptive content; Unity (FACS) and HeadBox are
animation mechanisms; BEAT is motion data; ShotDeck is cinematic reference.

Recommended start (the user's): Viddo + Emotion Thesaurus + FACS/Unity —
together the three parts of an entry: the feeling described, the acting
asked of the model, the expression as action units on a 3D face.

## Shape of an entry (proposal)

Like the other catalogs (`emotion_assets/<id>/emotion.toml`, layered):
the feeling and its family; physical signals (face, body, voice) in our
own words; intensity levels (subtle, clear, overwhelming) and how it
builds or fades over a shot; the prompt wording for a video model at each
intensity; the FACS action units (AU numbers and weights) for a rigged
face; references (links only). A shot would name one — `emotion: {id,
intensity, arc}` — and the generation prompt and the brief would use it,
as camera moves already reach the model in words (CT-0027). The existing
voice direction (CT-0040: state and delivery) is the audio half of the
same idea.

## Constraints

- **Licensing first**: the user has not checked whether texts, code or
  assets of these references may be incorporated. The Emotion Thesaurus is
  a copyrighted book; ShotDeck is a paid library; code licences of the
  FACS/HeadBox/BEAT repositories must be read. Entries are written in our
  own words, citing references by link; FACS action-unit numbers are a
  public coding system and may be used.
- Creative decisions stay the director's: the catalog offers vocabulary
  and mechanisms, it does not decide how a character feels.

# Done: sound effects and music (2026-10-03)

From SINGULAR's practice (read-only: `ferramentas/cena.py` `AMBIENTES`,
`EFEITOS`; `cena_ltx.py` layers and `ambiente_ate`; `ferramentas/sons.py`
and `singular/sons/MANIFESTO.csv`). Guide: `docs/sound.md`.

- `sounds.py`: a layered catalog (`sound_assets/<id>/sound.toml`, built in,
  `CINE_TOASTER_SOUNDS_PATH`, the production's `sounds/`) of ambience,
  effect, Foley and music; a source is an FFmpeg graph (`{d}` its length)
  or a file with provenance, licence, credit, page and status. 26 built-in
  items, generated, ours: SINGULAR's ambiences and effects in English plus
  wind, rain, heartbeat, whoosh, impact, glitch, buzz, thunder, footsteps,
  and three music beds.
- Placing: shot `sounds` (at seconds into the shot as cut), scene
  `ambience` and `music` (`from`/`at`/`to`/`until`/`duration`). Defaults per
  category (ambience -34 LUFS looped; effect -24; Foley -28; music -24,
  ducked 10 dB). `sound_problem` (error) for unknown ids/keys/times;
  `sound_provisional` (advice) for a provisional recording. `sounds` is a
  core shot field.
- The cut: `plan_scene` places cues on the timeline (`plan.cues`, notes for
  what cannot be heard); `render` joins, then `sounds.mix` renders each cue,
  measures it (EBU R128, short sounds padded to the meter window), sets its
  gain, delays it into place, ducks music under the cut's speech spans with
  0.3 s ramps (a volume expression, deterministic -- not a sidechain keyed
  on the take's own ambience), sums with a limiter. The job summary keeps
  `sound` (id, kind, start, length, level, gain, licence, credit) and the
  version's summary says "Sound laid: …".
- Sources (`sound_sources.py`), the user's request (2026-10-03): SINGULAR's
  two -- Freesound (CC0 only, HQ preview, `preview-hq`) and Sonniss GDC
  (archive.org mirror, md5-checked, `provisional`) -- and, for music,
  Openverse (Jamendo, ccMixter, Wikimedia...; CC0/PDM/CC BY only, the
  credit kept). `toast sound search|fetch`. `toast sound import` registers a
  library on disk by its `manifest.csv` (or SINGULAR's column names) in
  place: SINGULAR's 53 sounds, nothing in SINGULAR written. Category guessed
  from the file and its use; the author corrects it.
- Interfaces: `toast sound list|preview`, `/api/sounds`, `/api/sound-preview`
  (cached WAV in the state dir), the control room's Sound room (listen,
  licence, status, provisional warning), MCP `list_sounds`, doctor "Sound
  sources" (the Freesound key).

Validation:

- every built-in item rendered and measured at its level (after fixing
  `bandpass`, whose `w` is a Q unless `width_type=h`);
- `tests/test_sounds.py`: catalog, expansion and problems, placement on
  the timeline, the duck (music >7 dB down under a line), an effect landing
  at its time, an assembly job laying ambience, music and a shot sound and
  the version saying so, findings, a library import with SINGULAR's
  columns;
- on a scratch demo copy: one real fetch from each source (Freesound
  700702, a Sonniss UI sound, an Openverse Jamendo track), SINGULAR's
  library imported (16 ambience, 32 effect, 5 music), the Sound room
  checked headless (82 items, a preview played, no page errors).

Remains:

- generated sound from a model (Stable Audio Open; MMAudio from the
  picture) as a provider under the ledger;
- J/L split edits carrying sound across a cut; stems for a final mix;
- an imported library's category is guessed from the file name and its
  use (SINGULAR: 16 ambience, 32 effect, 5 music); some are wrong and are
  corrected by hand in each `sound.toml` until a review step exists;
- Freesound items are the HQ preview MP3, not the original; Sonniss items
  come from an unofficial mirror -- both must be replaced before release
  (the status says which);
- the emotion catalog (section 2).

# Done: the emotion catalog (2026-10-03)

The three parts of an entry, as the user framed them -- describe, ask,
express -- in `emotions.py` and `emotion_assets/<id>/emotion.toml`
(layered: built in, `CINE_TOASTER_EMOTIONS_PATH`, the production's
`emotions/`). Guide: `docs/emotions.md`.

- 25 built-in entries in nine families (joy, sadness, fear, anger,
  surprise, disgust, connection, self, thought), including what SINGULAR
  needs now: recognition, shock, tenderness, dread, numbness, grief.
- **Describe**: face, body and voice signals, in our own words.
- **Ask**: what a video model sees at subtle, clear and overwhelming --
  behaviour, not a label (the principle behind micro-expression prompting);
  `arc` holds, builds (subtle → the intensity), fades, breaks (sudden).
- **Express**: FACS action units with weights (EMFACS prototypes for the
  basic six, composed for the rest) scaled by intensity, mapped to the 52
  ARKit blendshapes (`emotions.face`, `toast emotion face`) so a Unity,
  Blender or Unreal (Live Link) rig can wear it; head and gaze units kept
  apart.
- A shot names `emotion: {id, who, intensity, arc, reason}` (or several);
  checked (`emotion_problem`: unknown id, key, intensity, arc, or a `who`
  outside the scene's cast, subjects and speakers). The generation prompt
  gets a sentence per person ("The woman at the console: at first only …,
  growing until …"); a line without its own delivery takes the feeling's
  voice at that intensity; the brief gets an `ACTING` slot.
- `toast emotion list|show|face`, `/api/emotions`, the Emotions room,
  MCP `list_emotions`.

Licensing, as recorded above: nothing is copied from the Emotion
Thesaurus, Viddo, ShotDeck or the FACS/HeadBox/BEAT repositories; FACS
numbers are a public coding system; the ARKit names are Apple's public
API. References may be added to an entry by link (`references`).

Validation: `tests/test_emotions.py` (every entry complete; arcs; the
face scaled and mapped; placements checked; the prompt and the brief), the
MCP tool, the room checked headless (25 cards, no page errors).

Remains: driving a 3D board's face (the mannequins have none yet: a rigged
proxy, CT-0049); BEAT-style gesture data for the body; a check that a line's
delivery and its emotion do not contradict; style catalog entries choosing
intensities (CT-0049).

# Noted for later: surround and spatial sound -- research first (2026-10-03)

The user's request: surround/spatial sound as a future feature (their
home theatre is 5.1), with a reference they were unsure was relevant, and
the instruction to research it in depth before implementing anything.

The reference: github.com/danieldotwav/Spatial-Audio-Renderer -- a small
real-time renderer for games (C++, OpenAL: 3D sources, EFX reverb, a
"beamforming" simulation; Dolby Atmos and HRTF only listed as future).
Useful as a concept, not as a dependency: it has **no licence** (so
nothing may be incorporated), it is real-time where a film is mixed
offline, and it is small and inactive (4 stars, last push 2024-10).

What Cine Toaster already has toward it: every sound placed on a timeline
(takes, catalog cues, ambience, music), speech spans, and -- unusually --
the plan's geometry: where each subject and the camera stand in every
shot, so a voice or an effect could be panned to where it is on screen
(or behind the camera) rather than by hand.

Questions the research must answer before an implementation:

1. **Deliverable**: 5.1 (and 7.1) channel-based mixes first? Encoded how
   (AAC 5.1, AC-3/E-AC-3 for home theatre, FLAC/WAV stems), and played by
   what the user owns (a 5.1 receiver over HDMI from which player)?
2. **Mixing conventions**: dialogue in the centre, music and ambience in
   L/R and surrounds, LFE for low effects, downmix to stereo checked;
   loudness for 5.1 (EBU R128 / ATSC A/85 with the LFE excluded).
3. **Panning from the plan**: map a subject's screen side and depth (the
   blocking frame) to a pan position per shot; how far to follow movement;
   off-screen sound to the surrounds; the cut's J/L handles.
4. **Object-based and scene-based audio**: Dolby Atmos (ADM BWF; the
   renderer is proprietary and licensed), MPEG-H, ambisonics (first or
   higher order; IAMF/Eclipsa from AOM, open), and binaural/HRTF for
   headphones (SOFA files; FFmpeg's `sofalizer`). Which are open enough to
   adopt (ADR 0011: external programs on files, permissive licences)?
5. **Tools to evaluate**: FFmpeg channel layouts and `pan`/`amerge`/
   `surround`/`sofalizer`; libspatialaudio, Spatial Audio Framework
   (SAF), Google Resonance Audio, OpenAL Soft (LGPL, as an external
   program), Blender's audio (speakers in a scene, 5.1 mixdown) given the
   USD stage already exists; their licences.
6. **Sources**: the catalog's recordings are mostly mono or stereo;
   ambisonic ambience libraries and their licences; whether generated
   sound can be produced spatially.
7. **Monitoring**: how the user checks a 5.1 mix at home and in the
   control room (a stereo or binaural preview of it).

Status: noted, not started. No implementation until this research is
written up and the user has chosen the deliverables.
