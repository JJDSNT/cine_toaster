# ADR 0002: Keep a headless runtime outside the renderer

Status: accepted

## Context

Cine Toaster is expected to support browser and desktop interfaces, CLI and API
access, multiple projects, long-running media jobs, agent sessions, and external
processes. The current implementation is a working Python CLI and local HTTP
runtime. The proposed desktop direction uses React/Vite and Tauri.

Renderer processes are unsuitable as the sole owner of canonical writes, jobs,
locks, or application-global state because navigation, reload, and window
lifecycle may replace them. Rewriting the current Core in TypeScript solely to
share the renderer language would also discard working behavior before a
domain-command boundary exists.

## Decision

Cine Toaster has a headless Application Runtime containing application services
and the Project Core. Interfaces communicate through versioned commands,
queries, and subscriptions.

The existing Python runtime remains the initial implementation. React/Vite is a
strong frontend candidate and Tauri 2 is a strong desktop-shell candidate.
Tauri may supervise and package the runtime as a sidecar, but desktop and Rust
code do not duplicate film-domain behavior.

Transport is not fixed by this decision. Local HTTP/SSE, Tauri IPC, or another
transport may implement the same application contracts after validation.

## Consequences

- CLI, browser, desktop, and agents can reuse one domain implementation.
- Renderer reload and active-project changes do not define job lifetime.
- Desktop packaging must solve runtime supervision and sidecar distribution.
- Python remains an intentional initial runtime choice, not an immutable
  architectural dependency.
- Moving the Core to TypeScript or Rust requires a new ADR and behavior-parity
  migration plan.
