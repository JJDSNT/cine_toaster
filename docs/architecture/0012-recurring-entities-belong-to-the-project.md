# ADR 0012: A character belongs to the project, not to each scene it appears in

Status: accepted

## Context

ADR 0007 moved scene geometry out of a script and into authored project state,
because the production could not see, version, check or show what lived as
constants inside code. A character has the same problem one level up.

Today a recurring character is described wherever it is needed. Each scene file
carries its own prose for the same person. The descriptions are written at
different times by different hands and they diverge without anything noticing:
on a real production, one character across eight scenes had six different
descriptions. Every individual description reads fine. The film does not.

This is not a writing discipline problem. It is a placement problem. Text that
is re-authored per use has no canonical version, so there is nothing for a check
to compare against and nothing for a generation request to attach. The tooling
that would fix it cannot be written while the data is scattered.

The same defect was found in a general-purpose system built for this work
(CT-0014). Its scene entries hold free-text asset descriptions, its asset
manifest records no character, and its guidance contradicts itself inside a
single file about whether identity should be phrased identically across shots.
Independent arrival at the same failure is reasonable evidence that the failure
follows from the placement rather than from the authors.

## Decision

An entity that recurs across scenes is declared once, at project level, and
referenced by a stable id.

Cast is the first such entity (SPEC-0003). A cast member owns its sheet, the
aspects it is authoritative for, and the reference images that generation must
use. Scenes refer to it; scenes do not restate it. The ids already used by
`[[geometry.subjects]]` and by a shot's `subject` and `looks_at` resolve to it.

Authority is declared, never assumed. A sheet states which aspects it decides.
An artifact may be authoritative for one thing and wrong about another, and the
only way that stays true in software is for the artifact to say so.

References are executable. A reference image is not an attachment for a human to
look at; it is what the provider layer is given when a shot names that
character. The caller names the character and never names a file.

What was sent is recorded. Lineage is runtime state beside the authored file
(ADR 0006), naming the references actually passed to generation and their
digests, so that a claim about a take can be contradicted by evidence rather
than trusted.

Locations are the same shape and are deliberately left for later. One entity
implemented is better evidence for the second than two entities designed at
once.

## Consequences

Identity drift becomes checkable before anything is generated, in the same
family as the geometry checks: a subject with no cast entry, a character with
no master reference, a take generated without the reference its character
declares.

Replacing a master reference stops being silent. Prior takes remain valid and
become marked as generated against a superseded master, which is a fact a
director can act on rather than a discrepancy nobody sees.

The scene file gets smaller and says less about who people are, which is the
intended direction: a breakdown should decide shots, not re-describe the cast.
