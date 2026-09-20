# ADR 0009: Accumulated knowledge is evidence-linked data, not documentation

Status: accepted

## Context

Singular had accumulated real, expensive knowledge before Cine Toaster existed,
kept in agent skill documents: which instructions LTX 2.5 obeys, which it
inverts, which mistakes cost how many discarded versions, and on what date each
was measured. It is genuinely good material, and none of it was reachable by the
software.

We looked at how a comparable project handles this. Its skills are static
manuals — "when to use", a table of tools, a list of rules. Readable, but written
once by a maintainer, with no date, no evidence, and no way to tell a measured
fact from an opinion. That model does not accumulate; it is documentation with a
folder structure.

The Singular skills are better precisely where that model is weak: almost every
rule carries a date, a scene, and a cost. What they lack is the other half — any
link to whether software now enforces the rule, so a person still has to
remember all of them at the right moment.

## Decision

Knowledge is data the runtime loads, in two kinds.

**Practices** (`knowledge/practices/<id>.md`) are rules the production learned.
Each carries `status` (`measured`, `suspected`, `convention`, `refuted`),
`learned_on`, `evidence`, `cost`, and — the field that matters —
`enforced_by`: the check codes that now enforce it automatically.

**Provider profiles** (`knowledge/providers/<id>.md`) are what a specific
generator does and does not obey. Each claim carries its own status, measurement
date, evidence, impact, and workaround. This is a capability profile a future
generation adapter reads, not prose.

Both use a `+++` TOML header followed by prose. Structured fields have to be
machine-readable so the tool can report what it enforces; the reasoning has to
stay prose or nobody will write it.

Records load from three layers, the same as the transition library: built-in,
shared (`CINE_TOASTER_KNOWLEDGE_PATH`), and the project's own, each overriding
the last by id.

`enforced_by` is validated against the real check registry. A practice claiming a
check that does not exist fails to load, so the ledger cannot drift into
comforting fiction.

## Consequences

The tool can report its own coverage: how many known rules a machine enforces,
which still depend on a person, and which checks have no recorded reasoning
behind them. `toast knowledge` prints it and the interface shows it.

A finding stops being a bare verdict. `toast why eyeline_mismatch` prints the
rule, what it cost the last time it was missed, and the evidence — attached to
the moment someone is looking at the problem.

Refuting a fact is a first-class act. Set `status = "refuted"` and it stops being
enforced without being deleted, because the fact that we once believed it is
itself worth keeping.

What deliberately does not go here is judgment: when to use a long lens, what a
director's style means, "less is more". That is not checkable, gains nothing from
this format, and stays in the skills where it belongs.

Pipelines are not introduced. The comparable project uses pipeline manifests to
orchestrate an agent from brief to render, which is not this product's shape.
The equivalent concept here is the per-scene workflow that already exists, and
the honest next step is to give its steps force as human gates rather than build
a second orchestration vocabulary beside them.
