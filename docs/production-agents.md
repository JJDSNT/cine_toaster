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

## Production Coordinator

The **Production Coordinator** is the production-level orchestrator. It is not
the meta-agent, not a super-director and not a new source of truth.

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

The Production Coordinator may:

- decompose a high-level production goal into role-specific questions/tasks;
- ask only the specialists needed for the current decision;
- discover installed provider/tool capabilities through adapters;
- identify dependencies and blockers before scheduling jobs;
- reconcile compatible recommendations into a proposed plan;
- **surface disagreements rather than deciding creative disputes invisibly**;
- resume workflows from durable project/job state;
- report what requires human approval next.

The Production Coordinator should **not**:

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

## Meta-agent / Workforce Architect

The **Meta-agent** operates one level above production orchestration. Its
subject is the **digital workforce itself**.

Its defining capability is that it may **design and create agents** when the
current workforce lacks a reusable competence. It may also propose changes to,
specialisation/merging of, evaluation of, or retirement of existing agents.

This is not equivalent to granting arbitrary authority. Creating an agent and
granting it powers are separate operations. New access to project writes,
external systems, spending, publication, deployment or other consequential
capabilities must follow explicit permission and human-gate policy.

The Meta-agent should use workforce evidence rather than agent proliferation.
For example, repeated lighting-continuity failures might justify proposing a
specialist only after showing that the competence cannot be handled cleanly by
an existing role.

A lifecycle may be:

```text
need observed -> agent proposed -> human review where required
      -> created -> evaluating -> active
      -> improve / specialise / merge / retire
```

An agent definition should be inspectable and versioned: role, mission,
responsibilities, non-responsibilities, required context, capabilities/tools,
permissions, model/provider policy, budgets, human gates and evaluation
criteria.

The Meta-agent must not silently expand its own authority, erase evaluation
history, or turn every transient task into a permanent agent.

## Cine Toaster Studio Engineering Agent

The **Studio Engineering Agent** owns the evolution and operational health of
Cine Toaster itself. Technology scouting is one responsibility, not its whole
identity.

Its domain spans:

- SDLC: requirements, issues/specifications, implementation coordination,
  review, testing and release;
- DevOps: CI/CD, environments, dependencies, deployment/infrastructure and
  operational failures;
- architecture and technical debt;
- capability gaps discovered by real productions such as Singular;
- technology radar: models, ComfyUI workflows/nodes, Blender, FFmpeg, Ardour,
  compositing/VFX, generative techniques and relevant standards;
- licences, hardware requirements, provider cost and deprecation risk;
- regression and integration health.

External novelty is valuable only after mapping it to Cine Toaster's stable
capability model. A useful finding is not merely "a new model exists", but
whether it fills, improves, duplicates or obsoletes a capability, what adapter
boundary it belongs behind, and what evidence is needed before adoption.

A typical loop is:

```text
production need / external change
            |
            v
 research -> impact/capability analysis -> issue/spec
            |
            v
 implement -> test -> review -> integrate -> release -> monitor
```

The Studio Engineering Agent may coordinate coding agents and specialised
engineering agents, but consequential repository/release/deployment permissions
remain governed by workforce policy.

## Digital Workforce Console

The UI should eventually include a **Digital Workforce** area: not merely an
agent settings screen, but the operational and "HR" view of the entire digital
workforce across film production and studio engineering.

It should make the workforce inspectable at three levels:

**People/roles:** active, idle, evaluating, proposed and retired agents; role,
skills/capabilities, model/provider, permissions, toolbelt, version and owner.

**Work:** current tasks, queues, dependencies, decisions, conflicts, human
gates, failures and recent activity.

**Analytics:** cost, tokens, GPU/runtime consumption, latency, utilisation,
task completion, approval/rejection, human intervention, retries/rework,
quality/evaluation scores and savings/avoided work where those can be measured
honestly.

Useful views include:

- workforce roster and lifecycle;
- per-agent detail and history;
- skill/capability matrix and gaps;
- cost by agent, production, sequence, scene, shot and engineering activity;
- task/dependency activity;
- agent-to-agent handoffs and conflicts;
- evaluation/quality trends;
- proposed hires, role changes, merges and retirements from the Meta-agent;
- Studio Engineering technology/capability radar.

Analytics must distinguish measured values from estimates. "Quality" must never
be a decorative universal percentage: each role needs explicit evaluation
criteria, and artistic judgment may remain human rather than reducible to a
score.

The Console is a view/control surface over runtime/workforce records; it must
not become a second authoritative project database.

## Workforce architecture

```text
                              HUMAN
                                |
                         human gates/policy
                                |
                         META-AGENT
                      Workforce Architect
                   create / evaluate / evolve
                                |
              +-----------------+------------------+
              |                                    |
       FILM PRODUCTION                      STUDIO ENGINEERING
              |                                    |
 Production Coordinator                 Studio Engineering Agent
              |                                    |
 Director / DoP / Editor                SDLC / DevOps / Radar
 Continuity / Design                    coding/testing/release agents
 Sound / VFX / Finishing
 Producer
              |                                    |
              +-----------------+------------------+
                                |
                    DIGITAL WORKFORCE CONSOLE
                  roster / work / quality / cost
                                |
                    Application API / Runtime
                                |
                      capability adapters
                                |
 Blender | ComfyUI/LTX | FFmpeg | Ardour | GitHub/CI | future systems
```

Production Coordinator answers **who needs to work on this production goal**.
The Meta-agent answers **whether the workforce itself has the right agents,
skills, permissions and structure**. The Studio Engineering Agent answers
**how Cine Toaster itself should be researched, built, tested, operated and
evolved**.

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
4. **Production Coordinator** -- initially thin: route work,
   collect findings, expose conflicts and human gates.
5. **DoP and Editor** -- deepen planning and feedback/retake loops.
6. **Production Design, Sound, VFX and Finishing** -- grow as their underlying
   artifact/capability adapters mature.
7. **Digital Workforce Console** -- expose roster, work, gates, evaluation and
   cost from real runtime telemetry.
8. **Studio Engineering Agent** -- connect capability discovery to the actual
   SDLC/DevOps loop.
9. **Meta-agent / Workforce Architect** -- enable evidence-based creation and
   evolution of agents only after agent definitions, permissions, telemetry and
   evaluation are inspectable.

The implementation order should continue to follow Cine Toaster's existing
rule: **Singular exposes the production wall; Cine Toaster takes ownership of
the reusable mechanism needed to cross it.**

## Definition of done for a workforce agent

The following baseline applies to production and engineering agents. Additional
criteria apply to agents with workforce-management or repository/deployment
authority.



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
- How should cost/time budgets influence the Producer and Production Coordinator?
- At what point should the coordinator schedule parallel work automatically?
- What is the canonical, versioned agent-definition format?
- Which permissions can the Meta-agent grant automatically, and which always require a human gate?
- Which evaluation metrics are meaningful for each role rather than vanity metrics?
- How should workforce telemetry and cost history be persisted without competing with project state?
- When does a recurring capability gap justify creating an agent instead of extending an existing one?
