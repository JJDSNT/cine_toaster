# Milestone 01: Project Browser

The first Cine Toaster milestone is intentionally narrow. It must open an
external audiovisual project, index its existing files without changing them,
and make the production navigable.

## User outcome

Given an existing project directory, a filmmaker can:

1. browse its hierarchy;
2. find scenes, takes, versions, and production documents;
3. search filenames, paths, and human-readable text files;
4. preview images, video, audio, text, and PDFs;
5. place up to four media items in a side-by-side comparison.

The initial reference project is `Singular` in the pre-existing `confyui`
workspace. Cine Toaster treats it as read-only.

## Boundary

- Projects are external directories. They do not live in this repository.
- The filesystem remains the source of truth.
- The SQLite index is written under the user's cache directory and is fully
  rebuildable.
- The scanner does not rename, move, or write project files.
- Classification is an adapter hint for navigation, not a permanent domain
  ontology.

## Explicitly deferred

- annotations, approvals, and selections;
- a canonical Cine Toaster project manifest;
- generation and provider adapters;
- asset relocation or project migration;
- production workflow states;
- multi-user writes and locking.

Those features should be designed from observed use of the browser rather than
from a speculative final product model.

## Initial assessment of `Singular`

The current top-level structure is a strong production structure and should be
preserved: screenplay, scenes, cast, locations, visual language, sound,
production documents, and historical work already have clear homes.

The structure inside individual scene directories is intentionally treated as
observational data rather than a finished standard. Current scenes contain
useful but evolving conventions such as `ltx/`, `master/`, `v2/`, `trabalho/`,
`_tomadas/`, `_descartados/`, `teste*/`, and `versoes/`. They document how the
production method was discovered. The browser recognizes these conventions,
but Cine Toaster will not require them for future projects until repeated use
shows which distinctions are stable.

No bulk reorganization of `Singular` is part of this milestone.
