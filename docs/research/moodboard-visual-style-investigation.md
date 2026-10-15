# Moodboard / Visual Style References — Future Investigation

> **Status:** investigation candidate. This document records a topic for later evaluation; it is **not** a decision to add a Moodboard feature to Cine Toaster.

## Question

Would a first-class **Moodboard / Visual Style Reference** capability improve Cine Toaster's filmmaking workflow, particularly visual consistency and art direction across scenes and shots?

The investigation should determine whether moodboards provide enough value beyond the project's existing reference-image, storyboard, prompt, catalog, and visual-consistency mechanisms to justify becoming a distinct project concept.

## What "moodboard" means here

In this investigation, a moodboard is primarily a collection of visual references used to communicate or condition aspects such as:

- color palette;
- lighting;
- texture;
- atmosphere;
- photographic/cinematic style;
- production design;
- architecture/environment;
- wardrobe or material language;
- overall visual tone.

The term **mood** should not be confused with direct interpretation of a character's emotion.

## Moodboard is not the emotion/performance model

Cine Toaster has separately considered catalogs/mechanisms for expressing character emotion, including facial expression, micro-expression, gaze, gesture, posture, and performance.

These concerns should remain conceptually distinct:

```text
                    SHOT INTENT
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
        VISUAL MOOD              PERFORMANCE
             │                       │
         Moodboard              Emotion model
             │                       │
        palette/style          emotion/intensity
        lighting               facial expression
        atmosphere             micro-expression
        texture                gaze
        production design      gesture/posture
             │                       │
             └───────────┬───────────┘
                         ▼
                        SHOT
```

A scene may also have a higher-level **dramatic/emotional intent** that influences both sides, as well as camera, editing, sound design, and music.

## Potential role in Cine Toaster

If adopted, moodboards should probably be modeled as a Cine Toaster project capability rather than as a ComfyUI-specific feature.

A possible future abstraction:

```text
Project / Film
     │
     ├── Visual Bible
     │
     ├── Moodboards
     │      ├── palette
     │      ├── lighting
     │      ├── texture
     │      ├── atmosphere
     │      └── visual references
     │
     ├── Character References
     ├── Location References
     └── Object / Prop References
              │
              ▼
         Scene / Shot
              │
              ▼
       Provider Adapter
              │
      ┌───────┼────────┐
      ▼       ▼        ▼
   ComfyUI  Provider  textual/
   workflow adapters  semantic fallback
```

This would keep the authoring model independent from any specific image/video model or conditioning technique.

## Relationship to storyboard and 3D blocking

Moodboards would not replace the planned dual storyboard/reference workflow.

A useful separation to evaluate is:

```text
3D Storyboard / Blocking
→ geometry, staging, composition, camera placement

Shot / Image Reference
→ target frame, subject/location/object identity

Moodboard
→ visual language, atmosphere, palette, lighting, texture

Performance / Emotion
→ acting, expression, gaze, gesture, posture
```

The final generation may combine these signals according to what the selected provider/model supports.

This separation could reduce the need for one reference image or one prompt to simultaneously encode geometry, identity, environment, visual style, and performance.

## ComfyUI references to investigate

### ComfyUI-Krea2Moodboard

Repository:

https://github.com/RedNodeAI/ComfyUI-Krea2Moodboard

Investigate whether this provides useful visual mood/style conditioning for Krea 2 workflows, including:

- multiple visual references;
- style/vibe transfer;
- control over reference strength;
- separation of style and subject/identity;
- interaction between moodboard and character references;
- suitability for still-image and video pipelines;
- workflow complexity and runtime cost.

### ComfyUI-Krea-Moodboards

Repository:

https://github.com/Andro-Meta/ComfyUI-Krea-Moodboards

Investigate its large moodboard/style catalog as a potentially different capability:

- browsing/discovery of visual styles;
- search;
- favorites;
- randomization;
- style mashups;
- conversion of moodboard/style choices into textual guidance.

This should be evaluated separately from true visual-reference conditioning. A **style catalog** and a **visual moodboard** may be complementary but are not necessarily the same feature.

## Provider-agnostic hypothesis

If Cine Toaster eventually exposes Moodboard as a first-class concept, providers could interpret it differently:

```text
Cine Toaster Moodboard
          │
          ▼
   Provider Adapter
          │
          ├── visual conditioning
          ├── style adapter / reference adapter
          ├── embedding / vision conditioning
          ├── prompt/style extraction
          ├── provider-native moodboard feature
          └── unsupported → semantic/text fallback
```

The project model should describe creative intent; adapters should translate that intent into provider-specific mechanisms.

## Questions for later evaluation

1. Does a dedicated moodboard improve cross-shot and cross-scene visual consistency?
2. Is it materially different from the existing/planned Visual Bible?
3. Should moodboards exist at project, sequence, scene, and/or shot scope?
4. Should a shot inherit a project/sequence moodboard and override selected attributes?
5. Should references have semantic roles such as palette, lighting, texture, architecture, wardrobe, or cinematography?
6. How should moodboard influence be represented and versioned?
7. How do moodboards interact with character and location identity references?
8. How should they interact with 3D storyboard/blocking?
9. Which current image and video providers can consume visual mood/style references natively?
10. When only textual conditioning is supported, can a vision model reliably translate the moodboard into reusable visual-language descriptors?
11. How should moodboard consistency be evaluated automatically?
12. Does the workflow improve creative control enough to justify additional UI and project-model complexity?
13. Should a catalog of predefined styles be part of Moodboard or remain a separate catalog?
14. Can moodboard information be propagated from still-image development into video generation without degrading temporal or identity consistency?

## Possible validation experiment

Before adding a permanent feature, use a small sequence and compare:

```text
A — prompt + ordinary references
B — prompt + ordinary references + textual visual bible
C — prompt + ordinary references + visual moodboard conditioning
```

Evaluate:

- visual consistency between shots;
- adherence to intended art direction;
- character/location identity preservation;
- prompt complexity;
- iteration count;
- generation cost;
- portability across providers;
- usefulness to a filmmaker during pre-production.

A Cine Toaster demo project could eventually serve as the validation case if the investigation advances.

## Architectural caution

Do not make a ComfyUI custom node the Cine Toaster abstraction.

The desired dependency direction, if the feature is adopted, is:

```text
Cine Toaster creative model
          ↓
Moodboard / Visual Style Reference
          ↓
provider capability / adapter
          ↓
ComfyUI node or other implementation
```

not:

```text
ComfyUI node
    ↓
Cine Toaster project model
```

This keeps Cine Toaster portable as models, providers, and conditioning techniques evolve.

## Next step

Later, perform a focused technical and workflow evaluation of:

- the two ComfyUI projects above;
- native moodboard/reference-style support in current image/video models;
- overlap with Cine Toaster's Visual Bible and reference architecture;
- UI implications;
- a minimal provider-agnostic project schema;
- an A/B/C validation experiment.

Only after that investigation should Moodboard be considered for the roadmap.
