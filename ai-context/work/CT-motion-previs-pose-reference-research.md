# Motion previs, pose conditioning, and audio separation — reference research

Status: research reference only; no implementation approved.
Date: 2026-11-18

## Purpose

Expand Cine Toaster's agent-discoverable filmmaking repertoire with independent references for spatial previsualization, pose/motion extraction, and audio stem separation. This is not a mandate to adopt a particular application, port a dependency, or change the canonical production model.

## Reference projects

- **Blockout** — https://github.com/wassermanproductions/blockout
  - Grey-box staging and actor/camera choreography, shot-specific camera coverage, deterministic motion-reference export, depth and optional normal passes, stills, machine-readable shot metadata, ComfyUI workflow examples, animated-camera glTF/Blender handoff, and MCP agent control.
  - Architectural insight: the scene's blocking can be authored independently from the final video generator or from Blender. Distinguish authored scene state from derived conditioning media.
- **Motion Previs Studio** — https://github.com/wassermanproductions/motion-previs-studio
  - Reference-video analysis for pose, depth, and camera motion; useful as an *inverse previs* input to planning and shot reconstruction.
  - Investigate exact formats and extraction fidelity before claiming interoperability with Cine Toaster.
- **Stem Studio** — https://github.com/wassermanproductions/stem-studio
  - Reference for separating a finished mix into dialogue, music, and sound-effects stems, relevant to editorial revision and audio finishing.
  - Source separation is an estimation; it does not recreate the original unmixed recordings.

## OpenPose and pose representation

- **OpenPose** — https://github.com/CMU-Perceptual-Computing-Lab/openpose
  - A human keypoint-estimation implementation and a widely recognized family of 2D skeleton/keypoint representations. Do not conflate the OpenPose implementation, OpenPose-style JSON/keypoint maps, and generic pose-conditioned video generation.
- **ControlNet** — https://github.com/lllyasviel/ControlNet
  - Reference for conditioning diffusion generation with spatial controls, including pose. Model-specific support and temporal behavior must be verified; a pose image is not a universal video-control interface.
- **DWPose** — https://github.com/IDEA-Research/DWPose
  - Alternative pose-estimation reference. Estimators should be replaceable; outputs require documented joint layout, coordinates, confidence, frame timing, and tracking identities.

Three distinct opportunities:
1. **Pose extraction:** video/images -> timestamped body/hand/face keypoints and confidence.
2. **Pose conditioning:** keypoint tracks or rendered skeleton sequences -> model-specific control assets.
3. **Motion transfer:** map source movement to a target performer/rig, accounting for differing skeletons, camera frames, occlusion, and temporal consistency.

These are *capabilities to investigate*, not features confirmed implemented. A single image of a skeleton does not preserve identity, 3D position, or motion continuity.

## Architectural fit and evaluation questions

Cine Toaster already documents spatial previs, geometry/movement checks, Blender-derived depth/segmentation, ComfyUI integrations, audio stems, and continuity checks in its README. Before proposing any new adapter, inventory existing commands, schemas, models, and workflows to avoid duplicating capabilities.

- **Interchange:** distinguish scene geometry/camera/animation, image-space keypoints, depth/normal/segmentation passes, and final video. Preserve fps, timebase, camera calibration, coordinate system, keypoint schema/version, actor identity, provenance, and licensing where available.
- **Continuity:** evaluate whether pose and motion references remain consistent across shots and take revisions, not just whether one generated clip follows a pose.
- **Agent toolbelt:** make these references discoverable as optional techniques with inputs, outputs, limitations, and links; agents should select them based on filmmaking intent and actual available tools, not a hard-coded preferred product.
- **Tool independence:** support Blender, other DCCs, procedural scene tools, or captured footage as possible sources; no Blender-only assumption.
- **Validation before integration:** check project activity/licensing, supported output formats, local vs remote compute, model compatibility, repeatability, performance, and source/target attribution.

## Relationship to existing research

- Review `ai-context/work/CT-LTX-VFX-comfyui-evaluation.md` before changing ComfyUI nodes or workflows.
- Review existing spatial previs, depth/segmentation, audio, and continuity implementations before suggesting new components.
- Preserve the distinction between external reference, researched opportunity, executable adapter, and working end-to-end production workflow.

## Work record

- Changed: added research references and evaluation vocabulary only.
- Not changed: production model, runtime, adapters, tests, or feature status.
- Validation: documentation-only change; repository README and AGENTS.md reviewed. No runtime tests executed.
- Remaining: detailed format/license verification and mapping to existing code before any implementation proposal.
