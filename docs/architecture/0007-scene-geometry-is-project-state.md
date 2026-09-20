# ADR 0007: Scene geometry belongs to the project, not to a script

Status: accepted

## Context

The continuity failures that matter in generated film are not bad frames. They
are coherent shots that do not cut together: a camera that crosses the line of
action, a character filmed from above in one shot and below in the next, a set
whose dimensions drift between angles. Each individual shot passes review. The
scene fails.

Productions already solve this on paper. In Singular, the scene file carries measured room dimensions, the position of every
person, and a list of named camera positions with what each one is aimed at and
which shots use it. That model was invented by the author by hand, independently
of Cine Toaster, which is good evidence that it is the right one.

The problem was where it lived. The same production keeps its set as measured
constants at the top of an 859-line Blender script. The geometry was code, so
the project could not see it, version it, check it, or show it.

## Decision

Scene geometry is first-class authored project state, declared in the scene
file:

- `[geometry.room]` — measured width, depth, height;
- `[[geometry.subjects]]` — who is where, with an optional eye height;
- `[[geometry.cameras]]` — named, fixed positions with target, lens, and an
  optional height;
- `[geometry.axis]` — the line of action, named explicitly by the author.

Shots reference a camera by id rather than describing a new viewpoint.

Heights are optional. A plan drawn from measurements usually exists long before
anyone decides how high the camera sits, and a check invented from a default
value is worse than no check.

The axis is never inferred. A tool that guesses which two characters define the
line will eventually accuse a correct scene of being wrong, and one false
accusation costs more trust than ten true findings earn.

## Consequences

`toast check` can read the grammar of a scene before anything is generated, and
the interface can draw the set from the same data.

Generation adapters gain a provider-neutral place to read camera intent from,
instead of each one re-parsing prose.

The geometry is deliberately 2D plus heights. It describes staging, not set
dressing. If occlusion and sightlines through real geometry ever matter, that is
a different model and a separate decision.
