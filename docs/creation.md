# Creation / Inception

## Pending decisions and approved inputs

Use **Awaiting you** from the main workspaces or open `/app/decisions.html`.
It gathers saved current direction requests and waiting production gates, with
their scope, consequence and origin. Warnings and informal conversations are
not fabricated approval requests; a failed read is shown as unavailable.

When a storyboard-development proposal names existing canonical scene/shot
targets, the review shows them explicitly and offers **Approve & advance**.
The human decision and source-pinned stage input are saved atomically. The same
CoAgent can then develop and retain storyboard drawings. Each retained output
links back to this input/decision; all previous images remain. New image
generation still asks for its own exact quota consent.

This adopts input for development, not final storyboard approval, master-face
selection or a canonical shot-manifest rewrite. An ambiguous proposal needs
agent clarification, not a manual authoring form. Proposals containing only
local draft shot IDs cannot yet be promoted to canonical shots.

If the assistant is unavailable or reaches a turn limit, the approved input
and any outputs remain visible. **Continue approved work** starts another
explicit turn in the same CoAgent. It is not a second scheduler or an assurance
of autonomous recovery after restart. The output display is canonical evidence;
a saved instruction alone is not proof of a running agent or completed work.

Open `/app/creation.html` on a `toast serve <film> --assistant` session.
This is a **human situational view**, not a form-based interface for operating
the agent's work. The copilot develops concepts and alternatives through shared
application operations. The human inspects results, compares directions and
enters at explicit approval/rejection gates with guidance. Chat itself does not
constitute a production decision.

The primary view contains retained visual rounds, comparison, saved candidate
text, known downstream uses, job results and the contextual assistant. Manual
candidate, round and reference-generation forms are removed, not hidden under
Advanced. Reference-input editing checkboxes are removed too. CLI/MCP/HTTP
operations remain available to agents and other authorised callers; no saved
record or image was deleted. Inspection works with the assistant off.

Opening a saved screenplay candidate shows its text and exact inputs. It does
not pretend the current shots cover that candidate, promote it or approve it.
Concept evolve/reject and a unified human decision inbox still require focused
implementation. Destination-specific readiness and a scoped human direction
decision are now available below; they do not imply autonomous execution.

## Is there enough to proceed?

The agent records its assessment for screenplay, storyboard and/or shot masters:
what is sufficient, which gaps remain, who should resolve them and the next
action. This is authored analysis with pinned material, not a score based on
how many images exist. Writing can proceed while master-image identity work
remains open. Readiness for starting a stage is not completion of that stage.

The Inception panel presents one recommendation with its scope and consequence:
**Approve direction** or **Request changes**. The latter opens only a human
direction field, required before sending. Decisions retain actor, time,
assessment identity and guidance in `creation/state.json`; earlier assessments
and decisions remain visible. A changed screenplay/reference/drawing/context
requires reassessment before another decision; a stale journal revision is a
conflict, never a silent replacement. Use **Refresh records** for external work.

Approval adopts this development direction only. It does not approve the
whole storyboard, select cast masters, rewrite the screenplay or authorise a
paid generation. The next agent instruction is retained, with execution
explicitly marked not dispatched. Automatic dispatch/continuation is not
implemented by this first assessment/decision slice (CT-0107); no running job
is fabricated. Human review actions work even with the assistant disabled.

Agents use MCP `assess_inception`, or `POST /api/creation/assessment` with
title, summary, destination-specific readiness, proposal and reference IDs.
Humans use `POST /api/creation/direction` with assessment ID, outcome
(`approved` / `changes_requested`), guidance and expected journal revision.
Both use shared operations; no MCP tool decides the human outcome.

```bash
toast creation assess /path/to/film --assessment-file assessment.json \
  --expected-revision 5 --actor creative-agent
toast creation decide /path/to/film assessment_id --outcome approved \
  --expected-revision 6 --actor director
```

