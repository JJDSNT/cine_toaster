# LTX 2.5 production and finishing roadmap

Status: **pending investigation / integration**

This document records concrete LTX 2.5 capabilities that are relevant to Cine
Toaster but are **not implemented yet**. They are roadmap candidates, not
dependencies and not commitments to make LTX a privileged provider. Cine
Toaster should expose the production operation; LTX/ComfyUI is one provider
that can perform it.

This list deliberately lives beside `generation.md` and `storyboard-3d.md`:
the capabilities below bridge generation, 3D previs, compositing and finishing.

## Pending capabilities

### [ ] Layout to Render

**Production operation:** turn 3D blocking/playblast plus visual reference
guidance into a camera-aligned rendered video.

Candidate implementation:

- LTX-2.5 22B IC-LoRA Layout-To-Render
- ComfyUI-LTXVideo official workflow
- 3D source may come from the Cine Toaster Blender/USD storyboard pipeline
- visual reference may come from a master picture / approved storyboard image

Why it matters here: today the 3D animatic is explicitly only for checking and
never reaches a video model. Layout-to-Render creates a possible new,
*optional* route where the blockout can guide generation without making Blender
responsible for final character animation. This must remain distinct from the
existing storyboard semantics until the behavior is measured.

Reference:
https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render

Investigation:
- [ ] reproduce the official ComfyUI workflow
- [ ] measure camera-path and subject-layout adherence against Cine Toaster boards
- [ ] define the adapter capability independently of LTX
- [ ] decide which board/playblast artifact is the canonical input
- [ ] preserve inputs, workflow/version and output provenance
- [ ] test remote ComfyUI/Runpod execution

### [ ] Alpha Gen

**Production operation:** derive an alpha matte from an RGB video for
compositing.

Candidate implementation:

- LTX-2.5 22B IC-LoRA Alpha-Gen
- ComfyUI-LTXVideo

Expected use: selected take -> alpha matte -> compositing/VFX. The matte is a
derived artifact and must not replace the selected take.

Reference:
https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen

Investigation:
- [ ] reproduce the official workflow
- [ ] test hair, smoke, fire, transparency and motion edges
- [ ] define matte/alpha artifacts in the media pipeline
- [ ] evaluate RGBA / ProRes 4444 / image-sequence handoff
- [ ] connect the result to future compositor/VFX adapters
- [ ] record source digest and model/workflow provenance

### [ ] Refine Details

**Production operation:** run a generative detail-restoration/refinement pass on
an approved video while retaining the source as the authoritative take.

Candidate implementation:

- LTX-2.5 22B IC-LoRA Refine-Details
- ComfyUI-LTXVideo

Expected use: selected take -> refinement derivative -> review -> finishing.
Because the pass is generative, it must never silently overwrite its source.

Reference:
https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details

Investigation:
- [ ] reproduce the official workflow
- [ ] measure identity, geometry and temporal-continuity drift
- [ ] distinguish refinement from ordinary sharpening/upscaling in the capability model
- [ ] make before/after review possible
- [ ] retain source, parameters, model/workflow version and output provenance

### [ ] Native 4K / 8K via Tiled Fusion

**Production operation:** produce a delivery-resolution derivative of an
approved video through tiled video-to-video processing.

Candidate implementation:

- LTX-2.5 V2V TiledFusion Native 4K/8K
- ComfyUI-LTXVideo official workflow

This belongs after take selection: expensive delivery-resolution work should
normally be performed on an approved take, not on every probabilistic
generation candidate.

Reference:
https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Native_4K_8K.json

Investigation:
- [ ] reproduce the official 4K/8K workflow
- [ ] benchmark tile sizes, overlap, VRAM, time and visible seams
- [ ] test temporal consistency across tiles
- [ ] define delivery-resolution derivatives without changing the canonical take
- [ ] record resolution, tile configuration and workflow provenance
- [ ] measure practical Runpod GPU requirements and cost

### [ ] SDR to HDR

**Production operation:** create an HDR finishing derivative from an SDR source.

Candidate implementation:

- LTX-2.5 IC-LoRA SDR-to-HDR Distilled
- ComfyUI-LTXVideo official HDR workflow
- HDR post-processing / high-precision decode

This is particularly useful at the provider boundary: a production may target
HDR even when the generator that produced the selected take only emits SDR.

Reference:
https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/HDR_workflows/LTX-2.5_ICLoRA_SDR_to_HDR_Distilled.json

Investigation:
- [ ] reproduce the official workflow
- [ ] document input/output transfer functions, primaries, bit depth and container expectations
- [ ] verify the high-precision/HDR handoff through Cine Toaster
- [ ] define HDR metadata/provenance
- [ ] test interoperability with FFmpeg, Blender and future compositing/color tools
- [ ] keep SDR source and HDR derivative separately reviewable

## Possible finishing flow

```text
3D blocking/playblast + reference image
                |
                v
         Layout to Render
                |
                v
              TAKE
                |
                v
          take selection
                |
        +-------+--------+
        |                |
        v                v
    Alpha Gen      Refine Details
        |                |
        v                v
  compositing/VFX   detail derivative
        |                |
        +-------+--------+
                |
                v
       Native 4K / 8K
                |
                v
       SDR -> HDR (when needed)
                |
                v
        grade / delivery
```

The diagram is illustrative, not a required fixed pipeline. Operations should
remain independently callable and composable.

## Architectural constraint

Do **not** model these as first-class "LTX features" in Project Core. Model the
stable production concepts -- layout-guided render, matte generation, detail
refinement, delivery-resolution processing and dynamic-range conversion -- and
let generation/media adapters advertise implementations.

The ComfyUI workflows are valuable because they provide concrete executable
reference implementations and fit Cine Toaster's intended ComfyUI/local-or-
remote GPU integration. Provider-specific parameters and workflow JSON belong at
the adapter boundary.

## Definition of done for an integration

A capability moves out of this pending list only when Cine Toaster can:

1. detect/report the provider capability;
2. show the exact planned inputs before execution;
3. execute it through an adapter without Project Core depending on LTX;
4. retain the source artifact unchanged;
5. store the result as a derived, reviewable artifact;
6. record reproducible provenance (source digests, model/workflow, parameters,
   execution record and cost when available);
7. expose failure/cancellation honestly through the job system; and
8. exercise the path with automated tests plus at least one real media fixture
   or documented production measurement.

## Upstream references

- Lightricks LTX-2.5 Layout-To-Render:
  https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render
- Lightricks LTX-2.5 Alpha-Gen:
  https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen
- Lightricks LTX-2.5 Refine-Details:
  https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details
- ComfyUI-LTXVideo SDR-to-HDR workflow:
  https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/HDR_workflows/LTX-2.5_ICLoRA_SDR_to_HDR_Distilled.json
- ComfyUI-LTXVideo Native 4K/8K TiledFusion workflow:
  https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Native_4K_8K.json
