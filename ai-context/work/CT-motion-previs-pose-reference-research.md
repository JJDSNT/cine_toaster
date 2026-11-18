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

## TEIN / Sirio Berati — programmable camera direction and subject replacement (2026-11-18)

**Primary code reference:** https://github.com/sirioberati/ai-filmmaking-camera-control-seedance-2-5

This public MIT-licensed repository is more than a 3D editor demo: it documents a reproducible *camera-first reference-video method*. Its Three.js scene engine runs with Remotion, with camera rigs and framing/cut checks; 137 coded shot templates, their grey-box reference clips, prompts, submission metadata and comparison results; 24 environment references; and an agent-oriented `skills/cinematic-previs/` directory. The template catalogue is at `templates/INDEX.md`, the rendering engine at `engine/cinematic/`, the evaluation tools at `tools/seedance/`, and limitations at `docs/known-limits.md`. Source: project README and `docs/build-your-own-template.md`.

**Key mechanism:** a *pill clip* uses plain environments and striped capsule/pin stand-ins for actors, specifying scale, position, facing and timing without giving the generator detailed anatomy to imitate. A reference video conveys camera motion **and** subject motion; minimizing visual detail in stand-ins aims to prevent the generator from copying an artificial performer. A still/contact-sheet alternative is documented, but lacks the same temporal guidance. The author reports that frame-specific cuts drift more with a contact sheet; these are project observations, not universal model guarantees.

**Cinematographic controls to study:** named camera support/rig, lens and shot size, movement duration, path speed, actor-facing direction, start/end composition, eyeline, cuts and continuity of action. The project describes measured QA checks (distance, shot size, camera path, cut rules) and exceptions rather than relying on prompts alone. Study these as reusable *validation concepts*, not as universally correct filmmaking laws. Some examples are experimental; the repo explicitly documents failures and unproven findings.

**Dependencies and scope:** local reference rendering uses Node/Remotion/Three.js and FFmpeg; final generation goes through the Tein-hosted Seedance API/MCP with an account and key. The MIT license for this source does **not** imply Seedance weights, service, hosted models or sample media are open source. Do not hardwire the Tein API, Seedance, a Three.js scene format, or the 137 templates into the Cine Toaster Core. A template is an *optional repertoire item*, not a canonical film object unless a future design justifies it.

**Secondary reference:** https://github.com/sirioberati/Genjustsu-Open-Source-Workflow

Genjustsu is a separate MIT-licensed, locally orchestrated workflow for *video subject replacement*, using depth estimation, SAM 3 video masks, optional MediaPipe face landmarks, vocal isolation/pitch processing, hosted generation and restoration of the original soundtrack. It explicitly gates generation on human review of masks/landmarks and artifact hashes, creates low-cost drafts before approved HD generation, and warns about limits of single-speaker face tracking and hosted-media URLs. This is a useful example of provenance-bound approval and temporal review, not proof of general-purpose character continuity. It depends on external services and third-party licenses; example media are not covered by its MIT code grant.

**Specific page caveat:** the Tein `open-source/seedance-3d-blockout-editor` web page and the previously mentioned `sirioberati/seedance-blockout-editor` repository are **not verified as an independently downloadable public codebase**. Do not equate that page with the confirmed public camera-control repository. Do not record, share or reuse the `mcp_token` query parameter from a user-provided link; treat it as a credential.

### Comparison and architectural opportunities

| Reference | Distinctive idea | Cine Toaster question |
| --- | --- | --- |
| Blockout | 3D authored blocking, cameras and conditioning passes | How do we interchange shot intent and derived passes? |
| Motion Previs Studio | Recover motion/pose/camera cues from existing footage | How do extracted cues map back to the film's shots? |
| OpenPose / DWPose | Human keypoints and pose representation | How are joint schemas, timebase and identity documented? |
| TEIN camera-control | Programmatic camera rigs + intentionally featureless actor stand-ins + measured QA | Can a shot's direction be tested before generation, without mandating a renderer? |
| Genjustsu | Depth/masks/face mesh, reviewed replacement, audio restoration | Can review/approval bind exactly to the evidence used to generate a take? |
| Stem Studio | Separate dialogue/music/effects from a mix | Where does derived audio sit in finishing and provenance? |

The interesting distinction from OpenPose: **pill-based blocking controls spatial presence, timing and camera without detailed skeletal pose**; OpenPose-style keypoints express articulated body motion but do not by themselves define lens, camera movement, world geometry or performer identity. They may complement each other; neither is a complete continuity solution.

### Evaluation before proposing implementation

