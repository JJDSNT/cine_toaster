# ADR 0001: Projects are external and indexes are disposable

Status: accepted

## Context

Cine Toaster is an application. Productions such as `Singular` and `Ceva` have
their own identity, lifecycle, storage needs, and potentially their own version
control. The earlier `confyui` workspace combines tools and productions because
it grew as a productive laboratory; Cine Toaster must not require that coupling.

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
- The current scanner can be tested against `Singular` without modifying it.
- Future canonical metadata must be stored in an open, portable format inside
  the project, not only in this cache.

