---
id: CT-0053
title: Upscaling to 4K as a production standard
type: work
status: ready
owner: unassigned
created_at: 2026-10-03
updated_at: 2026-10-03
tags:
  - upscaling
  - 4k
  - delivery
  - generation
---

# What

The user (2026-10-03): is there an upscaler to 4K? It would be a good
requirement for a modern production standard. There is none -- not in
Cine Toaster, not in SINGULAR -- and this machine has no GPU.

# Findings

- **SeedVR2** (ByteDance Seed, Apache-2.0): one-step diffusion video
  super-resolution with video-native attention, temporally consistent
  (needs batches of at least 5 frames); open 3B weights; ComfyUI nodes.
  With FlashVSR, the open state of the art in 2026, compared to Topaz.
- **LTX-2** (the family Cine Toaster generates with): native 4K
  (3840x2160) by multi-stage generation with a latent spatial upscaler
  (`ltx-2-spatial-upscaler-x2`), applied during generation.
- Both need a GPU: RunPod, under the spend ledger (US$ 2 ceiling, about
  US$ 0.58 spent).

# Proposal (awaiting the user)

- Upscale **takes**, not finished versions: an upscaled take is a new take
  derived from the original, with lineage, so titles, captions, VFX and
  reframing are drawn natively at 4K (upscaling a finished cut would blur
  its text).
- **4K as a delivery target** of a version or rendition (UHD 3840x2160):
  the assembly uses each shot's upscaled take and names the shots that
  have none.
- Two paths: SeedVR2 after generation (any take, also existing ones);
  later, native 4K in LTX-2 generation.
- A plain FFmpeg resize is never called an upscale; `toast doctor` reports
  the capability.

# First step, if approved

A paid spike: one take upscaled to 4K by SeedVR2 on RunPod, estimate shown
and approved before sending, on a scratch copy (never SINGULAR itself);
measure cost, time and temporal consistency; then decide the job and the
provider adapter.

# Sources

- https://upsampler.com/blog/seedvr-vs-flashvsr-ai-video-super-resolution-2026
- https://huggingface.co/numz/SeedVR2_comfyUI
- https://docs.comfy.org/tutorials/utility/video-upscale
- https://huggingface.co/Lightricks/LTX-2
- https://ltxworkflow.com/resources/tutorials/ltx-23-multi-stage-latent-upscaling-comfyui
