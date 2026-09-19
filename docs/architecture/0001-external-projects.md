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

## Consequences

- Moving a legacy project creates a new cache until a future project manifest
  supplies a path-independent project ID.
- Search remains fast even for projects containing thousands of files.
- Unstructured directories can still be inspected through the supporting file
  library without application-specific adapters.
- Future canonical metadata must be stored in an open, portable format inside
  the project, not only in this cache.

The repository may contain small demo fixtures and templates under `examples/`.
They are copied to an external destination before normal use and are not a user
project store.
