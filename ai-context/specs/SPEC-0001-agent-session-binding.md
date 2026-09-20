---
id: SPEC-0001
title: Scoped agent threads and provider session bindings
type: specification
status: accepted
implementation: planned
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - agent-runtime
  - sessions
  - providers
  - context-scope
---

# Goal

Allow a Cine Toaster production agent to resume useful provider context through
a provider session ID while guaranteeing project isolation, explicit context
scope, provider replaceability, and human control.

# Context

An external agent provider may return an opaque session identifier that can be
used to continue a prior interaction. That handle is valuable, but it cannot be
the identity of a Cine Toaster agent or conversation:

- providers may expire, reject, rotate, or lose sessions;
- a filmmaking role may change providers;
- one role may have several conversations in the same project;
- the same role may work at project, scene, shot, workflow, or task scope;
- project state may change after the provider built its internal context;
- provider context is not canonical production knowledge.

Cine Toaster therefore owns the logical thread and separately binds it to a
provider session.

# Concepts

## Agent thread

`AgentThread` is the Cine Toaster-owned logical continuity of a production-agent
interaction. It survives provider session rotation and, where policy permits,
provider replacement.

Required fields:

```text
thread_id
project_id
agent_role_id
scope_kind
scope_resource_id
scope_version
status
created_at
updated_at
last_used_at
created_by
title
summary
last_synced_project_revision
context_digest
```

Optional fields may include workflow or task correlation IDs, normalized
transcript location, compaction summary references, and user-facing labels.

Thread status is one of:

```text
active
suspended
closed
```

A closed thread is retained according to operational-state retention policy but
cannot be resumed without an explicit fork or reopen operation.

## Agent session binding

`AgentSessionBinding` associates one Cine Toaster thread with one opaque session
handle owned by an agent provider.

Required fields:

```text
binding_id
thread_id
project_id
agent_role_id
provider_id
provider_session_id
status
created_at
updated_at
last_resumed_at
provider_metadata
parent_binding_id
replaced_by_binding_id
failure_reason
```

`provider_session_id` may be absent while a provider session is being created.
Once returned, it is stored as an opaque value and is never parsed for domain
meaning.

Binding status is one of:

```text
pending
active
suspended
expired
invalid
replaced
closed
```

Only one binding is the preferred active binding for a thread and provider at a
time. Previous bindings remain available for audit according to retention
policy but are never selected implicitly.

# Context scope

A thread has exactly one immutable root context scope:

```text
scope_kind:
  project | scene | shot | workflow | task

scope_resource_id:
  null only for project scope
  stable resource ID for every narrower scope

scope_version:
  version of the scope-resolution policy
```

The resolved context may include canonical dependencies needed to understand the
root resource. For example, a shot scope may include its scene, referenced
characters, location, selected visual references, and applicable decisions.
Those dependencies are resolved by the versioned scope policy; they do not
silently broaden the root scope to the whole project.

The scope tuple is immutable for the lifetime of a thread. Changing project,
agent role, scope kind, or scope resource creates a new thread. This rule avoids
pretending that an already-contextualized provider has forgotten information
after a nominal scope reduction.

# Identity and isolation rules

A provider session may be resumed only when all of these match the stored
binding:

```text
project_id
thread_id
agent_role_id
provider_id
scope_kind
scope_resource_id
scope_version
```

The active UI project is never used as an implicit substitute for `project_id`.
A provider session ID discovered under one project cannot be attached to
another project, even when the same provider and role are configured there.

Multiple threads are allowed for the same project and role. A user or workflow
selects the thread explicitly; "most recent session" is not a safe global
lookup rule.

# Canonical state and storage

Threads, bindings, provider session IDs, normalized transcripts, and compaction
summaries are operational Application Layer state. They are stored in platform
application data keyed by stable project ID, not in canonical film manifests by
default.

Deleting them may lose conversation continuity but must not destroy the film.
The following become canonical only through explicit Project Core commands:

- creative decisions;
- approvals or rejections;
- selected alternatives;
- accepted prompts, notes, or plans;
- registered generated assets and their provenance;
- workflow or human-gate transitions.

Provider authentication tokens and secrets are never stored in session binding
records. They come from the configured credential mechanism. Provider metadata
is namespaced, bounded, and must not contain raw credentials.

# Resume algorithm

`resume_agent_thread` performs these steps in order:

1. Resolve the thread and binding by Cine Toaster IDs.
2. Verify explicit project, role, provider, and immutable scope identity.
3. Reject closed, expired, invalid, or replaced bindings.
4. Re-evaluate current tool permissions and provider access; a prior session is
   not a durable permission grant.
