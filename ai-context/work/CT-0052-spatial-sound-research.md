---
id: CT-0052
title: Surround and spatial sound -- research (playback chosen by the hardware present)
type: work
status: blocked
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - sound
  - surround
  - spatial
  - research
  - delivery
---

# What

Research only -- nothing implemented. The user's goal (2026-10-03): sound
"like Netflix", where the experience follows the hardware present: a 5.1
home theatre (the user's own) gets 5.1, a TV or laptop gets stereo,
headphones get binaural. The user asked for deeper research before any
implementation (CT-0048 note), and observed that much open-source material
exists.

# Findings

**How the "Netflix model" works.** A title is mixed once (Atmos or 5.1)
and delivered as several audio streams; the device or player picks the
one its output can carry. Netflix streams 5.1 as Dolby Digital Plus
(E-AC-3, up to 640 kb/s) and Atmos (up to 768 kb/s) only to devices that
report support or are connected to a 5.1 system; it derives 5.1 and
stereo from Atmos by Dolby downmix parameters. Nothing in this model needs
one file per device: one file with several tracks, or one stream with
several audio renditions, plus a player that chooses.

**Choosing by hardware, three places it already happens.**

1. *Files with several tracks* (MP4/MKV): stereo AAC first (plays
   anywhere) and 5.1 E-AC-3 or AC-3 (passed through HDMI/ARC to a
   receiver). Kodi, VLC, TVs and Jellyfin choose and pass through; Jellyfin
   (GPL-2.0, an open home "Netflix") selects or transcodes per client
   device profile. Pitfalls seen in its forums: a client may claim a codec
   its HDMI chain cannot carry (S/PDIF/ARC carries 5.1 AC-3/E-AC-3
   bitstream, not multichannel PCM); downmixed 5.1 often sounds quiet
   because dialogue sits alone in the centre.
2. *Streaming*: HLS/DASH alternate audio groups -- `EXT-X-MEDIA` with
   `CHANNELS="2"` and `CHANNELS="6"`, AAC and AC-3/E-AC-3 groups -- and the
   player picks.
3. *The browser* (the control room): the Media Capabilities API
   (`decodingInfo` with `channels` and `spatialRendering`) and the Web
   Audio `destination.maxChannelCount` tell what the device can decode and
   output; the page can then choose the 5.1, stereo or binaural track.
   Browsers rarely pass a bitstream over HDMI, so this is for previewing
   and laptops, not the home theatre.

**Formats.**

- *Channel-based 5.1/7.1*: universal; FFmpeg encodes AC-3 and E-AC-3 and
  places sound with `pan`; this machine's FFmpeg 6.1 already has both.
- *IAMF / Eclipsa Audio* (Alliance for Open Media; Google and Samsung,
  2025): an **open, royalty-free** immersive format (beds, objects,
  ambisonics) with an open reference renderer (`libiamf`, BSD-3-Clause-
  Clear), tools (`iamf-tools`), a DAW plugin (`eclipsa-audio-plugin`,
  Apache-2.0); YouTube accepts it, Chrome and Android were announced;
  FFmpeg ≥ 7.0 writes it (an `iamf` muxer; a 2026 CVE in its writer means a
  patched build). This machine's FFmpeg 6.1 has no IAMF muxer.
- *Dolby Atmos*: what Netflix uses, but the renderer and encoder are
  proprietary and licensed -- outside ADR 0011 unless the user licenses it.
- *ADM* (ITU-R BS.2076, the broadcast object model): the EBU's open
  renderer `ear` (Python, BSD-3-Clause-Clear) and `libear` (C++,
  Apache-2.0) render beds, objects and scenes to any speaker layout -- a
  candidate interchange between Cine Toaster's plan and any renderer.
- *Ambisonics and binaural*: `libspatialaudio` (LGPL-2.1+, used by VLC;
  HOA up to 3rd order, binaural with SOFA HRTFs), the Spatial Audio
  Framework (mixed ISC/GPL), Resonance Audio (Apache-2.0, inactive since
  2022), OpenAL Soft (LGPL, real-time). FFmpeg's `sofalizer` and
  `headphone` filters render binaural from a SOFA HRTF file.

**The reference the user sent** (danieldotwav/Spatial-Audio-Renderer): a
real-time game renderer on OpenAL, no licence -- a concept only.

**What Cine Toaster brings that others do not**: the plan knows where
every subject and the camera stand in every shot. A voice can be placed
where its speaker is on screen (or behind the camera), an effect where its
source is, and the placement follows the cut -- object positions most
productions author by hand.

**Added after the user's own search (2026-10-03).**

- *Cavern* (github.com/VoidXH/Cavern, C#/.NET, active): an object-based
  engine that decodes Dolby Atmos (E-AC-3 JOC, TrueHD), reads ADM BWF and
  DAMF, renders to any layout, HRTF, room correction, upmixing. Its licence
  is **source-available, not open**: no selling, attribution, and the
  author's permission for public or commercial use. It cannot be part of
  Cine Toaster (ADR 0011: the terms bind any use in the product); it can
  be a personal tool for the user to check a mix on the 5.1 system or
  decode Atmos material for reference.
- *Grapes 3D Audio Control* (grapes-3d.com): commercial and closed (VST3
  and standalone); a controller that choreographs sound objects over time
  and sends positions over OSC to an existing renderer (Atmos, d&b, L-ISA).
  Not an engine, not a dependency. Its idea -- object movement on a
  timeline -- is what Cine Toaster derives from the plan; OSC or ADM
  automation out of the plan could later drive such tools.
- *IAMF* (Sounding Future, 2025-10): confirms IAMF as the open alternative
  among MPEG-H, Dolby Atmos and DTS:X.
- *Sony 360 Reality Audio* (built on MPEG-H, mostly music) and *DTS:X*:
  proprietary, the same rule as Atmos.

# Recommended architecture (for the user to approve)

*Master once, deliver several, let the player choose.*

1. **Mix**: the assembly's sound timeline (takes, catalog cues, beds,
   music) mixed to a **5.1 bed** -- dialogue to the centre by default,
   music and ambience to L/R and surrounds, low effects to the LFE -- with
   object positions from the plan as an option per shot.
2. **Derive** from the 5.1: a stereo downmix (with the dialogue level
   checked: the "quiet dialogue" problem) and a binaural render
   (`sofalizer` with an open SOFA HRTF).
3. **Package**: every version (and rendition) as one file with tracks in
   this order: stereo AAC (default), 5.1 E-AC-3, binaural AAC (labelled
   for headphones); later an IAMF track.
4. **Choose by hardware**: in the control room, Media Capabilities and
   `maxChannelCount` choose the track; at home, the user's player (TV app,
   Kodi, Jellyfin) chooses and passes 5.1 to the receiver; for streaming,
   HLS/DASH audio groups.
