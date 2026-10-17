---
id: SPEC-0014
title: Retained storyboard drawings and pinned creative inputs
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-10-16
updated_at: 2026-10-16
---

# Contract

ADR 0027 separates a storyboard drawing candidate from discovered stills, cast
master references, a finished shot master and the scene's human storyboard gate.
An existing canonical shot can receive drawings without geometry, a blockout,
a fixed face or an approval. This contract does not promote screenplay drafts.

The production owns `storyboard/state.json` (schema 1, project identity, journal
revision and append-only candidates) and `storyboard/images/<id>.<extension>`.
Each candidate records stable identity, scene/shot, title, per-shot version,
optional same-shot predecessor, actor/time, note, owned image path and SHA-256,
relevant story-context fingerprint/snapshot, selected reference snapshots and
generation provenance when known. Declared creative direction is distinct from
actual provider inputs. Missing historic provenance is not invented.

Import requires the expected journal revision. It validates a real scene/shot,
predecessor, reference IDs, bounded JSON provenance and a bounded PNG/JPEG/WebP
source with a matching signature. This is format filtering, not full image
decoding. It creates a unique owned image and atomically replaces the journal
under the production lock. Failure retains the previous journal and images;
concurrent stale writers receive the shared revision-conflict error. A corrupt
journal is an error, not an empty production. Project-owned paths cannot escape
through traversal or symlinks. CLI may explicitly import a local source file;
HTTP/MCP are restricted to existing sources inside the addressed production.

Shared reads report missing/changed image bytes, changed shot/story context and
changed/missing reference inputs without replacing recorded versions. Coverage
counts shots with a recorded candidate, not available images or approvals.
The GUI defaults to the latest preview, allows exact older-version URLs and
reports an invalid explicit version instead of substituting silently. Inception
and storyboard expose known reference uses in both directions. The assistant
can read the same records. No import rewrites screenplay, scene manifests,
cast masters, gates or the discovered-still directory.

# Acceptance and remaining scope

Core/interface tests cover preservation, conflicts, failed commits, invalid
inputs, path boundaries, corruption and drift. Browser acceptance covers
version selection/reload/back, input/use trace, separate 3D studies, missing
drawings versus read errors, and narrow-screen layout. Inspect real films
read-only; test writes on disposable productions without model calls.

The full creative workflow remains partial: no candidate verdict/selection,
shot-master publication or automated storyboard -> 3D -> master conversion is
implemented here. A user may inspect and discuss drawings; only an explicit
human production decision approves the scene. Concept themes/evolve/reject,
destination-specific readiness and a unified decision inbox remain CT-0105.