5. Load current canonical project state required by the scope policy.
6. Compare current project revision and context digest with the last synchronized
   values.
7. Build a current authoritative context update. Provider memory is advisory and
   never overrides the project.
8. Ask the provider adapter to resume the opaque session.
9. Stream the run through Agent Runtime and AG-UI/application adapters as
   appropriate.
10. On success, update usage time, synchronized revision, digest, summary, and
    bounded provider metadata.

If the project changed, the runtime does not discard the provider session
automatically. It supplies an explicit resynchronization update. A future
scope-policy implementation may classify a change as incompatible and require a
fork; that decision must be deterministic and observable.

# Resume failure and rotation

If a provider reports that a session is missing, expired, corrupt, or no longer
resumable:

1. mark the binding `expired` or `invalid` with a sanitized reason;
2. retain the Cine Toaster thread and normalized local continuity permitted by
   retention policy;
3. create a new binding instead of overwriting the old provider session ID;
4. seed the new provider session from current canonical scope plus the latest
   safe thread summary or transcript;
5. link old and new bindings with `replaced_by_binding_id` and
   `parent_binding_id`;
6. emit an observable rotation event.

Provider replacement follows the same model: the thread remains, a new binding
is created, and provider-specific context that cannot be translated is not
treated as canonical.

# Forking

`fork_agent_thread` creates a new thread when the user or workflow wants a
different line of reasoning, role, scope, or experimental branch.

A fork records its parent thread and the point or summary from which it was
created. It receives a new thread ID and a new provider binding. Reusing the same
provider session ID for both parent and fork is prohibited unless a provider
adapter can prove the provider itself created an isolated fork and returns a
distinct session handle.

# Context and permission separation

Context scope describes what information is assembled for the agent. Tool
authorization describes what the agent may read or change. These are separate:

- seeing a scene does not authorize modifying it;
- project scope does not grant unrestricted filesystem access;
- a resumed session does not inherit yesterday's tool approval;
- creative human-gate approval does not grant shell, filesystem, network, or
  secret access.

Every tool call is evaluated against current application policy, explicit
project identity, resource scope, and command preconditions.

# Operations

The Agent Runtime exposes implementation-independent operations:

```text
create_agent_thread
list_project_agent_threads
get_agent_thread
resume_agent_thread
suspend_agent_thread
fork_agent_thread
close_agent_thread
invalidate_session_binding
rotate_session_binding
```

Provider adapters expose internal create, resume, cancel, and close capabilities
without leaking their raw API into Project Core or UI components.

# Events

Application events include:

```text
agent.thread.created
agent.thread.suspended
agent.thread.forked
agent.thread.closed
agent.session.bound
agent.session.resumed
agent.session.expired
agent.session.invalidated
agent.session.rotated
```

Events carry `project_id`, `thread_id`, `agent_role_id`, applicable `binding_id`,
correlation/causation IDs, and timestamps. They never include provider secrets
or an unrestricted transcript. AG-UI may represent the associated run lifecycle
to the interface but is not the durable registry for threads or bindings.

# Privacy and retention

- Treat provider session IDs as sensitive opaque identifiers and avoid placing
  them in ordinary logs or UI URLs.
- Store operational records with platform-appropriate restricted permissions.
- Make transcript persistence configurable when providers or productions impose
  privacy constraints.
- Apply explicit retention to closed threads, transcripts, and invalid bindings.
- Redact secrets and raw provider errors before persistence or event emission.
- Deleting operational sessions does not delete canonical decisions already
  promoted to the project.

# Acceptance criteria

An implementation conforms when:

- it can maintain several threads for the same role and project;
- it resumes the correct provider session only for an exact identity/scope match;
- switching the active UI project cannot redirect an existing session;
- changing scope creates a new thread rather than relabeling existing context;
- every resume re-evaluates permissions and current canonical project context;
- project revision drift produces explicit resynchronization behavior;
- provider session loss rotates the binding without losing the Cine Toaster
  thread or corrupting the film;
- provider replacement does not change canonical workflow semantics;
- provider sessions and transcripts remain deletable operational state;
- decisions enter the project only through explicit domain commands;
- events and logs do not expose credentials or unrestricted transcript content;
- tests cover cross-project, cross-role, cross-scope, expired-session, revision
  drift, rotation, and permission-revocation cases.

# Deferred choices

The first provider spike will determine:

- exact operational database schema and indexes;
- transcript and summary serialization;
- provider-specific session creation and resume capability detection;
- context-digest algorithm and change classification;
- retention defaults and storage encryption requirements;
- resource and token budgets;
- whether a provider supports a true remote fork.

These choices may refine implementation but may not weaken the identity,
isolation, authority, and permission rules in this specification without an
explicit revision.
