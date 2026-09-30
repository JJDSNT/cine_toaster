# Claude Code on a film, through Cine Toaster

Connect Claude Code to a production, and it works through Cine Toaster's
own commands instead of editing files and writing scripts:

```bash
make install-mcp
claude mcp add cine-toaster -- toast mcp ~/confyui/singular --env-file ~/confyui/.env
```

`--env-file` is needed only for paid generation; the credentials are read,
never printed. `toast doctor` reports whether the MCP server can run.

## What it can do

- **Read:** `film_overview`, `read_scene`, `read_shot`, `read_cast`,
  `search_screenplay`, `read_budget`, `check_scene`, `list_locations`,
  `list_camera_moves`, `plan_generation`, `plan_picture`, `job_status`.
- **Decide over the breakdown** (recorded as `claude-code`, an agent, with
  the reason given in `why`): `set_cut`, `set_cuts` (all or none),
  `clear_cut`, `set_reference`, `clear_reference`, `set_voice_in_cut`.
- **Make things:** `start_workflow`, `resume_workflow`, `assemble_scene`,
  `slice_block`, `revoice_take`; follow a job with `wait_for_job`, which
  brings what it made into the film, or stop it with `cancel_job`.
- **Pay:** `generate` and `make_picture` need `max_usd` at or above the
  estimate `plan_generation` or `plan_picture` gives. The budget ceiling
  (`toast budget`) holds whatever is passed.

## What it cannot do

Approving or refusing a master picture, choosing a take and approving the
storyboard are the director's; no tool does them. No tool writes a
breakdown or the screenplay. A refused action comes back as `refused` with
the reason, and nothing is changed.

Everything it decides appears in the control room's history, where it can
be undone like any other decision. See ADR 0020.
