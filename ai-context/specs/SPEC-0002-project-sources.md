---
id: SPEC-0002
title: Project locators, sources, and materialized workspaces
type: specification
status: accepted
implementation: partial
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - projects
  - storage
  - multi-project
  - object-store
---

# Goal

Open Cine Toaster productions from arbitrary local locations today and support
mounted or object-store-backed sources later without making Project Core depend
on storage-provider semantics.

# Context

Built-in demos are source templates distributed with Cine Toaster. Once copied,
their productions are ordinary external projects. They do not prove that the
application can register a project created independently, detect two locations
claiming the same identity, or materialize a source such as
`s3://studio/film-a`.

Local filesystems and object stores also have materially different behavior.
Object stores do not provide ordinary atomic rename, directory locks, in-place
writes, or filesystem watching. Passing an object-store URI into `Path` APIs
would leak those differences into every domain operation.

# Project locator

`ProjectLocator` identifies where a project source can be accessed. It is not
the identity of the film.

Required fields:

```text
scheme
uri
```

Initial schemes are:

```text
file       local directory or mounted filesystem
s3         future S3-compatible object store
gs         future Google Cloud Storage
```

Rules:

- `file` locators use normalized absolute `file://` URIs.
- Object-store locators identify a bucket and project prefix, not credentials.
- Signed URLs, access keys, session tokens, and local cache paths never appear
  in a persisted locator.
- Two locators may refer to copies of the same project; canonical project
  identity comes from `project.toml`.

# Project source adapter

A `ProjectSourceAdapter` translates a locator into a local materialized
workspace. Its logical operations are:

```text
probe(locator)
materialize(locator)
status(workspace)
pull(workspace, expected_source_revision)
push(workspace, expected_source_revision)
close(workspace)
```

The first implementation supports only `file`. It validates and returns the
external directory directly; it does not copy the project into the application.
Mounted local, NAS, and FUSE paths use the same contract while retaining their
platform-specific failure behavior.

Object-store adapters are future implementations. They download metadata and
required assets into a controlled local workspace and synchronize explicitly.

# Materialized project

`MaterializedProject` is the filesystem root used by Project Core.

Required fields:

```text
workspace_id
project_id
locator
local_root
source_revision
sync_state
read_only
materialized_at
```

Sync state is one of:

```text
clean
dirty
pull_required
push_required
conflict
offline
error
```

For a `file` locator, the external directory itself is the workspace and source
revision may be absent. For an object store, source revision is an ETag,
generation number, version ID, or adapter-defined immutable revision token.

# Authority and synchronization

Project Core always reads and writes a local filesystem project. For a local
source, that directory is the canonical production.

For a future object-store source, the materialized workspace is a checked-out
working production and the remote revision is its synchronization baseline.
Local canonical changes become `dirty` until explicitly pushed. Remote changes
require an explicit pull or conflict resolution. Neither side silently wins.

The object-store adapter must use conditional writes or versioning. If the
expected remote revision changed, synchronization enters `conflict`; it never
overwrites another writer through last-writer-wins behavior.

Derived caches remain separate from the materialized project. Deleting an
application cache must not delete unpushed canonical project changes.

# Project identity and registration

The stable identity is the non-empty `id` in `project.toml`. Paths and locators
can change without changing `project_id`.

The Application Layer Project Manager:

- may register several different project IDs simultaneously;
- treats opening the same project ID at the same normalized locator as
  idempotent;
- rejects the same project ID at a different locator as an identity conflict;
- never chooses a project from process-global active state;
- returns handles addressed explicitly by `project_id`;
- does not require projects to share a parent directory.

Rebinding a moved project inside a persistent registry will require an explicit
operation. The initial in-memory manager may simply be reconstructed and open
the new location, proving that identity survives the move.

# Object-store layout constraints

A future adapter must define a versioned layout rather than infer directories
from list operations. At minimum it needs:

- a small project manifest object discoverable without downloading all media;
- immutable or versioned canonical metadata objects;
- content-addressed or versioned large assets where practical;
- checksums and sizes;
- safe staging for uploads;
- a commit/publish marker tying one remote revision together;
- lazy media hydration and resumable transfer;
- explicit deletion and garbage-collection policy.

The project format may refer to stable logical asset IDs. Credentials and
temporary signed URLs remain Application Layer operational state.

# Security

- Normalize and validate local roots before registration.
- Do not infer trust from a `file://` scheme or mounted path.
- Keep source credentials in configured secret storage, not project files.
- Constrain a materialized workspace to its allocated root.
- Validate checksums before adopting downloaded canonical files.
- A read-only source may be browsed but canonical commands fail with a typed
  permission error before mutation.

# Initial local API

The first implementation exposes:

```text
ProjectLocator.from_path(path)
LocalProjectSource.open(locator)
ProjectManager.open_project(path_or_locator)
ProjectManager.get(project_id)
ProjectManager.list_projects()
ProjectManager.close_project(project_id)
```

It intentionally does not persist recent projects, define active UI project
state, watch files, or implement remote synchronization.

# Acceptance criteria

The local implementation conforms when:

- it opens a valid project created independently of built-in demos;
- unrelated directories and paths containing spaces are supported;
- two different project IDs can be registered simultaneously;
- the same project and locator can be opened idempotently;
- duplicate project IDs at different locators fail explicitly;
- moving a project preserves manifest identity in a reconstructed manager;
- missing, malformed, or incomplete manifests fail clearly;
- callers address handles by explicit project ID;
- no repository path or built-in-template assumption is required.

An object-store implementation additionally must prove conditional conflict
detection, interrupted transfer recovery, lazy media hydration, offline status,
credential isolation, and round-trip integrity against a real compatible
service such as MinIO before claiming S3 support.

# Deferred choices

- operational database schema for persisted project registrations;
- explicit rebind workflow for a moved open project;
- object-store manifest and commit-object format;
- encryption and retention of materialized workspaces;
- cache eviction while dirty or offline;
- collaboration and multi-writer merge semantics;
- direct media streaming versus local proxy hydration.
