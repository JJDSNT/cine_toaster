---
id: CT-0105
title: Creation / Inception -- developing ideas and carrying versioned inputs through the film
type: work
status: review
owner: codex
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - creation
  - inception
  - gui
  - production-flow
  - references
  - provenance
---

# What

The director requested an additional module before Screenplay & Storyboard:
**Creation / Inception**, a place for brainstorming ideas and generating rough
visual references. Work produced at one stage must be usable as input to the
next. This record specifies the module's purpose, first interaction design,
handoff semantics and validation slice. The first implementation now adds a
project-owned candidate journal, shared operations and a React Creation GUI.

# Why

Demo 01 began with an idea and an eleven-panel concept board. Identity and era
trials followed; the screenplay was written later. The GUI has no coherent
place to inspect that creative development or choose which results guide the
next stage. Starting the navigation at the screenplay hides real work and makes
its references difficult to carry forward. This complements CT-0103's incident
and extends the first GUI pilot in CT-0104.

# User direction

- Creation / Inception precedes Screenplay & Storyboard in the navigation.
- It supports brainstorming and draft reference generation, with human or AI
  participation.
- Outputs can become inputs to later stages, preserving their identities and
  versions instead of being manually pasted or silently copied.
- The existing preservation rule applies: keep alternatives, earlier outputs,
  prompts and reasons when the direction changes.

## Latest director feedback — recorded for the next iteration

The director wants to review the GUI more calmly before further implementation.
The following direction is recorded, not delivered functionality:

- **Copilot-first interaction.** Brainstorming, requesting another pass and
  developing a candidate should primarily happen through the copilot. The GUI
  presents artifacts, round groups, comparisons and decisions. Manual authoring
  forms are secondary/advanced, not the main workflow. The director explicitly
  finds the current forms of little use beyond direct marking for deletion.
- **One human-decision inbox across the film.** The director needs to know
  everything awaiting their choice, accessible from any module; it need not
  live in Creation. Each item should explain the question, context, candidates,
  copilot recommendation when present, affected work and next action. Support
  choosing, requesting another round or deferring, through shared operations.
  Decisions and outcomes must survive chat/session loss and reload.
- **Inventory before implementation.** The existing Review room filters scenes
  and shots by review status and offers take comparison. It is not the unified
  queue above. Reuse existing gates, selections and scene questions; distinguish
  an actionable human request from a technical warning or work not ready for
  approval. Do not make every missing output a request for the director.
- **Demo 01 acceptance example.** "Define Lia's visual identity references"
  should be discoverable as an open decision with relevant Eras/Age control
  candidates and the missing cast designation as evidence. Currently Cast only
  says "No master picture"; Creation holds the images, but neither connects
  them into an actionable request. Clarify age/style-specific identity instead
  of prescribing one unchanged face across every age; approval stays human.
- **Marking is not deleting.** A direct mark-for-deletion/discard action is a
  useful GUI exception to conversational authoring. It must be separate from
  physical deletion, retain history and respect the director's preservation
  principle. No deletion feature or permission to delete was implemented or
  inferred from this feedback.
- **Rounds remain generic.** Freely named, filmmaker-defined groups are the
  organizing unit. Storyboard reference / Eras / Age control describe only
  this demo's actual history, not a fixed template for other productions.

No code, production records, creative approvals or images are changed by this
follow-up note. Resume from this direction when the director asks to advance.

## Director refinement — concepts and destination-specific readiness

While authorising the storyboard slice, the director clarified the next GUI
iteration: make concepts the primary objects, potentially addressing different
themes, rather than adding more Inception forms. Keep freely named exploration
rounds within that creative history; do not confuse a theme with a revision or
force existing references into invented historical concept records.

- Present each concept's intention, retained alternatives and known downstream
  uses, with **evolve**, **reject** and **develop toward…** actions. Rejection is
  a recorded creative verdict, not file deletion, and is distinct from marking
  an artifact for eventual deletion. Preserve rejected material and rationale.
- Explain readiness separately for **starting a screenplay draft** and
  **starting storyboard development**: available inputs, actual missing context,
  unresolved choices and a suggested next action. Neither image count nor form
  completion proves creative sufficiency. A copilot assessment is advice with
  evidence, not a human approval or a new mandatory gate.
- Permit partial progress: one concept or scene can be developed while another
  remains exploratory. Identity/style choices required for a finished image do
  not necessarily prevent an exploratory screenplay or story drawing.
