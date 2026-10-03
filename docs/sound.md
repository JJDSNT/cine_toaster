# Sound and music

A cut is more than its takes' own sound. Cine Toaster lays three kinds of
sound under it, from a catalog (CT-0048), as SINGULAR did with its ambience
beds, effects and layers:

- **shot sounds** -- effects and Foley a shot places at a time;
- **ambience** -- a bed under the scene, from a shot to another;
- **music** -- cues under the scene, lowered under speech.

## The catalog

`toast sound list <project>`, the control room's **Sound** room, and the
MCP tool `list_sounds`. An item is `sound_assets/<id>/sound.toml`:

```toml
id = "station-hum"
name = "Station hum"
category = "ambience"            # ambience | effect | foley | music
says = "A facility's low machine hum with a slow, soft beep every 2.4 s."
use_when = ["A control room, a lab, a ship"]

[source]
generate = '''anoisesrc=color=brown:a=0.05:d={d}:r=48000,lowpass=f=180'''
# or a recording beside the manifest:
# file = "door.wav"
# provenance = "Freesound, by someone"
# licence = "CC0 1.0"
# credit = "..."                 # when the licence asks for one
# url = "https://..."
# status = "provisional"         # or preview-hq; empty when final

[params]                          # the category's defaults, overridable
level = -34                       # integrated LUFS (speech is at -20)
loop = true
fade_in = 1.0
fade_out = 1.2
duck = 0                          # dB lowered under speech
duration = 0                      # seconds; 0 = as long as placed
```

Layers: built in, `CINE_TOASTER_SOUNDS_PATH`, then the production's
`sounds/`; a later layer replaces an item with the same id. The 26 built-in
items are generated with FFmpeg -- ours, no licence to check: room tone,
station hum, corridor, hospital room, air conditioning, distant city, low
pulse, wind, rain; breath, boom, beep, dissonant beep, flatline, alarm,
heartbeat, whoosh, impact, glitch, electric buzz, thunder; door and
footsteps (Foley); tension drone, riser and a sad pad (music).

Category defaults: ambience -34 LUFS and looped; effects -24; Foley -28;
music -24, faded in and out, ducked 10 dB.

## Placing sound

```yaml
ambience: [room-tone, {id: rain, from: P4, level: -30}]
music: {id: tension-drone, from: P2, at: 0.5, until: P6, duck: 12}
shots:
  - n: 2
    sounds: [door, {id: alarm, at: 1.2, level: -20}]
```

- A shot's `at` is seconds into the shot **as cut**; a sound runs for its
  `duration`, past the shot if it is longer.
- A bed runs from `from` (the first shot by default, `at` seconds in) to the
  end of `to` (inclusive) or the start of `until` (exclusive) -- SINGULAR's
  bed that stops early -- or for `duration`; the last shot by default.
- A shot not in a version (no take, out of the cut) makes its beds start or
  end elsewhere, and the version's notes say so.
- Unknown ids, unknown keys and negative times are errors
  (`sound_problem`): a sound would be lost, not guessed.

Each placed sound is rendered, measured (EBU R128) and brought to its
level, then mixed under the joined cut with a limiter. Music is lowered by
`duck` dB under every line the cut knows of (the takes' word timings),
with 0.3 s ramps. The version's summary lists what was laid, at what gain,
under which licence.

## Sources

SINGULAR's two, and one for music. Searching writes nothing; fetching
writes `sounds/<id>/` with the file and its manifest.

```bash
toast sound search freesound "metal door" --env-file ~/confyui/.env
toast sound fetch film freesound 700702 --as metal-door --category foley --env-file ~/confyui/.env

toast sound search sonniss "hologram"
toast sound fetch film sonniss "CB Sound Design - .../CYBERDECK_General_UI_18.wav" --as ui-touch

toast sound search openverse "dark ambient"          # music; --effects for any audio
toast sound fetch film openverse <id> --as main-theme
```

- **Freesound**: Creative Commons 0 only (no credit, commercial use). The
  API key (`FREESOUND_API_KEY`) gives the HQ preview MP3, so items are
  `preview-hq`.
- **Sonniss GDC**: royalty-free, commercial, no credit, never
  redistributed -- read from an unofficial archive.org mirror, so items are
  `provisional`, and a scene using one gets a `sound_provisional` advice:
  replace the file with the official pack's
  (https://sonniss.com/gameaudiogdc) before release.
- **Openverse**: music from Jamendo, ccMixter, Wikimedia and others, only
  CC0, public domain and CC BY; a CC BY item keeps its credit for the end
  titles.

A library already on disk, described by a `manifest.csv` (file,
provenance, licence, url, status, use -- or SINGULAR's own column names),
is registered where it is:

```bash
toast sound import film ~/confyui/singular/sons --prefix singular-
```

SINGULAR's 53 sounds become catalog items pointing at its files, with their
licences and statuses; nothing in SINGULAR is written.

## Not yet

- Generated music and effects from a model (Stable Audio Open, MMAudio
  from the picture), as a provider under the budget ceiling.
- A J/L split edit carrying sound across a cut.
- Stems (dialogue, effects, music) as separate files for a final mix.
- An imported library's category is a guess from the file name and its
  use; correct it in the item's `sound.toml`.
