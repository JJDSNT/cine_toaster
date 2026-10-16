# A version's cut as OpenTimelineIO

Cine Toaster assembles a scene into kept versions. To finish a version in an
editor -- DaVinci Resolve, Premiere, FilmCraft, anything that reads
[OpenTimelineIO](https://opentimeline.io) -- ask for its cut beside it:

```bash
make install-otio                                   # once: the optional extra
toast assemble <project> <scene> --otio             # versions/vN.mp4, vN.otio, vN.media/
toast assemble <project> <scene> --otio --stems     # and the sound in its parts, on their own tracks
```

The same option is on the MCP server's `assemble_scene` (`otio: true`), so an
agent asks for it the way a person does.

## What the timeline holds

- **V1, the cut.** Each shot is a clip. A take points at its file, from its
  cut point, for as long as the shot plays. A shot the compositing graph drew
  -- a composite, a title, an effect, a still, a card -- points at its drawn
  picture, kept beside the version in `vN.media/`, since nothing else holds
  it. A solid screen is a generator, with no file. Each clip's metadata
  (`cine_toaster`) names its shot, its take and its file in the production.
- **Transitions** between clips, centred on the cut, of the frames the
  assembly overlapped: the editor finds the handles they need.
- **V2, disabled**: the version itself, to check the conform against.
- **A1**, the version's mix, and with `--stems`, **A2...**: dialogue, room,
  effects, ambience, music.

The timeline's length is the version's, frame for frame.

## What it does not carry yet

- J- and L-cuts are in the mix, not split across the tracks.
- A transition's own look (a matte, a shader) is drawn in the version; in the
  timeline it is a dissolve, with the transition's name in its metadata.
- A sequence's cut is not exported yet.

Paths are absolute file URLs, which editors resolve; move the production and
relink from the clips' metadata, which keeps each file's path in the
production.
