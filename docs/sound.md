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

## Surround (5.1)

```yaml
surround: "5.1"     # project.yaml, or a scene; off by default
```

Every version then carries two audio tracks: **stereo AAC first and
default** (a browser, a phone, a TV's speakers play it) and **5.1 (side)
as AC-3 at 640 kb/s**, which any 5.1 receiver decodes over HDMI/ARC or
S/PDIF; the player picks the track its output can carry (CT-0052, the
"master once, deliver several" model). The 5.1 is mixed from the same
pieces as the stereo, by film conventions: a take where someone speaks to
the centre, other takes to the front, ambience front and surrounds, music
front with a little in the surrounds, effects front with their low end in
the LFE (below 120 Hz). The version's summary gives both tracks'
loudness (EBU R128; the LFE not counted). Placing a sound where its subject
stands in the plan, a binaural track for headphones, and IAMF are the next
phases (CT-0052).

## Over several scenes

A music cue or an ambience that crosses scenes is declared on the sequence,
in `project.yaml`, with the same keys -- `from`, `to` and `until` name
scenes:

```yaml
sequences:
  - id: the-reply
    scenes: [SC-010, SC-030, SC-040]
    music: {id: main-theme, from: SC-010, at: 4.0, until: SC-040}
```

The sequence's assembly lays it over the scenes' versions, after the joins
between them. Every scene version keeps a sidecar of where its speech is
heard (`<version>.mp4.speech.json`), so the music ducks under the lines of
every scene it crosses. A scene's own music stays in its version: choose
one or the other for a stretch, or the two play together.

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

## Stems, for a final mix in a DAW

Cine Toaster lays the sound; a sound editor finishes it in a DAW such as
Ardour. Cine Toaster does not become a DAW. With `--stems`, a version also
carries its sound in parts, the film-mix way:

```bash
toast assemble <project> 3-01 --stems   # versions/v13.mp4 and versions/v13.stems/
```

| stem | what it holds |
| --- | --- |
| `dialogue` | the takes' sound while someone speaks, and the voice-overs |
| `room` | the takes' own sound when no one speaks |
| `effects` | the catalog's effects and Foley on shots |
| `ambience` | the catalog's beds |
| `music` | the catalog's music |

- **Format:** each stem is a stereo 48 kHz 24-bit WAV, the whole length of the
  cut, starting at zero. It has the version's own gains, fades, J/L handles
  and ducking. A stem with nothing in it is not written.
- **Summed:** laid together at unity, the stems are the version's stereo mix
  before its final limiter. The test checks this by loudness and envelope.
- **`stems.json`** lists them, with how to import them in Ardour:
  - Session > Import, "as new tracks", "at session start", one track per file;
  - the version's `.mp4` as the session video.
- **Not exported yet:** the 5.1 is mixed from the same parts, but it is not
  exported as stems.

## Not yet

- Generated music and effects from a model (Stable Audio Open, MMAudio
  from the picture), as a provider under the budget ceiling.
- A J/L split edit carrying sound across a cut.
- An imported library's category is a guess from the file name and its
  use; correct it in the item's `sound.toml`.