5. **Check**: loudness per layout (EBU R128 on 5.1 with the LFE
   excluded), the downmix's dialogue, a binaural preview for anyone
   without speakers.

# Phases, if approved

1. 5.1 bed + stereo downmix tracks in versions (FFmpeg only, no new
   dependency).
2. Placement from the plan (screen side and depth to pan; off-screen to
   surrounds; a per-shot override).
3. The control room picks the track by Media Capabilities; a binaural
   track for headphones (an open SOFA HRTF, licence checked).
4. IAMF/Eclipsa delivery once a patched FFmpeg ≥ 7.x is installed;
   ADM export (`ear`) as interchange.
5. Atmos only if the user licenses Dolby's tools.

# Questions for the user

- What plays to the 5.1 system today: the TV's own apps, a PC over HDMI,
  Kodi, Jellyfin, a streaming stick? (It decides the codec: E-AC-3 vs AC-3
  vs multichannel PCM.)
- Is an IAMF/Eclipsa track worth having (YouTube, newer Samsung TVs), or is
  5.1 enough for now?

# Validation

Desk research only (2026-10-03): web sources below; repository licences
read from GitHub; local FFmpeg checked (6.1.1: `ac3`, `eac3`, `pan`,
`surround`, `sofalizer`, `headphone` present; no `iamf` muxer).