- Make the later journey understandable from the same shot: story drawing,
  3D composition/animatic, shot master image and downstream stills/video. Show
  which versions informed or actually produced each result and what still
  needs review; do not imply that changing a label converts one into another.
  A cast master reference and a shot master image have different roles. A still
  is an image/frame, not by itself another approval or compulsory workflow step.

These are recorded requirements, not implemented actions or readiness checks.
Keep CT-0106 focused on the connected Inception/storyboard review slice; expose
its distinction between drafts and composition studies without claiming the
complete storyboard-to-master handoff is delivered.

# Module responsibilities

| Activity | What the filmmaker needs | Candidate output |
| --- | --- | --- |
| Explore the idea | Premise, intention, possibilities and open questions | An idea or concept draft |
| Discuss alternatives | Compare directions and explain preferences | Retained alternatives and an explicit chosen direction |
| Explore visually | Found references, rough generated images and comparisons | References with prompt, source, lineage and observations |
| Try identity and aesthetic language | Character/style experiments before fixing shot execution | Candidate identity/style references, still labelled exploratory |
| Develop toward the screenplay | Select a concept version, references and constraints | An explicit set of inputs for a screenplay draft |

These are interaction requirements, not new entity names already supported by
the Core. A logline exists; references and generated-reference lineage exist
(CT-0100/0101). A structured, versioned concept document and its downstream
usage need a focused contract. Do not use a chat transcript as their authority.

# Navigation and first layout

Proposed primary navigation now includes four task modules:

`Creation / Inception -> Screenplay & Storyboard -> Production -> Editing & Finishing`

These are activities on one film. The two established production phases remain
screenplay/storyboard development and producing the defined film; Creation is
an explicit creative entry before them. Importing an existing screenplay does
not require manufacturing a prior brainstorm or passing an additional gate.

```text
Demo 01                     Creation / Inception          Assistant

Idea & intention            Selected concept draft        References
Alternative directions      What are we exploring?       Original board
Open questions              Constraints and discoveries   Identity trials
Explorations                Drafts and comparisons        Era trials

                            Develop screenplay from…
                            [concept version + chosen reference versions]
```

Open the assistant in context; support direct writing and selection without it.
On small screens, these regions become modes instead of permanent columns.
Generation shows actual adapter availability and cost/quota before execution.
Do not display an enabled generation control before the application operation
and job/result lifecycle are wired.

# Handoff: an output becomes a specific input

The design needs to distinguish three uses of earlier work:

1. **Creative context:** a reference is looked at to inform a decision.
2. **Declared direction:** a person chooses an idea, constraint or visual
   candidate to guide a draft, scene or shot.
3. **Execution input:** an image, text or media version is actually supplied to
   a provider, renderer or assembly. Record what was sent, not merely linked.

One artifact may participate in several uses, which must not be conflated.
An exploration does not automatically become a cast master or a shot's
approved image. References can be addressed directly from later modules; they
do not need to be passed through every intermediate stage.

| From | Selected output | Use downstream |
| --- | --- | --- |
| Creation | Concept draft and chosen exploration references | Context and declared direction for a screenplay draft |
| Screenplay | Specific text and scene/shot coverage | Storyboard action and narrative intent |
| Storyboard | Candidate composition and shot intent | A blockout study or a master-image request |
| Blockout | Measured layout, camera and rendered board | Composition input where the chosen adapter supports it |
| Master images | Human-reviewed image version | Actual clip-generation input |
| Clips | Selected take versions | Scene assembly inputs |
| Assembly | Reviewed scene/sequence versions | Further editing, sound, finishing and delivery inputs |

Existing mechanisms cover parts of this table, not the entire chain. Each new
connection needs an inventory of existing records/commands before adding one.

## Required behavior for future implementation

- **Choose inputs:** later work can select earlier artifacts by stable identity
  and version. Show a preview and why each was selected.
- **Use together:** a concept and multiple references can inform one draft;
  a reference may inform multiple scenes. Preserve those relationships.
- **Trace back:** from a result, reach its actual input versions, prompts and
  producing operation when recorded. From an input, list only known uses.
- **Retain history:** revise by creating a successor candidate; retain earlier
  choices and rationale. Promotion into a canonical screenplay or master uses
  its own explicit operation and authority.
- **Surface changes:** an earlier artifact gaining a newer version does not
  automatically replace the version consumed downstream. Explain the known
  difference and allow explicit reconsideration; do not globally label outputs
  stale without a dependency/fingerprint that justifies the claim.
