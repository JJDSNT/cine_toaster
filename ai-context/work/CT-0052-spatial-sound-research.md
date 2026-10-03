---
id: CT-0052
title: Surround and spatial sound -- research (playback chosen by the hardware present)
type: work
status: ready
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