# Sources

- Netflix help, audio quality: https://help.netflix.com/en/node/109477
- Delivering a mix to Netflix: https://www.production-expert.com/production-expert-1/how-to-optimise-an-audio-mix-for-delivery-to-netflix
- Media Capabilities API: https://developer.mozilla.org/en-US/docs/Web/API/Media_Capabilities_API
- Spatial audio in the browser (Meta): https://developers.meta.com/horizon/documentation/web/browser-audio/
- HLS master playlist with Dolby Digital Plus: https://ott.dolby.com/OnDelKits/DDP/Dolby_Digital_Plus_Online_Delivery_Kit_v1.4.1/Documentation/Content_Creation/SDM/help_files/topics/c_hls_multi_codec_cc.html
- Audio in HLS, DASH and CMAF: https://www.forasoft.com/learn/audio-for-video/articles-audio/audio-in-hls-dash-cmaf
- Eclipsa Audio: https://opensource.googleblog.com/2025/01/introducing-eclipsa-audio-immersive-audio-for-everyone.html
- FFmpeg IAMF muxer: https://ffmpeg.org/doxygen/8.0/iamfenc_8c.html
- EBU ADM Renderer: https://tech.ebu.ch/news/2018/03/ebu-publishes-open-source-renderer-for-adm-next-generation-audio , https://github.com/ebu/libear
- libspatialaudio 0.4: https://jbkempf.com/blog/2025/libspatialaudio-0.4
- Jellyfin passthrough and device profiles: https://forum.jellyfin.org/t-force-audio-passthrough
- Cavern and its licence: https://github.com/VoidXH/Cavern
- Grapes 3D Audio Control: https://grapes-3d.com
- IAMF, an open 3D audio format: https://soundingfuture.com

# Done: phase 1, a 5.1 track beside the stereo (2026-10-03)

The user: "ok, advance at your best judgement" after the research; the
question of what feeds their 5.1 is still open, so phase 1 uses the
format every 5.1 receiver decodes, AC-3.

- `surround.py`: the 5.1 (side) mix from the same pieces as the stereo,
  routed by kind (`ROUTES`: dialogue takes to the centre, other takes
  front, ambience front and surrounds, music front and a little surround,
  effects front with the LFE), the LFE low-passed at 120 Hz, a limiter;
  attached as a second track (AC-3 640 kb/s, named "5.1", not default)
  after the stereo AAC (default, "Stereo"); loudness of each track.
- `surround: "5.1"` on the production or a scene (`false`, `stereo`,
  `none` mean off); `Plan.surround`, `Plan.loudness`; the version's summary
  names the tracks and their loudness. Renditions inherit it.
- Tests: `tests/test_surround.py` (two tracks in order and disposition;
  dialogue in the centre, a rain bed front and back, a silent LFE; a boom
  in the LFE; the field and its off values).

Remains: phase 2 (placement from the plan), phase 3 (the control room
picks the track by Media Capabilities; a binaural track), phase 4 (IAMF
with a patched FFmpeg >= 7), and a sequence's own 5.1 (a sequence today
re-mixes the scene versions' stereo).

# Paused by the user (2026-10-03)

"These are future improvements": phase 1 is kept (it works, tested, off by
default); the rest waits until the open work is closed. The design worked
out for phase 2, so it is not lost:

- a shot's sound names its source: `sounds: [{id: alarm, at: 1, source:
  SPEAKER}]` (a subject; set pieces once the blocking frame gives their
  horizontal place);
- the source's angle from the camera comes from the blocking frame at the
  cue's shot (`figures[].angle`, negative = left; `behind`);
- the 5.1 places it by pairwise amplitude panning between the two nearest
  speakers of the ITU layout (C 0°, L/R ±30°, Ls/Rs ±110°), behind the
  camera into the surrounds; the stereo track by a constant-power balance
  clamped to ±30°;
- dialogue stays in the centre by convention (a per-shot `follow` later);
- a moving source: its start angle first, interpolation later.

Unblock when the user returns to sound (also: what feeds their 5.1).
