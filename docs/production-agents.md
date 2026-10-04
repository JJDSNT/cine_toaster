# Production agent roles

Status: **architectural direction / pending implementation**

Cine Toaster's agents should model **film-production responsibilities**, not
vendor tools. Blender, ComfyUI, LTX, FFmpeg, Ardour, compositors and future
providers belong in the toolbelt; an agent represents a durable production
role, uses the same Application API as GUI/CLI, and acts on the same canonical
project state.

This keeps the agent model useful when tools and models change and makes the
system resemble the production it is intended to coordinate: a feature film
with many shots, alternatives, decisions, dependencies and human approvals.

## Principles

- **Roles before tools.** Do not create a Blender Agent or LTX Agent merely
  because an integration exists. Expose capabilities and let production roles
  use them.
- **One production state.** Agents do not keep private authoritative copies of
  scenes, takes or decisions.
- **Human gates remain explicit.** Agents may analyse, propose, prepare and
  execute authorised work; creative/final approvals remain visible decisions.
- **Durable rationale.** Important proposals, rejections and approvals should
  say who/what made them and why.
- **Specialists may disagree.** A good orchestration model preserves a
  continuity objection or editorial concern rather than hiding it behind a
  single synthetic answer.
- **No rigid assembly line.** Film production is iterative. Editing can request
  a retake; continuity can stop an expensive render; VFX can return a selected
  take for another generation.
- **Capability-driven execution.** Roles request operations such as
  layout-guided generation, matting, mixing or restoration. Adapters choose the
  installed provider able to perform them.

## Proposed production roles

### Director

Owns dramatic and cinematic intent: what the scene means, what an audience
should perceive, performance intention, emphasis, reveal, pacing and approval
criteria. The Director should produce constraints and intent that other roles
can execute rather than micromanaging provider prompts.

Typical interactions: screenplay/breakdown -> directing intent -> DoP,
Production Design, Sound and Editor -> review generated takes -> approve or
request changes.

### Cinematographer / Director of Photography (DoP)

Translates directing intent into visual cinematography: shot size, lens,
camera position/movement, composition, axis, depth, exposure/lighting intent
and visual coverage. It should use scene geometry and 3D previs where useful
without making Blender animation responsible for final generative performance.

### Production Designer

Owns the visual continuity of locations, sets, props and material appearance.
It connects screenplay requirements, asset/reference libraries and 3D set
representations. It should distinguish production facts from temporary
generation references.

### Script Supervisor / Continuity

Maintains production-wide continuity rather than only per-shot validation.
Cine Toaster already has useful inputs for this role: measured geometry, line
of action, named cameras, shots, takes, sequences and durable decisions.

Its eventual continuity ledger may track, where a production declares them:

- character position, screen direction and eyeline;
- wardrobe, hair, injuries and carried objects;
- prop/set state (open/closed, broken/intact, present/absent);
- time of day, weather and lighting continuity;
- narrative/temporal dependencies;
- character emotional/performance state;
- known continuity exceptions deliberately approved by a human.

It may block or warn before an expensive generation when the planned shot
contradicts known production state, but must distinguish measured facts,
authored intent, inference and advisory findings.

### Editor

Owns the cut as a narrative construction: take comparison, coverage, rhythm,
shot order, transitions, J/L cuts and requests for pickups/retakes. Selection
remains a durable decision rather than deleting alternatives.

### Sound Designer / Supervising Sound Editor

Owns the scene's sonic intention and detailed sound construction: dialogue
needs, ambience, Foley, effects, perspective and transitions. It may prepare
stems and hand work to an external DAW such as Ardour; Cine Toaster should not
reimplement a DAW.

### VFX Supervisor

Determines which selected material needs compositing/VFX operations and
coordinates plates, mattes, clean plates, alpha generation, masks, generated
elements and compositing passes. It operates on derived artifacts and preserves
their provenance.

### Colorist / Finishing

Owns final image consistency and delivery transforms: shot matching, look,
detail refinement, restoration when applicable, delivery resolution, SDR/HDR
paths, colour metadata and masters. Generative finishing operations remain
reviewable derivatives, never silent replacements of approved sources.

### Producer / Production Manager

Owns production progress rather than artistic taste. It should provide an
operational view across scenes and sequences: what is approved, blocked,
awaiting generation/review/VFX/sound, what jobs failed, estimated/actual
provider cost where available, and what decisions are preventing completion.

A useful Producer answer should eventually resemble:

> Sequence Boreal: 17 shots; 12 approved, 3 awaiting generation, 1 rejected
> for continuity and 1 awaiting VFX. These are the blockers and the next
> decisions required.

