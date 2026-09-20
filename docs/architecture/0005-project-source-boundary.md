# ADR 0005: Open projects through a source boundary

Status: accepted

## Context

Cine Toaster already opens arbitrary local directories, while built-in demo
projects are templates copied to external locations. Future projects may live
on mounted storage or originate in an object store. Local filesystems and object
stores do not share write, locking, watching, consistency, or identity
semantics.

Making Project Core accept provider URIs would couple production behavior to
storage infrastructure and weaken filesystem safety.

## Decision

The Application Layer opens a `ProjectLocator` through a
`ProjectSourceAdapter`, producing a local `MaterializedProject`. Project Core
continues to operate only on the materialized filesystem project.

The initial adapter supports external local `file://` projects. It uses the
external directory directly. Future object-store adapters must materialize a
workspace and implement explicit revision-aware pull, push, and conflict
behavior.

Project identity comes from `project.toml`, not path or locator. Registering the
same ID at two different locators is an explicit conflict rather than two
independent open projects.

The detailed contract is maintained in
[`SPEC-0002`](../../ai-context/specs/SPEC-0002-project-sources.md).

## Consequences

- External projects need not originate from Cine Toaster templates.
- Local, mounted, and remote storage remain Application Layer concerns.
- The Core retains ordinary filesystem and atomic-write semantics.
- A future cloud adapter requires local materialization and conflict-safe sync;
  adding an `s3://` string alone is not cloud support.
- Credentials, signed URLs, caches, and transfer state stay outside canonical
  project files.
- Multi-project registration can be developed before remote storage is chosen.
