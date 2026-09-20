---
id: CTX-DEVELOPMENT-FRONTEND
title: Frontend development
type: guide
status: active
owner: project
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - development
  - frontend
  - desktop
---

# Frontend development

## Current UI

The existing vanilla HTML, CSS, and JavaScript control room is a useful product
prototype. It demonstrates production-oriented rooms, scene navigation, review
queues, file browsing, media serving, and transition previews.

Preserve it until a React replacement reaches behavior parity for the migrated
room. Do not pause the first canonical write merely to create a new frontend.

## Target direction

React, TypeScript, and Vite are the preferred candidates for the next sustained
visual interface. Tauri 2 is the preferred desktop-shell candidate. The
renderer consumes a versioned Application API and remains a projection over
authoritative project state.

Tauri responsibilities are limited to desktop lifecycle, native dialogs,
permissions, safe process supervision, and OS integration. Film-domain logic
stays in the headless runtime.

## Interaction principles

- Organize the interface around production rooms and decisions, not the
  filesystem tree.
- Treat generate, preview, compare, choose, and refine as a continuous workflow.
- Keep the current project and global background activity simultaneously
  visible where useful.
- Make human gates actionable outside chat.
- Keep agent navigation typed and optional through `Follow Agent`.
- Display provider identity where operationally relevant without making it the
  domain concept shown to the user.

## Desktop and browser modes

The browser client and desktop renderer should reuse the same query, command,
and subscription contracts. Tauri-specific calls stay behind a small host
adapter so ordinary interface development and tests can run in a browser.

Do not expose unrestricted shell or filesystem primitives to renderer code.
Open-project access and process commands use explicit scoped capabilities.

## Spikes

Before selecting a screenplay editor, prove screenplay-specific editing and
navigation rather than generic text editing. Before selecting a preview engine,
measure synchronization, seeking, frame stepping, A/B switching, CPU/GPU use,
and behavior with representative proxies.

Do not describe browser playback as frame-accurate until measured against known
media and timecode.