## Meta-agent / Production Coordinator

A **meta-agent is a possible orchestration layer**, not a super-director and
not a new source of truth.

Its purpose is to understand a production request, identify which specialist
roles and capabilities are relevant, gather their findings, expose conflicts,
sequence authorised work and return a coherent production-level status or
proposal.

For example:

```text
Human: "Prepare the Boreal arrival sequence for generation."
                         |
                         v
                Production Coordinator
                  /       |        \
                 v        v         v
             Director    DoP    Continuity
                 \        |        /
                  \       |       /
                   proposed shot plan
                         |
                    human gate
                         |
                generation capability
                         |
                 takes + provenance
                    /           \
                   v             v
                Editor        Continuity
                    \           /
                     review decision
```

The meta-agent may:

- decompose a high-level production goal into role-specific questions/tasks;
- ask only the specialists needed for the current decision;
- discover installed provider/tool capabilities through adapters;
- identify dependencies and blockers before scheduling jobs;
- reconcile compatible recommendations into a proposed plan;
- **surface disagreements rather than deciding creative disputes invisibly**;
- resume workflows from durable project/job state;
- report what requires human approval next.

The meta-agent should **not**:

- become the owner of project state;
- bypass human gates;
- silently override a specialist's finding;
- encode Blender, ComfyUI, LTX or any provider into its domain logic;
- turn every operation into an expensive multi-agent conversation;
- invent production facts when the project does not contain them.

### Orchestration policy

Use the smallest useful team. A metadata query may need only the Producer. A
camera plan may need Director + DoP + Continuity. Finalising a difficult shot
may involve Editor + VFX + Finishing. The coordinator should select roles by
required capability and risk rather than always broadcasting to every agent.

Parallel work is appropriate when roles are independent; ordering is required
when one decision is an input to another. Conflicts should become first-class
review items, for example:

```yaml
review:
  type: agent_conflict
  subject: SC-120/P07
  positions:
    - role: cinematographer
      proposal: cross_axis
      reason: reveal the station entrance
    - role: continuity
      finding: violates_declared_axis
  requires: human_decision
```

The exact schema is illustrative. It should not be added to Project Core until
a real production workflow requires it.

## Relationship to tools

```text
Production roles
Director | DoP | Editor | Continuity | Sound | VFX | Finishing | Producer
                              |
                    Application API / Runtime
                              |
                     capability adapters
                              |
 Blender | ComfyUI/LTX | FFmpeg | Ardour | compositor | future providers
```

Tools can disappear or be replaced without changing the production roles.
Likewise, one tool may serve several roles: Blender can support DoP previs,
Production Design and VFX; FFmpeg can serve Editor, Sound and Finishing.

## Suggested implementation order

This is not a commitment to implement all roles immediately.

1. **Script Supervisor / Continuity** -- extends data Cine Toaster already owns
   and can prevent expensive mistakes before generation.
2. **Director** -- establishes explicit creative intent and acceptance criteria
   that downstream roles can consume.
3. **Producer / Production Manager** -- makes a feature-length production
   operationally observable.
4. **Production Coordinator (meta-agent)** -- initially thin: route work,
   collect findings, expose conflicts and human gates.
5. **DoP and Editor** -- deepen planning and feedback/retake loops.
6. **Production Design, Sound, VFX and Finishing** -- grow as their underlying
   artifact/capability adapters mature.

The implementation order should continue to follow Cine Toaster's existing
rule: **Singular exposes the production wall; Cine Toaster takes ownership of
the reusable mechanism needed to cross it.**

## Definition of done for a production agent

A role should not be considered integrated merely because an LLM prompt with
that role name exists. It is integrated when it can:

1. read only the production context needed for its task;
2. use the same Application API and canonical project state as GUI/CLI;
3. produce structured, inspectable findings/proposals;
4. distinguish facts, authored intent, inference and recommendation;
5. invoke only authorised capabilities;
6. persist consequential decisions or findings with provenance;
7. stop at configured human gates;
8. survive process restart through durable state where required;
9. report failures without pretending work completed; and
10. be exercised against a real production scenario.

## Open questions

- Which findings belong in runtime state and which remain ephemeral advice?
- What is the minimum continuity ledger Singular actually needs?
- Which decisions require Director approval versus a general human gate?
- Should agent conflicts be persisted as review objects?
- Which roles need long-lived sessions and which should be stateless calls?
- How should cost/time budgets influence the Producer and meta-agent?
- At what point should the coordinator schedule parallel work automatically?
