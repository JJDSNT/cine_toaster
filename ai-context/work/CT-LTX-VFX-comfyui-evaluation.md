---
id: CT-LTX-VFX
title: LTX VFX and ComfyUI node evaluation
type: work
status: ready
owner: project
created_at: 2026-11-13
updated_at: 2026-11-13
tags:
  - vfx
  - comfyui
  - ltx
  - toolbelt
  - finops
---

# LTX VFX and ComfyUI node evaluation

## What
Investigate the LTX VFX capabilities as optional Cine Toaster toolbelt operations, with priority on **existing ComfyUI nodes and reusable workflows** rather than new implementations. This is research, not authorization to install nodes, spend money or implement.

Primary reference: https://comfy.org/ltx-vfx-features/

| Candidate capability | Investigation |
| --- | --- |
| Reframe | Video outpainting and aspect-ratio reframing; check ComfyUI API-node availability, credentials, fees and self-hosted compatibility |
| AlphaGen | Video alpha/matte extraction; identify weights, LoRAs, nodes, transparent-video output and temporal quality |
| SDR to HDR | Color and dynamic-range finishing; investigate ACEScct/AP1 claims, transforms and available workflows |
| Upscale | Video 4K/8K enhancement; investigate weights, nodes, VRAM, detail fidelity and temporal stability |

Do not conflate **ComfyUI API nodes** with **locally executed nodes or open-weight workflows**. Verify actual node names, repositories, licenses and workflow JSON before describing any route as available.

## Why
Cine Toaster already uses ComfyUI/LTX/RunPod and has a compositing graph, keying, mattes, depth signals, OpenColorIO and FinOps. Determine whether LTX VFX adds measurable capability without duplicating the compositor or tying the Project Core to a provider.

## Done
- Captured the official announcement and candidate capabilities.
- Recorded ComfyUI node/workflow discovery as the first integration gate.

## To do
1. Audit existing Cine Toaster ComfyUI adapters, toolbelt, matte/segmentation, OCIO, upscaling, compositor and RunPod/FinOps code. Identify overlaps and gaps.
2. For **each** capability, inventory the exact ComfyUI node classes, official/custom-node repositories, workflow JSON examples, dependency versions, model and LoRA identifiers, licenses, installation steps, input/output media formats, frame/audio handling, and whether inference is local or API-backed. Mark unverified items explicitly.
3. Verify whether the published Reframe API node and any premium Upscale/HDR API templates run on self-hosted ComfyUI/RunPod, and document credentials, pricing, availability and data-transfer implications. Compare with open-weight alternatives.
4. Map validated workflows to provider-neutral, typed Cine Toaster operations, keeping ComfyUI workflow graphs inside adapters. The Cine Toaster compositing graph remains authoritative for assembly.
5. Check asset lineage, alpha semantics, timebase, color spaces, HDR metadata, cancellation, retries, capability reporting via `toast doctor` and FinOps (GPU runtime, downloads, storage, API calls and cost per processed minute).
6. Design representative, approval-gated validation: hair/transparency/edge flicker for AlphaGen; camera and scene continuity for Reframe; highlights/color accuracy for SDR-HDR; detail/temporal coherence for Upscale. Compare against existing toolbelt behavior.
7. Decide per operation: integrate an existing node/workflow, use another external tool, defer or reject. Require measurable results and licenses before adoption.

## Decisions
- Prefer reusing existing ComfyUI nodes and workflows where suitable; avoid unnecessary adapters or mandatory provider dependencies.
- No new core compositing primitives solely because a ComfyUI workflow exposes them.
- No GPU/API spending, model downloads or custom-node installation without approval.
- Do not advertise these capabilities as implemented until actual end-to-end execution is validated.

## Validation
Documentation-only research intake. No nodes, workflows, models or runtime compatibility verified yet.
