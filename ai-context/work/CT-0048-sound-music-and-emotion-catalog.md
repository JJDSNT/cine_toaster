---
id: CT-0048
title: Sound effects, music, and a catalog of emotional expression (later)
type: work
status: doing
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
