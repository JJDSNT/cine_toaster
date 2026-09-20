# ADR 0001: Projects are external and indexes are disposable

Status: accepted

## Context

Cine Toaster is an application. Productions have their own identity, lifecycle,
storage needs, and potentially their own version control. Cine Toaster must not
require application code and production content to share a workspace.

## Decision

Cine Toaster opens a project by filesystem path. The application repository and
installation contain no user projects.

The first implementation creates a SQLite search and navigation index at:

```text
$XDG_CACHE_HOME/cine-toaster/projects/<root-fingerprint>/index.sqlite
```

or, when `XDG_CACHE_HOME` is unset:

```text
~/.cache/cine-toaster/projects/<root-fingerprint>/index.sqlite
```

The cache can always be deleted and reconstructed from the source directory.
It is never the exclusive location of creative or production decisions.

Machine-local operational state such as thumbnails, recent-project paths,
process handles, job recovery records, and agent session handles should follow
the same placement principle: use platform application data or cache locations,
keyed by the stable project ID where relevant. Project-scoped does not imply
stored inside the project directory.

A project-local `.cinetoaster/` directory is not part of the default format.
Introducing one requires a specific portability or collaboration use case and
must preserve the rule that deleting it cannot destroy production state.

## Consequences

- A manifest project ID provides path-independent identity. Moving an
  unstructured legacy project creates a new cache until it gains such an ID.
- Search remains fast even for projects containing thousands of files.
- Unstructured directories can still be inspected through the supporting file
  library without application-specific adapters.
- Future canonical metadata must be stored in an open, portable format inside
  the project, not only in this cache.

The repository may contain small demo fixtures and templates under `examples/`.
They are copied to an external destination before normal use and are not a user
project store.