The agent's JSON readiness entries name `destination`, `status` (`ready`,
`needs_work`, `not_assessed`), `summary` and `gaps`; each gap has `description`,
`owner` (`agent` / `human`) and `next_action`. The proposal names `destination`,
`question`, `scope`, `why` and `next_step`. Reference IDs are pinned alongside
the existing screenplay, storyboard drawings and creative context.

For Demo 01, the populated drawings are **SC-010 / Wake, P1/P2/P3**, at
`/app/preproduction.html?scene=SC-010&shot=P1`. Creation links directly to the
known populated work; the normal Control Room Storyboard also shows the drafts.

## Evolution is more than a preserved-file count

The primary gallery groups images by exploration round. Names, membership and
the number of rounds are freely defined for each film; these are not fixed
product stages. History, image lineage, actual recorded inputs, cast
designations and downstream use are available in collapsed details. None of
those relationships is automatically a human approval record.
Known storyboard uses now link to the exact drawing's scene, shot and retained
version; drawings link back to the reference card. Declared inputs remain
distinct from actual provider execution and from approval.

The shared **record exploration round** operation names the selected references,
purpose/problem, observation source and optional earlier round/correction pairs.
An agent can create a round or revise its title/membership/order. The
journal retains the whole pass, exact references and earlier record versions.
Revising a round is not regenerating its images. It does not
rewrite a reference's image-parent field or approve the new result.

For Demo 01 only, the director specified three groups: **Storyboard reference**,
**Eras**, **Age control**. They contain 1, 9 (including early era probes), and 3
reference records. The age-control studies correct insufficient maturation in
the era pass at 14/16/18; those three specific correction links remain recorded.
The image
generation records show that the second round used cast/style text, not the
earlier images. Both facts can therefore be displayed without contradiction.

CLI: `toast creation round <film> --title ... --reference <id> ...
--expected-revision <n> --why ... --source ...`, optionally `--follows <round-id>`
and repeated `--correction <previous-id>=<current-id>`; `--based-on <round-version>`
revises the group without deleting its earlier record. HTTP uses
`POST /api/creation/rounds`; MCP exposes `record_exploration_round`. All use the
same journal command. Conflicts never silently replace an earlier decision.

## Explore a new reference

The agent plans generation through the existing operation with parent reference
IDs, an optional saved concept and a visual request. The plan contains the
effective instruction, pinned inputs, availability and quota disclosure. The
first adapter is codex-image; it consumes subscription quota, not a known USD
amount. Unsaved concept text is not a generation input.

Generation requires explicit quota consent. Work runs as a background job,
with progress/cancellation/failure visible. Inspect the staged result and
**Keep as a new reference** to add it to the film. Earlier images are never
overwritten; the new reference is not automatically selected or approved.
Authentication/provider failures are reported by the job, not a successful
availability badge. `toast doctor` reports the installed capabilities.

## Other interfaces

`GET /api/creation` returns candidate history, reference previews and findings;
`POST /api/creation` saves using a required `expected_revision`. A conflict is
HTTP 409 and preserves the editor text. Inspect/refetch records before retrying.

```bash
toast creation list /path/to/film
toast creation save /path/to/film --kind concept --title "Direction A" \
  --text-file concept.txt --expected-revision 0 --actor director \
  --reference reference-id --why "Keep identity; explore the craft"
toast creation save /path/to/film --kind screenplay --title "Screenplay trial" \
  --text-file trial.fountain --concept draft_saved_id --expected-revision 1
```

MCP exposes `read_creation`, `save_creation_candidate`,
`plan_reference_exploration` and `start_reference_exploration`. Follow the job
with `wait_for_job(adopt=False)` to inspect it before explicitly adopting.

Candidates live in the film's `creation/state.json`, not SQLite/chat/cache.
Actual reference bytes and provenance keep their established `references/`
format. Missing/changed inputs are reported; newer alternatives never silently
replace an older candidate's inputs. Existing films need no retroactive concept
or invented historical handoff to keep using their screenplay.
