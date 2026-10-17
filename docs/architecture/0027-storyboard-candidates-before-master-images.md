# ADR 0027: Storyboard candidates are not discovered stills or approved masters

Status: accepted for CT-0106 implementation.

Retain draft storyboard drawings in the production's `storyboard/` directory.
`storyboard/state.json` is a runtime-owned, revision-checked journal of immutable
candidates; `storyboard/images/<candidate-id>.<suffix>` holds retained image
bytes. A shared import operation validates the scene/shot, copies a new image,
pins its hash, relevant screenplay/shot context and selected reference versions,
and atomically appends the record under the existing root-directory lock.
Failure leaves the previous journal and all older images unchanged.

Keep image-generation provenance and declared creative inputs distinct. A
reference supplied to a provider is recorded as such; selecting a reference
after generation records association, not invented execution history.

The latest candidate is the default preview, not a human selection. Older
versions remain addressable. Report missing/changed images or inputs and
changed story context instead of silently relinking. No candidate import
rewrites authored screenplay/scene files, changes cast masters, decides a gate,
or publishes a final still. Existing still discovery remains a separate path.

The first slice links the current canonical screenplay's shot coverage, not
unpromoted screenplay candidates. No renderer, geometry or fixed face is a
prerequisite. Shared reads/writes serve CLI, HTTP, MCP and agents; the GUI
focuses on reviewing images, not another primary authoring form.