- **Represent uncertainty:** an old draft with no recorded inputs remains
  "inputs not recorded". Do not reconstruct historical execution from chat or
  infer it from similar-looking images.
- **Survive restart:** saved concepts, chosen direction and input relations
  belong to production records, reachable by the same application commands
  from GUI, CLI or agents. Provider sessions and browser state remain optional.

Generation for early exploration can consume quota or money before screenplay
and storyboard are settled. Distinguish it from final shot production and
show its cost. The free planning path remains available. Do not introduce a
requirement to generate reference art to begin writing.

# Demo 01 as the first test

Existing evidence to display without relabelling its history:

- The original concept board in `references/2026-10-16-chatgpt-draft/`.
- Seven era/identity trials and three later age-control trials, plus earlier
  probes: 13 reference records in total.
- Lia's cast sheet, seven style records and the seven-scene screenplay.
- An incomplete visual storyboard and an opening composition experiment.

These are valuable Creation inputs and outputs, but no saved concept-version
handoff currently proves which exact items generated the screenplay. Show
them as existing references; a person can now declare intended use going
forward. Do not invent a past approval or provider-input relationship.

First acceptance journey:

1. Open Creation and find the original board alongside its prompt and notes.
2. Compare an earlier identity trial with its later age-control alternative;
   keep both and record what the comparison teaches.
3. Save a concept draft and explicitly choose reference versions for developing
   a screenplay draft. Verify exactly what will be passed to any agent/model.
4. Open the resulting draft in Screenplay & Storyboard and trace back to those
   chosen inputs. Promoting it must not silently overwrite the current script.
5. Create a revised exploration, then return to the screenplay: its original
   inputs remain identifiable and updating the direction is explicit.
6. Restart, recover the draft and relations from the film's records, and
   navigate to a later shot while retaining its origin.

# Done

- Final director clarification: the dense evolution panel was visually noisy.
  The interaction is now images grouped by the film's freely named exploration
  rounds; lineage, use and corrections are collapsed details. Demo 01's groups
  are Storyboard reference (1), Eras (9, including early probes), Age control
  (3). These are this film's history, not a fixed three-stage product template.
  Round edits append versions with stable identity; both earlier round records
  remain, while the primary gallery shows three current groups. Tests cover
  arbitrary Costume/Lighting group names, unassigned images and cyclic order.
- Director feedback during implementation: the flat "13 preserved records"
  gallery hides evolution, actual reuse and any review/selection history. The
  Demo 01 files prove board -> probe -> era trial -> six image-conditioned
  studies. Independent age trials share cast/style context but have no image
  parent. Lia's cast references are empty; do not infer master approval from
  reuse or prose observations. A read-model/UI follow-up is in progress to
  expose these distinctions without rewriting historical production records.
- Implemented the feedback: reference-evolution reading separates declared
  ancestry, hash-recorded image inputs, cast designations, draft use and missing
  approval records. Explicit, versioned exploration rounds and creative
  correction pairs share the candidate journal and its lock/revision/atomic
  commit. GUI/HTTP/CLI/MCP use the same operation. The round-entry actor and
  source of the observation are separate.
- Recorded the director's new clarification in Demo 01: seven initial identity
  trials, then three corrective age studies (14/16/18), with three exact
  correction pairs. All 13 reference files/metadata remain unchanged; no
  screenplay or approval was changed. No historical image-parent relationship
  was invented for the text-driven corrective studies.
- Implemented the first GUI at `/app/creation.html`: candidate editing/history,
  reference previews and two-way comparison, contextual assistant presence,
  selected inputs and explicit concept -> screenplay candidate development.
  `/app/preproduction.html?draft=<id>` displays the candidate and exact inputs
  without misrepresenting existing shots as coverage of that text.
- Added shared Core/HTTP/CLI/MCP candidate operations (ADR 0026), optimistic
  revision checks, atomic journal replacement, input digests and drift findings.
- Added `generate_reference` jobs using the existing image adapter. A reviewed
  prompt/input plan and quota consent precede execution; cancellation, staging,
  preview and explicit non-overwriting adoption preserve alternatives.
- First ten Core/CLI/HTTP tests passed, including concurrent writers, failed
  commits, changed inputs and staged generation with a fake provider. Frontend
  builds and existing frontend tests passed. Full-suite and browser acceptance
  are in progress; no live generation was requested by the validation.