1. Inventory Cine Toaster's current scene geometry, blocking/3D storyboard, camera motion, compositing/depth/segmentation, take provenance, audio stems, ComfyUI and continuity facilities.
2. Check whether existing interchange can carry camera trajectory and intrinsics, actor placement/facing, joint tracks (where available), exact timebase, and references to rendered control video or passes without introducing provider-owned Core state.
3. Compare *video control vs contact-sheet control* on the same shot and measure camera adherence, actor movement, cut timing, continuity, repeatability and cost. Attribute observed results to model/version and test inputs.
4. Review licensing, portability and availability of each codebase and external model/service. Keep local reference rendering separate from paid inference and do not submit media or credentials without authorization.
5. For agents, preserve discoverable options and evidence rather than telling agents which implementation to choose. Document the input/output contract and observed strengths/limits of each technique.

### Work record update

- **What / why:** extend the existing pose/previs research with confirmed TEIN public code references and the camera-first control method.
- **Done:** repository-level source and documentation review; conceptual comparison with existing references; integration boundaries and evaluation questions recorded.
- **Decisions:** research-only; no new adapter, API key, model download, provider commitment, branch or runtime feature.
- **To do:** inspect actual template/rig/QA source and compare against existing Cine Toaster code before recommending integration; verify independent editor page/source separately.
- **Validation:** documentation inspection only; no build, render, model generation or tests executed.

## Recovered Seedance 3D Blockout Editor source — verification (2026-11-18)

**Public copies inspected:**
- https://github.com/josephcrown920/seedance-blockout-editor
- https://github.com/cbunseng/seedance-blockout-editor-private

Both repositories expose the same README, `index.html`, `bridge.mjs`, and `package.json` blob SHAs in the checked files. This demonstrates matching source files, **not** complete tree or history equivalence, nor authorization by the original author. The original Sirio Berati repository is still not confirmed accessible.

**Licensing correction:** the recovered editor's `LICENSE`, `NOTICE` reference and `package.json` declare **Apache-2.0**, copyright 2026 Sirio Berati. Do not confuse this with the separate MIT-licensed camera-control project. Before reusing code, inspect provenance, notices, dependency licenses, and whether copies are authorized; links are sufficient for research.

**Source layout and actual behavior:**
- `index.html`: interactive Three.js editor with synchronized 3D scene, overhead floor plan, camera/frustum/path, final-shot view, editable camera keys and timeline.
- `tools/previs/`: JSON shot-sheet compiler and checker. A world JS file owns actors, trajectories and timed events, independent of the shot sheet. Shot entries specify `start`, `preset`, `subject`, optional `look`, `params`, `track`, `focus`, and notes. Documentation enumerates **21 presets**, including locked, chase, over-shoulder, crane, top-down and FPV.
- `bridge.mjs`: local project/draft helper, reference-video render and optional Tein generation integration. `render.mjs` produces stills/video, with Chromium/Puppeteer and FFmpeg dependencies; Node >=20 required.
- The editor's assisted review uses local Claude Code for camera fixes, shot critique, prompt writing, pacing, before/after images, undo and notes attached to time spans. These functions are optional except that its documented default generation prompt route requires the bundled Seedance skill; a simple test-only prompt writer exists.
- Reference outputs include video, sketch, depth and contact sheets (up to 16 frames); output variants have different temporal guidance. The default generation route incurs external Tein API costs, while `TEIN_SEND=0` disables paid sends.
- The documented `npm test` checks a sample shot sheet; the README also acknowledges a camera-turn threshold failure in another example. Do not infer all scenarios pass validation.

**Architecture comparison with Blockout:**
- The recovered editor demonstrates an actual *interactive cinematography workspace* with world/shot separation, camera editing, explicit temporal notes, review, history and generation submission.
- Blockout is a complementary reference for reusable shot/actor staging and conditioning export. Do not treat the tools as interchangeable solely because both use simplified 3D.
- Cine Toaster already has a canonical film model, spatial planning, camera previews, review decisions and continuity checks. Study whether the recovered editor's world/shot-sheet separation and review ergonomics fill an actual gap before considering reuse. In particular, avoid importing its fixed 30-second take assumption or provider-specific prompt rules into the Core.
- OpenPose remains complementary: skeleton keypoints describe articulated body motion; this editor primarily provides camera trajectory, subject tracking and coarse world events.

**Follow-up checks:** compare the two copies' complete trees and commit history, confirm original author/provenance, inspect specific camera-key and timebase code, evaluate renderer output determinism, and map current Cine Toaster functionality against the editor's workflow. No installation, code import, model call, tests or spending performed.

