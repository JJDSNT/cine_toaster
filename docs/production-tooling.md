# Production-specific tooling

Cine Toaster owns reusable filmmaking mechanisms. A production owns the
creative values and one-off automation that make its film look and behave like
that film.

This boundary matters even when a mechanism was first discovered while making
one production. Moving code into Cine Toaster must not move the production's
look with it.

## Ownership test

Ask what remains after the film-specific material is removed:

- If a substantial, film-independent operation remains, Cine Toaster may own
  that operation. The production supplies its palette, curve, timing, mask, or
  other creative input explicitly.
- If only a small generic shell remains around distinctive numbers, geometry,
  or scene assumptions, keep the complete tool with the production.
- A value that worked for one film is not a default. A Cine Toaster default
  must be technically neutral or broadly safe, not hidden creative content.

The origin of a mechanism does not decide ownership. Its knowledge does. Code
may be promoted from a production once its film knowledge can be removed
without making the remaining abstraction trivial or misleading.

## What a production should do

A production may keep its own scripts, LUTs, masks, curves, recipes, shaders,
and related documentation in its own directory and version control. Cine
Toaster does not currently reserve a general `tools/` directory or define a
general recipe file. A production can choose a layout that suits its workflow.

When Cine Toaster already provides the mechanism, a production should call it
with explicit creative inputs. Those inputs remain production-authored data;
they must not be copied into the application as defaults.

When no useful separation exists, the complete operation stays with the
production. Another film is not required to copy it or have an equivalent.

Cine Toaster never discovers or executes arbitrary project code merely because
it is present. A supported extension point may load a constrained declared
asset, as the transition catalog does. Integrating a production tool with jobs,
the GUI, CLI, or agents requires a typed operation with declared inputs,
outputs, side effects, project scope, and permissions. It must not become an
implicit shell escape.

## Examples from Singular

These examples established the boundary; Singular itself remains external to
this repository.

| Operation | Owner | Reason |
| --- | --- | --- |
| grading | Cine Toaster mechanism; production palette | Palette is an explicit input and the remaining LUT operation is substantial. |
| switch off ceiling fixtures | Cine Toaster mechanism with flags | Detecting and dimming unwanted cold ceiling light is a reusable repair. |
| animate point of focus | Cine Toaster mechanism; production curves | The curve is a directorial choice and is therefore required input, not a default. |
| relight one particular room at night | production | Its colour vectors, power curve, and spatial assumptions are the look of that film; removing them leaves only a trivial mask-and-blend shell. |

## Demo examples

The two source templates demonstrate opposite valid outcomes:

- **The Last Signal** needs no executable project extension. Its README shows
  how a scene-specific palette or focus curve would remain explicit production
  input to a shared operation.
- **Amiga Demo Reel** includes `transitions/amiga-copper-bars/`. Cine Toaster
  owns the constrained transition loader and GLSL host contract; the production
  owns the copper colour, bar pattern, timing, and editorial meaning. Those
  choices do not become a built-in transition.

The examples are intentionally asymmetric. A production-specific tool is an
option, not a required project component.