- Implementation started: immutable concept/screenplay candidates in a
  project-owned, revision-checked creation journal; selected reference content
  is pinned by digest. Existing screenplay files are never adopted implicitly.
  Shared operations will serve GUI, CLI and MCP. Reference generation will use
  existing background jobs and explicit, non-overwriting adoption.
- Reviewed the current Core/agent boundaries, references implementation,
  onboarding work, GUI pilot and earlier Visual Lab research (CT-0095).
- Defined Creation as a preceding module and specified how its outputs can be
  reused across later modules, including non-destructive version semantics.
- Updated the production flow and filmmaking guide to acknowledge creative
  inception and the difference between exploration and shot production.
- Linked the direction into CT-0104, project status, work index and roadmap.

# To do

0. On the next requested GUI iteration, implement the copilot-first interaction
   and a cross-module human-decision inbox described above. Inventory existing
   decision sources first. CT-0106 has removed manual candidate/round/generation
   forms and input-editing controls, and linked retained drawings to Inception references; concept
   evolve/reject, destination-specific readiness and the inbox remain pending.
1. Get the director's usability review of the implemented Creation/correction
   journey. Browser acceptance and preserved Demo 01 inspection have passed.
2. Add explicit screenplay promotion only with its own revision/authority and
   scene-coverage contract; candidate saves must not implicitly perform it.
3. Extend only the missing storyboard-candidate -> production relationships.
   CT-0106 supplies the drawing import/history/review boundary for canonical
   shots, not master publication. Keep working take and assembly lineage;
   do not force a uniform rewrite.
4. The embedded assistant can discuss contextual drafts; direct insertion of
   its response into the editor remains manual. MCP agents can save explicitly
   requested candidates through the same command, not approve or promote them.

# Decisions

- The additional module is the director's new product direction and supersedes
  the earlier three-module-only navigation proposal for this work.
- Naming is provisional: Creation / Inception. ADR 0026 specifies the minimal
  project-owned candidate journal; no new human gate is introduced. The first
  generation job reuses codex-image rather than adding a provider to the Core.
- A model-generated draft remains a candidate; a human creative choice and its
  durable production record are distinct from a chat exchange.
- Repository development memory remains separate from runtime film context.
  This record must not be packaged as the production agent's creative brief.

# Validation

- First-slice full suite: 1056 tests passed in 603 s. Expanded round/evolution
  full run: 1059 tests in 609 s; one new test had a misplaced CLI assertion
  (`main` out of scope), not an application failure. Fixed the test placement;
  all 13 Creation tests then passed, and all 12 graph/cache tests passed.
  The corrected fast-suite regression passed: 1018 tests in 220 s; heavy
  adapter tests passed in the expanded full run. Do not describe that full
  run as wholly green. After the final gallery simplification, all 14 Creation
  tests passed, the frontend build and all four frontend test files passed;
  the updated disposable browser acceptance also passed.
- `npm run build` passed; `npm test` passed all four frontend test files.
- Disposable browser acceptance passed, including comparison, save/reload,
  exploration-round authoring through the GUI, concept -> screenplay handoff,
  exact inputs, competing writer conflict, quota consent, staged generation,
  explicit adoption, preserved images and mobile overflow. Uses a fake provider;
  no subscription quota consumed. Evidence:
  `/tmp/cine-toaster-creation-review-yzokrjfh/` (final simplified gallery).
- Real Demo 01 read-only browser check passed: all 13 thumbnails, three current
  image groups with arbitrary round labels, collapsed history, prior/corrective
  age comparison, actual assistant composer and
  same-origin context, mobile overflow, no changes to production records.
  Evidence: `/tmp/cine-toaster-creation-live-g0fhp6fr/` (final inspected screenshot).
- Screenplay/storyboard browser regression passed against the updated server.
  An earlier populated-textarea accessible-label issue found by acceptance was
  fixed; all HTML app entry points now revalidate instead of retaining a year
  of stale HTML after a rebuild. Reference drift checks read the catalog once
  per view instead of rehashing every reference for each recorded use.
- The explicitly authorised Demo 01 write added only `creation/state.json`
  with source-attributed exploration rounds and three correction links; later
  grouping corrections retained five record versions for three current groups.
  No generated image or reference metadata, screenplay, cast master or human
  approval was replaced. The GUI is on `127.0.0.1:8787` with the assistant.

Director usability review and canonical screenplay promotion/storyboard
candidate authoring remain open; CT-0103's process incident is not closed by
these automated checks.
