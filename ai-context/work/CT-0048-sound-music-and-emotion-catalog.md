---
id: CT-0048
title: Sound effects, music, and a catalog of emotional expression (later)
type: work
status: proposed
owner: unassigned
created_at: 2026-09-30
updated_at: 2026-09-30
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
