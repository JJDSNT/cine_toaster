# CT-0073 — Creative context Core inventory and UX contract

Status: investigation, not implementation approval. 2026-10-08.

## Why

CT-0072 established that the left sidebar groups features but does not expose how film-wide decisions apply locally. This audit checks actual Core modules before specifying UI.

## Verified source-to-context matrix

| Domain | Authoritative Core evidence | Scope/resolution | UX affordance | Caveat |
| --- | --- | --- | --- | --- |
| Cast | `src/cine_toaster/cast.py`: `Member`, `Reference`, `Voice`, `load_cast`, `check_cast` | Character identity and variants are declared centrally; scene-specific voice state and line delivery are separate | Show character, active variant, authoritative identity and references | Do not assume the active variant can always be inferred from shot data without checking actual scene bindings |
| Look | `src/cine_toaster/looks.py::resolve` | Explicit priority: shot → scene → sequence → project; returns (effective value, deciding level) | Display **effective look** and **defined at** | A resolved value is not proof that a generated take faithfully depicts it |
| Style | `src/cine_toaster/styles.py::resolve`, `summary`, `departures` | Separate technique/direction/format axes; scene overrides project per axis; provenance returned | Show axis-by-axis source and deliberate local departure | No generic inheritance mechanism for every creative entity |
| Location | `src/cine_toaster/locations.py::resolve`, `load_locations`, `status`; `docs/locations.md` | Shared set plus scene geography, local camera/mark overrides; pinned backlot provenance | Show effective set, local modifications, reuse links | Geometry override and reference freshness are distinct |
| Performance emotion | `docs/emotions.md` | Character/shot-specific emotion, intensity, arc, reason | Show performance direction only when relevant | Not equivalent to visual mood or observed acting |
| Continuity | `src/cine_toaster/continuity.py::ledger`, `state_at` | Declared subject/attribute states, transitions and provenance across scenes/shots | Show known state, origin and warning/advice distinctions | Inferred continuity is not a confirmed creative choice |
| Editorial cuts | `src/cine_toaster/cuts.py::scene_cuts`, `frontend/src/CutEditor.tsx` | Shot transitions and continuity checks; revision-checked editing commands | Show cut rationale and affected shot pair | Does not alone prove a full take-to-assembly impact graph |
| Visual moodboard | `docs/research/moodboard-visual-style-investigation.md` | Future investigation only | Potential film/scene reference grouping | Do not present as an implemented field or resolved value |
| Navigation | `src/cine_toaster/web_assets/index.html` | Fixed left menu grouped Writing, Production, Reference | Global destinations remain discoverable | Menu does not itself display applicability/provenance |

## Data contract to investigate, not implement blindly

A **read-only Creative Context projection** could expose domain-specific entries with:

- `object_ref`: stable film / sequence / scene / shot identifier
- `domain`: cast, look, style-axis, location, performance, continuity, editorial, etc.
- `effective_value`: resolved by the domain's existing Core logic, not UI reimplementation
- `origin_ref` and `origin_level`: source file/object and level where known
- `scope`: exactly which objects are covered by this declaration
- `local_override`: actual declaration/override, not merely visual difference
- `evidence_kind`: declared / resolved / observed / inferred / unknown
- `dependent_refs`: only explicitly traced consumers, never hypothetical impact claims
- `available_actions`: links to current supported commands, with permission and revision handling

**These fields are a candidate presentation contract, not a new persisted schema.** Different domains may not supply every field; absence should be represented as unknown.

## Navigation prototype hypotheses

A. Existing feature sidebar with contextual inspector; minimal disruption but important relations may be buried.

D. Compact workspace switcher plus film/scene/shot explorer; a contextual section shows only applicable creative decisions with provenance and optional 'where used'. Keep a search/command palette for rarely used tools. No permanent relationship graph or mandatory fourth pane.

Use the same Singular example: Kael leaving the hospital in Geneva. On scene selection show Kael's relevant character/variant, Geneva location and local overrides, effective style axes and look, scene continuity, and linked boards; on shot selection reveal camera/reference/performance/takes and editorial uses when traceable. Treat sample data as illustrative until project records are loaded.

## Acceptance questions

1. Can a director explain which global decisions govern the current scene, and identify exceptions?
2. Can a writer change scene intent without having to inspect irrelevant provider settings?
3. Can a producer tell declared creative constraints apart from actual render outputs?
4. Can an editor trace the currently used take back to the scene and intended reference?
5. Can the user navigate to a global asset and back without losing scene/shot focus?
6. Does the UI distinguish intentional departure, possible continuity issue, and unknown relationship?

## Remaining implementation audits

- [ ] Trace exact API payloads and client navigation for cast/location/style/look context.
- [ ] Verify sequence and shot binding semantics in project normalization.
- [ ] Trace full take/version/assembly reference graph and persistence of cross-room selection.
- [ ] Identify which rationale fields are author-owned and which are computed.
- [ ] Prototype A vs D and test visual density, navigation errors and interruption recovery.
- [ ] Review existing APIs before proposing any new endpoint; write ADR only for validated gaps.

Related: CT-0066–CT-0072. No UI changes authorized by this document.
