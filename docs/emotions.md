# Emotions

How a person in a shot feels, from a catalog (CT-0048). An entry has three
parts:

- **describe** -- what shows on the face, in the body, in the voice;
- **ask** -- the words a video model gets, at three intensities: what can
  be seen, never a label ("the jaw tightens and the eyes hold", not
  "angry");
- **express** -- FACS action units, and from them ARKit blendshape weights,
  so the expression can drive a rigged face (Unity, Blender, Unreal through
  Live Link).

## In a shot

```yaml
shots:
  - n: 3
    emotion: {id: dread, who: MARA, intensity: clear, arc: builds, reason: The reply is her own voice.}
```

- `intensity`: subtle, clear (default), overwhelming.
- `arc`: holds (default), builds (from subtle to the intensity), fades,
  breaks (arrives suddenly).
- A list gives several people their feelings.

The prompt gets one sentence per person, after the action; a line that
person speaks without its own `delivery` is spoken with the feeling's voice
at that intensity. The brief shows an `ACTING` slot. Unknown ids, keys,
intensities, arcs or people are errors (`emotion_problem`).

The catalog offers vocabulary; how a character feels stays the director's.

## The catalog

`toast emotion list <project>`, `toast emotion show <project> dread`, the
control room's **Emotions** room, MCP `list_emotions`. 25 built-in entries
in nine families: joy, contentment, relief; sadness, grief, longing,
loneliness; fear, dread, unease; shock, surprise, recognition; anger,
contempt; disgust; tenderness, compassion; shame, guilt, determination;
confusion, numbness, awe, hope.

An entry (`emotion_assets/<id>/emotion.toml`; a production adds or
replaces entries in `emotions/`, or a shared path in
`CINE_TOASTER_EMOTIONS_PATH`):

```toml
id = "dread"
family = "fear"
says = "Fear of what is coming, slowly understood."
near = ["fear", "unease"]

[signals]
face = ["a fixed stare", "the jaw held", "a slow swallow"]
body = ["stillness", "shallow breathing"]
voice = ["low, careful, held"]

[ask]
subtle = "a stillness, the eyes fixed, a slow swallow"
clear = "the face goes still and pale, the eyes fixed on the source, the breath shallow"
overwhelming = "frozen, the eyes wide and unblinking, the lips pressed white, trembling"

[voice]
clear = "held, almost a whisper"

[facs]          # action unit = weight at full intensity
1 = 0.5
4 = 0.5
5 = 0.5
```

## A face for a rig

```bash
toast emotion face <project> grief --intensity overwhelming
```

prints the action units (scaled: subtle 0.35, clear 0.7, overwhelming 1.0)
and the ARKit blendshape weights they make (AU12 → mouthSmileLeft/Right,
AU1 → browInnerUp, ...); head and gaze units are listed apart.

## Sources and licences

The entries are written in our own words. The references that shaped the
idea -- micro-expression prompting for video models, the Emotion
Thesaurus, FACS/EM-FACS, BEAT, HeadBox, ShotDeck -- are not copied; an
entry may cite them by link in `references`. FACS action-unit numbers are a
public coding system; the blendshape names are Apple's public ARKit API.
