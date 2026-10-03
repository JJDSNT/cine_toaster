# Styles

A style is a way of making a film (CT-0049) -- not only a director's
manner. The catalog holds six kinds:

| Kind | Built in |
|---|---|
| movement | classical continuity, neorealist, new wave, vow handheld |
| approach | slow cinema, observational, contemplative science fiction, intimate drama |
| genre | noir, anime cinematic, kinetic action |
| manner | symmetrical tableau, cold precision, romantic melancholy |
| animation | stop-motion, hand-drawn 2D, 3D feature, cut-out, rotoscope, pixel art, painterly, pastoral anime |
| format | viral vertical, commercial spot, music video, trailer, explainer, interview documentary |

## Three axes, combined

Direction, technique and format are independent: a film can be
stop-motion, Wes Anderson-like and a viral vertical at once.

```yaml
style: {technique: stop-motion, direction: Wes Anderson, format: viral-vertical}
```

Each axis cascades on its own (a scene may change one and keep the
others; `{format: none}` removes one). Combined: the format owns shot
lengths, hook, aspect and total length; the technique opens the prompt and
sets the frame rate; the direction sets the performance register; the
strictest intensity ceiling holds; anything an axis avoids is avoided, and
the advice names that axis. Two entries on one axis, or an entry under the
wrong axis, is `style_unknown`.

## Naming one

```yaml
# project.yaml: the production's style
style: contemplative-sci-fi
```

```yaml
# scene.yaml: a scene may name another; the nearest wins
style: anime-cinematic
```

A style may also be named the way people know it -- `style: Ghibli`,
`style: Wes Anderson`, `style: TikTok` -- through its `aka`. The level that
decided is reported, as for looks. An unknown name is an error
(`style_unknown`).

## What it does

- **The video prompt** ends with the style's `prompt`, words of craft
  ("monumental wide-angle composition, tiny human figure ..."): the traits,
  described, which a model follows more reliably than a name. The names
  stay visible to people (`name`, `aka`, `inspired_by`).
- **A derived master picture** is asked to render in the style too, so a
  board, a plate or a photograph is drawn into it; `style: false` on the
  shot's `derive` keeps the source's look.
- **The brief** gets a `STYLE` slot: framing, moves, shot lengths, the
  performance register, the format's rules.
- **Emotions** default to the style's intensity (slow cinema: subtle).
- **Advice** (`style_departure`, never a refusal -- a departure can be the
  point) when a shot uses a move, a cut or a transition the style avoids,
  runs outside its shot lengths, plays an emotion beyond its ceiling, or,
  for formats, when the opening misses the hook or the scene misses the
  format's length.

## An entry

`style_assets/<id>/style.toml`; a production adds or replaces entries in
`styles/`, or a shared path in `CINE_TOASTER_STYLES_PATH`.

```toml
id = "viral-vertical"
kind = "format"
says = "Short, vertical, made to stop a thumb ..."
inspired_by = ["short-form social video"]   # for people only
framing = ["vertical 9:16, the subject centred and close"]
colour = "bright, punchy, phone-native"
sound = "a voice hook in the first second; captions do the work with sound off"
titles = ["caption", "word-by-word"]
prompt = "vertical smartphone video, close and centred subject, ..."

[camera]
prefer = ["handheld", "push-in", "crash-zoom-in"]
avoid = ["aerial-orbit", "time-lapse"]

[editing]
shot_seconds = [0.5, 4]
prefer_cuts = ["jump", "smash", "hard"]
avoid_transitions = ["cross-dissolve", "dip-to-black"]

[performance]
intensity = "clear"        # the emotions' default
max = "overwhelming"       # their ceiling

[format]                   # formats and animation techniques
aspect = "9:16"
total_seconds = [7, 60]
hook_seconds = 2
captions = true
# end_card = true; frame_rate = 12 (animated on twos)
```

Every move, cut, transition and title an entry names must exist in its
catalog (a test checks the built-in ones).

`toast style list|show`, the control room's **Styles** room (the
production's own is marked), MCP `list_styles`.

## A format on the cut

The assembly applies the format axis:

- **aspect** -- every take is reframed to it: a window as tall (or as
  wide) as the take allows, centred unless the shot says where
  (`reframe: {x: 0.3, y: 0.5}`, 0 to 1), scaled so the long side keeps the
  take's resolution. The whole take is reframed, so J/L-cuts keep their
  handles; titles are drawn in the new frame, so no text is cut. The takes
  themselves are not touched;
- **captions** -- the words spoken, in groups of up to four broken at
  pauses, from the word sidecar's words (`{start, end, word}`), else the
  shot's lines spread over its speech, burned in the lower part of the
  frame;
- **end card** -- stays the author's: a format that wants one advises when
  the scene does not end on a title card.

## Several formats at once

```yaml
# project.yaml (or a scene)
deliver: [TikTok, {name: square, aspect: "1:1"}]
```

Every version is then also delivered in each format named -- the same
takes, joins and sound, reframed and captioned for it -- kept with the
version (`renditions`) and watchable from it in the control room:
`renders/assemblies/SC-030/v3.mp4`, `v3.viral-vertical.mp4`,
`v3.square.mp4`. A name is a format style (or one of its `aka`); a mapping
gives an aspect and, optionally, `captions: true`. Anything else is
`deliver_problem`.

## Not yet

- A format's aspect and frame rate asked of generation (today the takes
  are generated in their own frame and reframed in the cut).
- A subject-aware reframe from the plan (the blocking frame knows where
  the subject is); today the window is centred or placed by hand.
- Renditions of a sequence; style for a sequence.
