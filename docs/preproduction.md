# Screenplay & Storyboard pilot

Open `/app/preproduction.html` on a running Cine Toaster server, or choose
**Screenplay & Storyboard** in the Control Room's Writing navigation. This
React page is an initial inspection and navigation slice of the three-workspace
proposal (CT-0104), tested against Demo 01. Existing rooms remain available.

[Creation / Inception](creation.md) now precedes this view. Opening
`?draft=<id>` instead displays a saved screenplay candidate and its recorded
concept/reference inputs, not the current film's shot coverage. Promotion is
explicitly not implemented; candidate saves never replace the screenplay.

The scene's screenplay and proposed shots appear side by side on wide screens
and stacked on narrow screens. A passage's shot buttons select its covering
shot; selecting a shot highlights its screenplay coverage. Scene, shot and
composition-study selection are kept in the URL for refresh and browser back.
Use **Refresh** to read changes made elsewhere.

**Shot visual** displays retained storyboard drawings, ordered shot thumbnails,
their reference inputs and collapsed version/provenance history (ADR 0027).
The latest drawing is the default preview, not a selected or approved master.
`?scene=<id>&shot=<id>&candidate=<id>` reopens a specific retained version.
An invalid explicit version is reported rather than silently substituted.
Missing drawings and read failures have distinct feedback. Changed shot context,
reference inputs or image bytes produce findings, not automatic replacement.
Links trace back to the Inception reference; its known uses link back here.
An existing discovered shot still remains separate, in collapsed details.
The normal Control Room **Storyboard** (`/?view=storyboard`) also reads these
same draft candidates and links to the exact drawing beside its screenplay.
It does not show an empty storyboard merely because final stills are absent.
**Composition study** displays existing clay start/end boards and a scene
animatic, when available. The displayed still's plan fingerprint can be stale;
the animatic's currency is not established by those still fingerprints.
Mannequin previews do not establish acting or pose correctness.

The assistant control always shows its availability. When enabled on the
server, it opens the existing directing assistant and sends the current
scene/shot, selected intent and visible review context. Off or unavailable
services have an explanation and a recheck action. Launching with
`toast serve <film> --assistant` enables the optional service; merely opening
the panel does not start a model call.

The shared import command retains a drawing in `storyboard/images/` and pins
the shot context, reference hashes, actor, prompt and provenance in
`storyboard/state.json`. It never changes screenplay, shot manifests, cast
masters or human gates. CLI accepts an explicit local source file; HTTP/MCP
accept only sources already inside the production. There is no primary import
form in this review view.

```bash
toast storyboard candidates /path/to/film --scene SC-010
toast storyboard add /path/to/film SC-010 P1 --image drawing.png \
  --title "Opening draft" --expected-revision 0 --reference reference-id
```

`GET/POST /api/storyboard`, MCP `read_storyboard_candidates` /
`save_storyboard_candidate` and CLI share the same read/import operations.
An expected-revision conflict is HTTP 409; prior images remain unchanged.
Declared creative references are not fabricated evidence of provider execution.

The expandable journey explains story drawing -> 3D composition -> shot master;
a static still is not by itself another production stage or approval. The full
handoff to finished masters remains outside this slice. Demo 01 has three
opening drawings, not a complete 24-shot storyboard or director approval.

**Edit screenplay** opens the existing
revision-checked editor; **Open scene tools** opens the scene's existing
commands and review tools. Return with browser back. Reference files, cast,
locations and styles are linked to their existing rooms, not silently assigned
to the selected shot. Approval state is read from the existing scene gate.

## Agent-led decoupage and continuity

The **Awaiting you** link shows how many real saved human requests are waiting,
even if their origin is Inception or another scene. Open the inbox to inspect
the question/scope and follow **Open request in context**. The same inbox shows
approved development inputs and links to retained storyboard outputs; it does
not invent a running state for unfinished work.

For existing-shot storyboard development, **Approve & advance** records the
exact displayed target and starts the same CoAgent's Art Direction role. Its
retained drawings appear in the ordinary storyboard view, with predecessor,
reference and handoff/decision provenance. No previous image is overwritten.
New generation needs separate quota consent. This does not approve the final
storyboard, rewrite a shot manifest or start 3D/master work automatically.

**Directing & continuity** shows scene shot-plan proposals and independent
reports retained by the assistant (CT-0111). Open **Assistant** and request
decoupage or a canonical continuity audit. No manual proposal form is needed.
Expand versions to inspect action, framing, camera intent, duration, exact
screenplay coverage, proposed entry/exit facts, source basis and limitations.
Canonical checks are separate from proposed checks; text is not pixel evidence.

A current successful proposal review can produce **Shot proposal · your
direction**, with approve/request-changes controls. Saving human guidance
starts another turn in the same assistant; versions remain and the page updates
without reload. This approves only the proposal's stated scope, not canonical
shot replacement, storyboard images or paid generation. Old reports/decisions
become stale when their proposal or canonical sources change. The complete
proposal-to-canonical-shot/image handoff remains unimplemented.

`scripts/check_directing_agents.py` exercises the real public CoAgent and HTTP
commands with a deterministic model on a disposable film, including a human
changes handoff, retained versions, reload and mobile layout. It does not
establish artistic quality or modify the user's production.

## Development validation

```bash
cd frontend
npm test
npm run build
```

Against a running production with at least two scenes containing proposed
shots, the read-only browser walkthrough saves screenshots and checks
selection, reload/back, composition access, a second scene, assistant off and
unavailable states, and mobile overflow:

```bash
.venv/bin/python scripts/check_preproduction.py http://127.0.0.1:8765
```

The browser walkthrough requires Playwright and its Chromium installation. It
uses actual production reads and mocks assistant failure responses to test
feedback without starting a conversation. If the real service is available,
it also checks that its chat composer renders and receives scene/shot context.
It does not validate human usability or the assistant's model responses.
`scripts/check_storyboard.py` tests retained-version navigation on a disposable
film, input/use trace-back, missing/error states and mobile layout. Its
`--inspect <origin>` mode reads the real Demo 01 without writes. No model is
called by either mode. CT-0103 remains
the acceptance record for the complete process.
