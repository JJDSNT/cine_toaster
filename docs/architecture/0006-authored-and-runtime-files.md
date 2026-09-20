# ADR 0006: Separate authored files from runtime-owned state

Status: accepted. Amended by
[ADR 0010](0010-one-native-format.md), which replaced the TOML scene file with
the production's own YAML breakdown. The split this record establishes — an
authored file the runtime never rewrites, and runtime state beside it — is
unchanged.

## Context

Milestone 02 needs the first canonical write. The obvious place to put a
selected take was the existing `scene.toml`, next to the shot that owns it.

Two things make that the wrong choice.

The first was mechanical: Python reads TOML in the standard library but does not
write it. ADR 0010 later removed that consideration entirely.

The second is the real one, and it still holds. Authored scene files carry comments, section
headers, and long prose direction notes. In Singular, the feature production
this tool is built for, the authored scene description holds the geography of the room,
the reason each character is filmed from a fixed height, and which shots reuse
another shot's master image. A round-trip through any serializer destroys all of
it. Software that silently eats a director's notes is worse than software that
cannot write at all.

## Decision

Cine Toaster never rewrites a file a human authored.

- Authored, human-owned: `project.yaml`, the scene breakdown,
  screenplays, world files. The runtime reads them and treats them as intent.
- Runtime-owned: `state.json` beside the breakdown, written only by application
  commands. It holds committed selections, the decision history, and the scene
  revision used for conflict detection.

When the two disagree about a selected take, the committed decision wins, and
the authored value is still reported as `authored_selected_take` so a generator
can be re-run from the original intent.

Runtime state is JSON because the standard library writes it losslessly, it
diffs readably, and nothing in it was typed by a person.

Writes are atomic: a temporary sibling file, `fsync`, then `os.replace`. A
failed write leaves the previous committed state readable and unchanged.

## Consequences

An external tool can regenerate `scene.toml` from its own source of truth as
often as it likes without touching decisions already made. ADR 0010 went further and removed
the generated file altogether.

The cost is two files per scene and one more thing to explain. A future
consolidation is possible but must not reintroduce rewriting authored text.

The event log is neither of these. It is operational, lives in the application
cache keyed by project location, and can be deleted without losing production
truth.
