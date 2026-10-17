---
id: CTX-PROJECT-STATUS
title: Project status
type: status
status: current
owner: project
created_at: 2026-09-20
updated_at: 2026-10-17
tags:
  - status
  - tracker
  - roadmap
---

# Project status

Last updated: 2026-10-17

## Current phase

The ordered plan (steps 1-13) is complete, and its work was closed out on
2026-10-03: 19 records closed, their loose ends gathered in one prioritised
backlog (`development/roadmap.md` § Backlog). Five records stay open on
purpose (CT-0020, CT-0028, CT-0041 future; CT-0052 paused by the user;
CT-0053 awaiting approval).

SINGULAR is migrated into ~/films/singular in Cine Toaster's own format
(CT-0054, ADR 0021): every scene assembles like SINGULAR's latest cut
(3-01 frame by frame against the approved v12), with its history (33
versions with the author's verdicts), cast, looks, locations and sounds.
Generation parity (CT-0055, a reference only), negative guidance (CT-0056),
the Producer status (CT-0057, `toast status`) and FinOps steps 2-3 (CT-0058)
are done, and so is the minimal continuity ledger (CT-0059, `toast
continuity`), meant for the remake of the sequence in Cine Toaster; one
face per person is now an error (CT-0060), and so is one voice per person
(CT-0062): SINGULAR's characters speak in generated voices with no recording
to hold them. FinOps steps 4-5 are done
(CT-0061, `toast finops`): of US$ 36.44 billed in 30 days, US$ 9.79 is
allocated to SINGULAR's job records. The effective LTX rate is US$ 1.92/h
against US$ 1.75/h assumed, so estimates run about 10% low. Stems for a DAW are done
(CT-0063, `toast assemble --stems`). On the way, a migration defect: 3-01's
"Claire?!" was not heard; it is fixed, and a missing line audio is now an
error. Waiting for the user: the
4K/finishing spike's cost, what feeds the 5.1, and
switching the working folder to ~/films/singular.

The demos line (2026-10-14): the reel is on the assembly path, a still is
a take, narration is written beside its scene in each line's voice
(CT-0065); footage is declared on a shot and fetched as its take with
source, licence and credit (CT-0066, `toast footage fetch`, `toast take
add`). Order agreed: the music-driven piece first, the reel after it and
out of it; nothing of the previous reel is kept. Next: music brought in
with its beats as a record.

The compositing engine (ADR 0022, `development/compositing-roadmap.md`): C1
and C2 are done, C2 closed only after the convergence audit the user asked
for (CT-0072): one GL pipeline (gl-transitions shaders are `opaque.gl`
nodes), one place for each decision (defaults, fitting to the frame,
showing a frame), cards and transition previews drawn by the graph, a still
as the graph at an instant (`toast still`), and the quick build (`toast
build`) removed. What still draws outside the graph has an owner step (C5,
C6, C10). C3 (animation) is done (CT-0074): eases are one vocabulary,
a beat's instant is kept apart from how a parameter reacts, and the music
piece's plume pulses on every beat. C4 (CT-0075) is done: layers are a record compiled into the graph, keys
and despill exist in both renderers, blends respect transparency, and the
ADO move, a replaced window and a keyed person are made on real footage.
The review of FilmCraft and EffectCraft is in `references.md` and the
roadmap (OTIO export to do; EffectCraft as an opaque renderer and an integer
time base to study). C5 (CT-0076) is done: the transition catalog is recipes of primitives,
filed by family, every one drawn by GL; two shaders stay with their reasons.
C6 (CT-0077) is done: transitions, effects, looks, stock elements and
titles all draw through one compositing engine, on GL; no FFmpeg filter chain
composites a picture; Blender stays a renderer whose clips the graph lays.
ADR 0022 separates what the graph supports from what the records expose.
The frame-access range rule is met: float sources keep their light above white
into the graph. C6b (CT-0078) is in progress: letters with their own time,
styles as recipes with a bevel, colour fonts, and Lottie read as a source by
ThorVG are done; the user's review of the chrome and colour fonts (the
ColorFonts look, not emoji; glints optional) is recorded to return to.
Then (the user's order): OpenFX into the shot's one graph (done), the time
base (CT-0079: three faults measured and fixed -- cut points on the frame
grid, rates as fractions, sound in samples, through one `timebase` module;
every click within half a sample over an hour at 30000/1001) and ADR 0023
(fractions to compute, ticks to store and exchange, the media clock's
contract for C9b). C7 is done (CT-0080): the remap's meaning, source and timeline
time composed (`clock`), retimed sound by policy (the anchored WSOLA),
retimes, offsets, trails and pins in the records, tracks as production
records (`tracks/<id>`), all on GL, and its three films. C8 opened
(CT-0081) with its audit; the C6b review stays in the backlog. Step 1:
signals as production records (ADR 0024). Step 2: a Blender scene's passes
rendered apart and recorded (`renders/passes/<id>`: picture, the camera at
every frame, Z depth and object index as signals), read by
`generate.render`; Blender 5's multipart EXR now read whole. Step 3: models
as adapters -- Depth Anything V2 Small, Video Depth Anything Small, SAM 2 --
in their own environment, fetched explicitly at pinned revisions, recorded
as estimated signals with their weights by hash, measured against Blender's
passes. Step 4: alignment over a stretch with its residuals (held out by
pixels, frames and a final stretch), unknown pixels apart from far,
inverted occlusions flagged per object pair and refused by `merge.depth`
until accepted; `merge.depth` also checks camera, quantity, unit and pixel
grid. Step 5: depth compositing at edges -- each layer's depth carried into
its coverage, three depth states kept, one depth per cut-out object; tests
split into `make test-fast` and `make test-heavy`. Step 6: the signal ops on
GL, conformant on llvmpipe and the Intel GPU. Step 7: depth and
segmentation declared in a shot's layers, compiled into the one graph. Step
8: the done-when film -- an orb rendered by Blender crossing behind Kael in
SINGULAR's generated corridor take (copied read-only), ordered by depth,
measured on the delivered file (`docs/trials.md`); making it found and
fixed records missing from composite identities. C8 closed on the user's
viewing (2026-10-15), and with it the exploratory phase of the compositing
roadmap: C9, C9b, C11, C10, C5b and the C6b review are now paths of
evolution taken when a production asks, not conditions for using the
engine. The compositing branch (`ct-0064-reel-on-the-assembly-path`, C1-C8
with the demos line's first points) was merged into `main` on 2026-10-15,
with `main`'s UX research; that research's records were renumbered
CT-0082..CT-0095 (their old ids were already the branch's). Next: the
demos, produced through the production flow -- each with an intention, a
screenplay, a storyboard -- the reel last, built from the others (the user,
2026-10-15), on a branch of their own.

Opened on 2026-10-13, at the user's request (CT-0064, `ready`): the Amiga
Demo Reel is to be rebuilt on the structure of NewTek's 1991 promotional
tape, as the two-act self-demo of `docs/production-validation.md`. Nothing
is built. The reel was rendered by `toast build` (removed in CT-0072), which drew text cards
only, while titles, effects, sound and transitions over moving video live
in the assembly; the record lists what is missing (the reel on the
assembly path, a matte and an overlay in the transition contract, layers
and a keyer, renderers for three declared composed engines) and the
order. It is its own line, not ordered by SINGULAR's milestones. A probe
on a copy of the reel showed the assembly already cuts catalog title
cards and recordings with transitions over moving video; it refuses a
still take, and `toast voice` has three defects.

Earlier: the first canonical production write is delivered. Cine Toaster is
no longer a read-only prototype: a human or an agent can compare registered
alternatives and commit a decision through one shared command.

## Product state

Cine Toaster can currently:

- open an external filesystem project;
- parse the project and per-scene operational manifests;
- build a disposable external SQLite index;
- expose project, scene, library, search, media, and transition queries;
- present a read-only Production Control Room in the browser;
- preview built-in and project transition assets;
- operate through the `toast` CLI;
- register concrete take alternatives per shot, with status, media, note, cost,
  and preserved provider provenance;
- commit a take selection through one shared command from Core, CLI, HTTP, or
  the browser, with revisions, typed errors, atomic writes, and a durable
  decision history;
- compare alternatives side by side in the browser and record why one was
  chosen;
- read scene geometry and report continuity problems before anything is
  generated (`toast check`);
- draw a plan-view blockout of the set, the cameras, and the line of action;
- link each scene to its screenplay scene and each shot to the lines it
  covers, so every storyboard frame shows its dialogue and action, and report
  uncovered, drifted, and unscripted lines (SPEC-0006, `toast script`);
- declare movement within a shot, meaning characters sent to marks and camera
  moves between poses, and check it before generating: positions carry across
  the cut, the move kind is derived, and axis crossings and screen-side jumps
  are reported (SPEC-0005);
- group scenes into sequences and report progress at the level a production
  actually reviews;
- follow committed decisions live, including decisions made from another
  terminal;
- record every assembled version of a scene with the takes it was built from,
  the author's verdict, and the reason, then roll selections back to any of
  them and list what differs between two cuts;
- read a production's own YAML breakdown directly, with no import step, and
  discover a shot's alternatives — including rejected ones and why — by reading
  the work directory;
- record what a production learns as data with dates, evidence, and a link to
  the check that enforces it, and report how much of it software actually
  enforces (`toast knowledge`, `toast why`);
- carry measured provider capability claims that a future generation adapter
  will read;
- list and instantiate two independently identified source fixtures: The Last
  Signal and Amiga Demo Reel; they are incomplete productions, not completed
  end-to-end demos;
- register multiple arbitrary external local projects simultaneously through an
  in-memory Project Manager;
- preserve manifest project identity across path changes and reject duplicate
  IDs opened from different locations;
- prevent `toast demo` from creating runtime productions inside the application
  source checkout unless an explicit fixture-development override is supplied;
- distinguish reusable Cine Toaster mechanisms from production-owned creative
  values and one-off tools, demonstrated by a working project-local transition
  in Amiga Demo Reel and the no-extension case in The Last Signal;
- preserve project files as the production authority.
- run a provider-independent Production Coordinator and Inception specialist
  inside the existing CoAgent, with retained creative drafts, readiness review
  and human-interaction-driven revision through shared application operations.

Cine Toaster cannot yet:

- persist the multi-project registry or expose project switching in the UI;
- persist fully scoped agent threads/provider session bindings or recover
  autonomous agent continuation after a runtime restart;

## Active work

CT-0115 (ADR 0034, 2026-10-17): agent review and structure. Roles are
declared (`agents/roles.py`) and the CoAgent state/reset derive from them;
every adapter declares capabilities and carries images (Claude CLI/API join
Codex); a model catalogue describes adapters and models and never picks one;
a person may bind a role to another model they supplied. No "RunPod agent":
generation recipes (data), a Generation Operations role with continuation on
job completion, and a development skill are the planned three layers. Format
intake (an interviewer that asks before advancing) is recorded as a gap.
Ordered follow-ups in `development/roadmap.md` § Agent Runtime structure.

CT-0112 addresses the hidden-pending-decision / approval-without-stage-output
gap (ADR 0032, SPEC-0018). A cross-workspace inbox derives current direction
requests and waiting scene/workflow gates. Explicit approval can atomically
adopt source-pinned development inputs for displayed existing scene/shot IDs.
The same CoAgent routes to Art Direction, which can publish registered image
references as retained storyboard candidates through the existing import command.
Generation still uses existing quota-confirmed jobs; no test approves Demo 01.
The first integrated 85-test regression passed; browser acceptance found and
fixed provisional-agent startup, then passed the complete approval-to-output
and new-gate path, reload/mobile and read-error feedback on a disposable film.
One announced graceful restart activated the same LAN server / `codex-cli`
after confirming no jobs. Demo 01's approval remains human-owned and pending.
Full regression passed: **1186 tests in 685.8 seconds**; the later explicit
continuation case also passed in the final focused run.
Director correction: the unit of work/human review is a **sequence**, not a
scene. The implementation above is a partial mechanism, not a validated
Inception -> storyboard transition. No production agent has reviewed Demo 01's
sequence-level adherence yet (zero real visual/continuity reviews). Next is an
independently reviewed sequence comparison package linking exact Inception
inputs, screenplay beats, ordered drawings and explicit gaps. Current pending
SC-010 P1-P3 development direction is not that sequence approval.
Canonical shot-manifest promotion, final storyboard approval, informal-question
capture and durable autonomous continuation remain open.

CT-0113 is active (SPEC-0019). Production-agent context now includes the shared
work/review contract and complete canonical sequence membership/order, with an
explicit `work_structure` read for Coordinator/Inception and the same context
in Directing/Continuity/Art and independent reviewer calls. This is runtime
product context, not repository memory, and does not infer readiness/approval.
External MCP agents receive the same startup contract and read-only
`read_work_structure` tool, as well as the updated filmmaking guide.
Singular's Genebra is 1-01..1-04 including 1-02A/B/C; Demo 01's The Ascent spans
seven scenes. The sequence comparison/package and independent adherence
validator/sequence-first GUI remain in progress, not delivered by this context
slice. No real-film gates or images were changed.
The context slice passed the complete **1199-test regression (653.9 seconds)**
and a separate ten-test MCP run; one announced graceful restart activated it
on the existing Demo LAN server / `codex-cli`, with LAN GUI HTTP 200. Actual
Singular sequence-room inspection confirmed Genebra's seven scenes / 202 shots.
Its preproduction startup exceeded 120 s during concurrent heavy tests; do not
claim the full Singular GUI walkthrough passed. Investigate this read/startup
cost separately from the remaining sequence review package.

CT-0111 reuses the existing Production Coordinator for Directing/Shot Planning
and Script Supervisor/Continuity (ADR 0031, SPEC-0017), not another Producer or
orchestration mechanism. Shared Core/HTTP operations retain versioned proposals
and independent source-labelled reports in Creation. The existing canonical
continuity ledger and geometry/coverage findings are reused. Proposal checks
remain distinct from canonical findings; text does not establish pixel or
numeric-camera validation. Preproduction displays versions/evidence and the
scoped human direction gate. Human changes resume the same CoAgent, preserving
prior proposals/reports. Canonical shot promotion and image generation from
these proposals remain unimplemented; approval does not claim either.

The first 60-test agent regression and expanded 23 directing tests passed;
real public CoAgents/HTTP/browser acceptance demonstrated a human changes
handoff, retained second version, reload/mobile and no manual authoring forms.
All five frontend test files and builds passed. The complete regression passed
**1172 tests in 583.3 seconds**, including heavy adapters. The Art browser
regression and read-only live LAN preproduction walkthrough also passed.
One announced graceful server restart activated the graph with the same
`codex-cli` adapter and LAN address, after confirming no jobs. LAN GUI HTTP
returned 200. Demo 01 remains revision 6 with its original source digest and
no test proposals/reports, generations or decisions. Real-film creative review
remains open, rather than filling the user's production with test material.

CT-0110 adds Art Direction and independent visual prevalidation to the existing
CoAgent (ADR 0030, SPEC-0016): versioned briefs, actual bounded raster attachments,
criterion evidence, stale-review/human-request checks and generation through
existing jobs after per-plan quota consent. The Creation GUI shows the records
without authoring forms. The reviewer uses a fresh role/context with the same
model; it cannot approve a gate. Codex CLI implements image input; unsupported
adapters report the gap through doctor/runtime. Bounded job waits do not add
durable auto-resume. Nineteen art tests, a 109-test focused regression and real
CoAgents browser/mobile acceptance passed. A live Codex model identified a red
circle from a synthetic raster input, not a production image. The server now
hosts the new graph on the same LAN URL; the old listener was absent when checked,
so no running instance was killed. Demo 01 revision/source digest are unchanged.
The early full run (1144 tests) had one synthetic-fixture provenance failure;
that fixture is corrected. The final full regression passed **1149 tests in
598.4 seconds**, including all 19 art cases and heavy adapters. Frontend tests,
build and existing Inception GUI continuation passed. Director review of actual
artistic quality remains open; no Demo 01 creative decision/generation was made.

The director requested an Inception role plus whole-film Production Coordinator
in the existing Agent Runtime ([CT-0108](work/CT-0108-provider-independent-inception-runtime.md)).
First correction: provider selection uses `--agent-provider`, then
`CINE_TOASTER_MODEL`, then the current CLI (Codex / Claude) when unambiguous,
with no implicit Claude CLI default. A Codex CLI model adapter is included;
finding a CLI does not verify authentication/inference. The current adapters
do not attach to an open provider conversation; SPEC-0001
thread/session binding remains planned.

The Coordinator and first Inception specialist are now implemented inside the
same public LangGraph `assistant` CoAgent (ADR 0029, SPEC-0015). Routing uses
whole-film context; blank/title-only films enter Inception without forcing
imported screenplays through another gate. Inception can append real concepts,
concept-linked screenplay drafts and readiness assessments via shared commands,
with revision/material preconditions and no human approval/image-generation
tools. GUI writes refresh canonical records, and a human direction can initiate
another turn through the same CoAgent, rechecking the saved decision. This is
interactive coordination, not a new queue or durable background dispatcher.
CT-0110 adds Art Direction / visual prevalidation, and CT-0111 adds the first
Directing / Continuity proposal-review slice. External reference research,
other stage executors and durable autonomous resume remain unimplemented.

Twenty-three specialist tests and the final 97-test focused regression passed;
real CoAgents browser acceptance proved saved work -> human changes -> retained
revision -> new review on a disposable film. A live Codex CLI smoke test returned
an Inception question grounded in that disposable film, without writing it.
The full regression passed (1117 tests, 617.6 s), including the earlier
storyboard-reopening test; its previous intermittent failure is not considered
independently explained. Four final agent edge cases and LAN-onboarding coverage
were added later and passed the final focused run. Demo 01 is reloaded with the
new graph and `codex-cli`; real-film inspection confirmed its material unchanged.

LAN onboarding ([CT-0109](work/CT-0109-lan-gui-onboarding.md)) now guides agents
to use an intentional trusted-LAN bind and report a real LAN URL. The CLI default
stays loopback. LAN launches now discover real URLs and inspect Windows/WSL
forwarding/listeners without changing OS rules. The director authorised TCP 8787
forwarding and a Windows Private/Wi-Fi/LocalSubnet firewall rule for Demo 01.
The Windows LAN URL `http://192.168.100.179:8787/app/creation.html` and assistant
info respond HTTP 200, and the director confirmed actual phone access. The
persistent host-specific rules may need an update after DHCP/WSL address changes.
LAN follow-up validation: 43 focused tests passed. The full 1129-test run reported
one jobs retry-test temporary-directory cleanup error; all 20 jobs tests passed
in isolation. That cleanup race remains unexplained, not fixed by LAN work.

Priority clarification from the director:
[CT-0107](work/CT-0107-agent-led-work-and-human-review-loop.md). The GUI is
human situational awareness; authorised active work must progress through the
agent or present a concrete human request over a complete scoped delivery.
The director narrowed the first implementation to readiness and a simple
direction decision. This is now implemented in the existing Creation journal:
agent assessment per destination, pinned material, scoped recommendation,
Approve / Request changes with guidance, and retained human decisions through
shared Core/CLI/HTTP operations. MCP can author assessments, not approve them
(ADR 0028). Demo 01 now has a real pending assessment at Creation revision 6:
enough material for screenplay/storyboard development; masters need identity
and composition work. No human decision or generation was performed. Focused
tests/browser acceptance and the full 1079-test regression passed. Automatic
dispatch/continuation remains unimplemented: the next instruction is recorded
as not dispatched. Do not claim the full autonomous workflow is delivered.
Continuation must reuse the existing LangGraph Agent Runtime/CoAgents, extending
missing specialists there instead of creating a parallel execution mechanism.
The repo registers one public `assistant` CoAgent; CT-0108 adds its internal
Coordinator/Inception loop. The wider specialist workforce and persistent
background continuation remain planned in the production-agent documentation.

The director authorised the next slice (2026-10-16):
[CT-0106](work/CT-0106-storyboard-candidates-and-inception-inputs.md), actual
storyboard image candidates beside the screenplay, with versioned Inception
inputs. Wake's three drafts are now retained with exact input hashes/prompts
and displayed beside the screenplay, with ordered thumbnails, prior-version
navigation and two-way Inception links. Core/CLI/HTTP/MCP use shared operations
(ADR 0027, SPEC-0014); bounded reads inform the assistant. The other 21 shots
stay explicitly incomplete. No face choice, blockout or approval was imposed
or inferred. Following the director's clarification, manual Inception forms and
input-editing controls are removed: the GUI is situational for the human,
while agents use shared operations. The normal Control Room Storyboard now
shows the same draft images, with links to their screenplay view. No additional
21-shot generation was started; the director only needs a clearly located
populated example. Targeted tests, disposable/real-film browser checks and the full
1068-test regression passed; director usability review remains open.
The server is available at `127.0.0.1:8787` with the assistant enabled.

Director refinement for the GUI follow-up: theme-oriented concepts, evolve /
reject without deletion, and evidence-based readiness separately for starting
screenplay and storyboard work. Explain story drawings -> 3D composition ->
shot masters and the role of stills without conflating cast references, image
formats and creative approvals. Requirements are recorded in CT-0105; these
concept actions and the full downstream handoff are not delivered; readiness
and direction decisions now have the CT-0107 first slice described above.

Latest director feedback, recorded for a later GUI iteration (2026-10-16;
[CT-0105](work/CT-0105-creation-inception-and-stage-inputs.md), "Latest director
feedback"): prioritize copilot-led interaction, with manual authoring forms
secondary, and a film-wide "Awaiting your decision" inbox accessible from every
module. Lia's identity-reference choice is the first concrete example; the
current Review room covers take review, not this unified queue. Show the
question, evidence/candidates and affected work; distinguish actionable human
requests from warnings or unfinished preparation. Mark-for-deletion is distinct
from actual deletion and must preserve history. These are recorded next steps,
not implemented capabilities; resume when the director requests advancement.

New GUI direction (2026-10-16):
[CT-0105](work/CT-0105-creation-inception-and-stage-inputs.md) adds Creation /
Inception before Screenplay & Storyboard. It supports idea exploration and
draft references whose selected versions can guide later work, with traceable
inputs and preserved alternatives. The design and Demo 01 acceptance journey
are recorded. The first slice is implemented at `/app/creation.html`: immutable
concept/screenplay candidates, selected input hashes, reference comparison,
contextual assistant and quota-consented exploratory reference jobs staged for
explicit non-overwriting adoption. Core/HTTP/CLI/MCP share the operations
(ADR 0026, SPEC-0013). Director feedback exposed the flat gallery's loss of
creative history. The director then requested a simpler primary gallery:
images grouped by freely named rounds, not a fixed stage taxonomy. History,
actual inputs, cast designations, use and corrections are collapsed details.
Demo 01 has Storyboard reference / Eras / Age control groups, retaining all 13
images and prior round-record versions without inferred approvals. The
first-slice full suite passed (1056 tests); the expanded full run caught a test
scoping error, fixed and followed by a green 1018-test fast run. The final
round-grouping slice passed its 14 Core/interface tests, frontend build/tests
and disposable browser acceptance; see CT-0105 for exact validation evidence.
Canonical screenplay promotion, candidate-specific storyboard authoring and
director usability validation remain open. This extends the earlier
three-workspace hypothesis; the embedded assistant's proposed text is inserted
manually, not silently saved.

Current process finding (2026-10-16): [CT-0103](work/CT-0103-demo-01-process-and-gui-incident.md)
documents Demo 01's premature advance from textual shot breakdown to blockout,
the GUI storyboard discovery gap and the assistant omitted at server launch.
The next demo action is to validate the screenplay/storyboard path in the GUI
and complete the missing visual review before expanding the blockout. The
record contains an acceptance scenario; the incident remains unresolved.

GUI follow-up: [CT-0104](work/CT-0104-demo-driven-gui-flow.md) now has a read-only
React pilot at `/app/preproduction.html`, linked from the Control Room. Actual
screenplay and proposed shots appear together, with distinct composition
studies, visible assistant availability and scene approval state. Browser
navigation, mobile layout and the enabled chat's context delivery were exercised
against Demo 01, without a model message. Visual-candidate
authoring/versioning and human usability validation remain open; existing UI
routes and production records are preserved. Build, frontend tests and the
full 1,044-test Python suite passed; the final doctor build-detection change
also passed its nine-test module separately.

Open records, by what they wait for (2026-10-15; every other record is
`done`, `ai-context/work/README.md`):

- **Doing, first complete demo**: the evolution of animation (`CT-0099`,
  `~/films/demo-01`), replacing the hybrid scene (`CT-0097`, paused). The
  `codex-image` adapter, cast sheet and seven era records are done. The first
  identity pass is generated: costume, hair and movement hold, but one
  eight-year-old parent picture prevented a valid test of ageing through eras
  1--6. A controlled 14/16/18 pass without that child picture now gives a clear
  age progression and preserves every first-pass image as history; facial
  identity across techniques still awaits the director's master-face choice.
  The film now has its canonical seven-scene screenplay and a 103-second,
  24-shot linked breakdown in one sequence. The opening scene has measured
  cameras and paths, six clay boards and a 12-second animatic. Its review
  exposed absent pose and flight-elevation support, insufficient landscape
  landmarks and a project-look inheritance mismatch in the brief. Next:
  validate the GUI/process findings in CT-0103, complete the visual storyboard
  and preserve the initial render pass before further spatial refinement;
  the transformation trial remains open. No storyboard is approved yet.
  The checked-in The Last Signal and Amiga productions are regression/source
  fixtures at the same portfolio level, not completed predecessors or the bar
  by which this film is called done.
- **Next, by the user's word**: the demos, produced through the production
  flow -- an intention, a screenplay, a storyboard -- the reel last, made
  from the others (`CT-0064`, `ready`; D8 and D9 of the roadmap). Each demo
  by a different approach (2026-10-16, the roadmap's "demo set"): The Last
  Signal narrative, the music piece an advertisement, the animated short a
  cartoon, the hybrid scene footage with ray-traced CG, the reel last with a
  ray-traced Juggler homage of its own. Order: the hybrid scene, The Last
  Signal, the advertisement, the cartoon, the reel. First: the hybrid
  scene's intention and screenplay, with the user. Open: how the cartoon is
  made, the generation budget.
- **Doing**: starting a film and onboarding a production agent (`CT-0098`):
  `toast new` (empty or from a screenplay, one linked breakdown per scene),
  `docs/making-a-film.md` (the two phases, the commands, what is the
  director's), and the guide and practices as MCP reads. Left: the film's
  own pointer for an agent opened in its folder, and the tools the MCP
  surface still lacks.
- **Awaiting the user's review**: SINGULAR's migration (`CT-0054`); the UX
  research made on `main` -- production information priorities, production
  awareness, cognitive ergonomics, creative context, compound locations,
  model-dependent mood, the Visual Lab (`CT-0087`..`CT-0095`).
- **Ready, not started**: Blender MCP (`CT-0082`), integrated editing
  (`CT-0083`), the three-workspace UX vision, wireframe and information
  visibility (`CT-0084`..`CT-0086`), surfaces from Blender (`CT-0073`, C5b),
  the interface reference and transition graph (`CT-0020`), Video Toaster
  transitions (`CT-0028`), learning from gate decisions (`CT-0041`), the 4K
  upscaling spike, its cost to approve (`CT-0053`).
- **Blocked**: spatial sound beyond 5.1, on what feeds the system
  (`CT-0052`).

## Closed: scene import

There is no import step. Cine Toaster reads the production's own YAML where it
lies, and takes are discovered from the work directory rather than declared
(ADR 0010). The exporter, the generated scene files and the staleness check they
required are all deleted.

## Delivered

- `CT-0026` — gl-transitions submodule: 117 unreviewed shaders plus 6 reviewed;
  GLSL transitions run through ModernGL, now as `opaque.gl` nodes of the GL
  renderer (CT-0072) (`done`).
- `CT-0013` — production-specific tooling boundary and demo examples (`done`).
- `CT-0002` — canonical take selection (`done`).
- `CT-0008` — scene geometry, continuity checks, sequences, live board (`done`).
- `CT-0009` — knowledge layer and the eyeline direction check (`done`).
- `CT-0010` — closed decision loop, assembly versions, staleness (`done`).
- `CT-0011` — one native format, read the production's YAML directly (`done`).
- `CT-0012` — generation providers moved into the tool (`done`).

## The ordered plan of 2026-09-29 (complete)

Follow the **ordered plan** in `development/roadmap.md` (2026-09-29):

1. screenplay coverage (SPEC-0006);
2. cut record;
3. blocking frame;
4. brief builder and SceneFlow export;
5. FDX interchange;
6. jobs runtime;
7. React stack decision and read-only canvas;
8. screenplay editor (ADR 0006 amendment);
9. generation unit decision and first generation adapter;
10. built-in workflow with a gate;
11. LangGraph spike;
12. CopilotKit/CoAgents spike;
13. editable canvas;
14. ~~Tauri~~ (cancelled, ADR 0019).

Steps 1–4 are **done**: screenplay coverage (SPEC-0006), the cut record
(SPEC-0007), the blocking frame (`CT-0025`), and the brief builder with a
local-video review (`docs/brief.md`). Step 4b, light previs (`CT-0029`), is
done too, and so is step 5, Final Draft interchange (ADR 0014: import to a new
Fountain file with a loss report, export a derived `.fdx`). The next action is
step 6, the jobs runtime, which is now done too (SPEC-0008: durable store,
previs and build as jobs, cancel, reconcile, retry, adopt, jobs tray). Step 7
is done: React 19 + Vite + React Flow (ADR 0015), with a read-only production
canvas at `/canvas/`. Step 8 is done: the screenplay editor (ADR 0016, amending ADR 0006) at
`/app/script.html`. SINGULAR was validated read-only (CT-0035), and several
fixes and a SPEC-0007 amendment (continuation) came from it. The flow is framed in two phases (`production-flow.md`): fitting the
screenplay and storyboard, then producing what was defined, with versions.
Scene assembly from the chosen takes now makes kept versions (CT-0038). Generation blocks and content-based slicing into takes are done (CT-0037);
they match SINGULAR's own slicing on all six blocks. The working order is in CT-0039. Speech-aware trims and loudness, job lineage
and cost, LTX rules as knowledge, and sequence versions are done. What
remains:

- SINGULAR's direction and production decisions are recorded in its own
  `docs/SINGULAR-CINE-TOASTER.md`, to take up when the user returns to it;
- the generation adapter is done, with a US$ 2 ceiling the user approved
  (`toast budget`, `toast generate`, versions `b<id>-<n>`; CT-0037). The control room
  starts one after showing the estimate. The voice spike is done too:
  `toast revoice` converts a take's speech to the cast member's recording, the
  room kept, as a new take, with each speaker of a multi-speaker take in their
  own voice (lines aligned to word timings, no diarization; CT-0040), or, as a
  decision on the shot, converted in the cut when the scene is assembled. Master pictures by
  `derive` (render + cast faces, `toast picture`) close step 9. Step 10 is done too:
  the built-in workflow stops at "approve the master picture" (SPEC-0009,
  CT-0042; `toast workflow`, the scene room's Workflow panel, a card on the
  canvas); refusals must say what is wrong. Step 11 is done (ADR 0017,
  CT-0043): production workflows stay built in; LangGraph runs the agents as an
  optional extra; a LangGraph CoAgent with CopilotKit knew what the page showed,
  shared state, and asked before starting a workflow; the model ran through the
  Claude Code CLI with no API key. Step 12 is done too (ADR 0018,
  CT-0044): `toast serve --assistant` puts a directing assistant beside the
  canvas (CopilotKit v2 → bundled Copilot Runtime sidecar → LangGraph agent over
  AG-UI → Claude Code CLI); it knows what is on screen, points at shots, and acts
  only through commands after a yes, never on a gate. Step 13 is done too
  (CT-0046): the canvas edits cuts (a decision over the breakdown, never a
  rewrite) and starts workflows, through the same commands. Step 14 (Tauri) was
  cancelled by the user (ADR 0019): the plan ends at 13. The hardening items
  after it are done (2026-09-30): references edited on the canvas and cut
  sets taken whole (CT-0046); a cross-interface conflict test, which found
  lost decisions and led to `state.scene_lock` (ADR 0006 amendment); set
  pieces and object subjects in the blocking frame with a `subject_hidden`
  check (CT-0025); master pictures from a location's plate, and a
  Locations room (SPEC-0010, CT-0030); camera-move previews (CT-0027).
  Aerial camera moves and outdoor plans followed (CT-0027). Catalogs of
  titles (CT-0031: FFmpeg and Blender) and visual effects (CT-0031/0047:
  FFmpeg, stock elements in every delivery form, OpenEXR through
  OpenColorIO, Blender-made effects and projects, OpenVDB, OpenUSD in and
  out, OpenFX through Natron, Gaussian splats through Spark) are in place,
  each form with a working example; Unreal/Unity and NeRF are studied in
  CT-0047. Sound and music are on the cut (CT-0048, 2026-10-03): a sound
  catalog (26 generated items from SINGULAR's practice), shot sounds,
  scene ambience and music levelled and ducked under speech, and three
  sources -- Freesound (CC0), Sonniss (provisional mirror), Openverse
  (music) -- plus SINGULAR's library registered in place; an emotion catalog
  (describe, ask a model, express as FACS/ARKit) reaches the prompt and
  the brief (CT-0048). A style catalog -- direction, animation techniques
  and formats such as viral vertical or commercial -- is named by the
  production or a scene and reaches the prompts, the brief and the checks
  (CT-0049); a format reframes and captions the cut, and a version can be
  delivered in several formats at once (`deliver:`). Versions can carry a
  5.1 track beside the stereo (`surround: "5.1"`, CT-0052 phase 1). A scene's version now renders its joins:
  catalog transitions (shader or FFmpeg stand-in) and J/L-cuts from the
  takes' handles (CT-0050). Scenes declare how they are entered (`enter`), and
  the sequence assembly renders it, with music and ambience over several
  scenes, ducked under every scene's speech (CT-0051). Unreal/Unity render adapters, a catalog of directors and
  styles, and 3D storyboards (ScreenWeaver as reference) too (CT-0049). Claude Code now
  works on a film through an MCP server of Cine Toaster (ADR 0020, CT-0045
  option 1: `toast mcp`). Noted for later, not started: RL beyond the
  refusal reasons (CT-0041), CT-0045 options 2 and 3, Video Toaster
  transitions (CT-0028), VFX and titles (CT-0031). The author will re-check
  later whether Kael's converted voice still sounds ill.

Earlier notes:

- Phase 2 — application runtime and jobs. The first job should be the one the
  external production already needs: assemble a sequence from its selected takes
  with FFmpeg, with progress and cancellation.
- A generation adapter reading `[[geometry.cameras]]` as camera intent, so a
  shot can be regenerated from the project rather than from a script.

The recommended next implementation is `select_take`, not a frontend rewrite or
agent integration. It establishes the mutation boundary that those interfaces
will later consume.

## The first records (2026-09-20)

- `CT-0007` — added Git ignore conventions and CLI protection against accidental
  in-repository runtime projects.
- `CT-0006` — added external local project locators, materialized workspaces, an
  in-memory Project Manager, identity conflicts, and the remote-source contract.
- `CT-0005` — added Amiga Demo Reel, selectable demo templates, stable indexed
  manifest identity, packaging coverage, and multi-project fixtures.
- `CT-0004` — accepted the scoped agent-thread and provider-session contract.
- `CT-0003` — standardized frontmatter across the development memory/tracker.
- `CT-0001` — architecture, tracker, decision records, and development guidance.
- Read-only Production Control Room.
- External filesystem projects and disposable search index.
- Transition library with GLSL and WebM preview support.
- Baseline architecture review against the proposed desktop and agent direction.

## Principal risks

- allowing GUI, CLI, and agents to develop separate write paths;
- moving long-lived runtime state into a renderer process;
- confusing project-scoped state with state stored inside the project folder;
- adopting CopilotKit, an orchestrator, or a media UI library before its boundary
  is proven by a spike;
- losing generation reproducibility by discarding provider provenance;
- hiding one film's creative values inside application defaults;
- claiming frame accuracy before measuring it.

## Validation baseline

On 2026-10-16 the whole suite passed 1018 tests (40 of them heavy: Blender,
models, voice) in 8.2 minutes with `make test`, its modules in parallel
(`tests/run.py`); `make test-fast` runs the other 978 in 2.4 minutes
(`development/testing.md`, CT-0096).

A fresh clone sets up, tests and builds (`scripts/fresh_clone_check.sh`), and a
kept version can carry its cut as OpenTimelineIO (`toast assemble --otio`,
`docs/otio.md`), and SAM 2's segmentation keeps each object's soft matte
for a layer's `cut` (`soft: true`), CT-0096.

Earlier, on 2026-09-20, the repository test suite passed 141 tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The source distribution and wheel build successfully. The isolated installed
wheel can instantiate both demo templates and register both simultaneously in
the Project Manager. `git diff --check` also passed.
