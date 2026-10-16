# Claude Code on a film, through Cine Toaster

Connect Claude Code to a production, and it works through Cine Toaster's
own commands instead of editing files and writing scripts:

```bash
make install-mcp
toast new ~/films/my-film --title "My Film" --screenplay draft.fountain   # or any production
claude mcp add cine-toaster -- toast mcp ~/films/my-film --env-file ~/.config/cine-toaster/.env
```

`--env-file` is needed only for paid generation; the credentials are read,
never printed. `toast doctor` reports whether the MCP server can run.

## What it can do

- **Read:** `how_to_make_a_film` (the guide, [making-a-film.md](making-a-film.md)),
  `list_practices`, `read_practice`, `list_references`, `film_overview`, `read_scene`, `read_shot`, `read_cast`,
  `search_screenplay`, `read_budget`, `check_scene`, `list_locations`,
  `list_camera_moves`, `plan_generation`, `plan_picture`, `job_status`.
- **Decide over the breakdown** (recorded as `claude-code`, an agent, with
  the reason given in `why`): `set_cut`, `set_cuts` (all or none),
  `clear_cut`, `set_reference`, `clear_reference`, `set_voice_in_cut`.
- **Make things:** `start_workflow`, `resume_workflow`, `assemble_scene`,
  `slice_block`, `revoice_take`; follow a job with `wait_for_job`, which
  brings what it made into the film, or stop it with `cancel_job`.
- **Generate a reference:** `generate_reference` makes a picture through
  Codex (subscription quota) from a description and earlier references,
  kept as a reference asked by `claude-code`.
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
