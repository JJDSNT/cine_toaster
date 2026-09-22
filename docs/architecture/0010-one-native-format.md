# ADR 0010: One native format, and it is YAML

Status: accepted. Amends ADR 0006 and supersedes the export path added with it.

## Context

Cine Toaster read a TOML scene file of its own. Singular, the production it is
built for, keeps its breakdown in YAML. To bridge them an exporter generated a
`scene.toml` beside each authored breakdown.

That was wrong, and the evidence was in the code we then had to write. A copy on
disk drifts, so we added `scene_out_of_date` — a digest check whose only purpose
was to detect a problem the copy created. Fixing a self-inflicted wound is a
reliable sign of a bad boundary.

The second cost was measurable: of 31 fields per shot in the authored source,
the export carried 5. Anyone working on the production still had to read the
original, so the tool was an additional surface rather than a place to work.

"The filesystem is the source of truth" means the state lives in files any tool
can read. It does not mean everyone must use the same file we invented.

## Decision

There is one native format, and it is the production's own: **YAML**, with the
breakdown as the scene file. No export step, no adapter layer, no second format
to keep in step.

YAML rather than TOML because of the shape of the data, not familiarity. A
breakdown is deeply nested — `falas: [{quem, en, pt, como}]`, `deriva: {…}`,
`geografia.cameras[].mira` — and it carries prose at several levels. TOML
punishes nesting and makes long prose awkward; YAML does neither. The
conventions already permit this: *do not contort important contracts merely to
avoid a justified dependency.*

`state.json` is unchanged. ADR 0006's split stands and is now sharper: the one
authored file is never rewritten, and everything the runtime commits lives
beside it in JSON.

**Takes are not declared.** They are files, discovered by reading the work
directory. `work/c04.mp4` is the clip in the cut, `_takes/c04-t11.mp4` a
kept alternative, `_rejected/c04-wrong-side.mp4` a rejected one carrying its
reason in its name. A declaration would be a second copy of something the
filesystem already states, and second copies drift.

**Field names stay in the production's vocabulary** (`planos`, `geografia`,
`quem`). The Core's domain model is English and one function translates between
them. Renaming the format would have broken roughly 1,500 lines of working
production tooling in the middle of a production, to buy nothing the film needs.
An English alias layer is a cheap later addition if an audience ever needs one.

## Consequences

Deleted: the exporter, the generated `scene.toml` in every scene, the digest,
`scene_out_of_date`, and the practice explaining it. A design is going well when
it removes code.

PyYAML becomes a real dependency. The dependency-free startup path is gone, and
the conventions are updated rather than quietly broken.

A scene may exist in several variants — the same scene reworked for a different
engine. The project names the variant in production; the others stay on disk as
history without competing for the scene id.

The risk taken knowingly: YAML's implicit typing. `safe_load` is used
everywhere, and a value like `no` or `on` becomes a boolean where TOML would
have kept a string. Scene and camera ids are quoted in the templates for that
reason.
