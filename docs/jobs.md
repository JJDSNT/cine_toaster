# Jobs

Renders run as **jobs**. A job keeps running if you leave the page, reload
it, or switch production. Its result waits in a staging area until you
**adopt** it into the production. Adoption never replaces an existing file
unless you confirm.

```bash
toast previs <project> SC-030 P2            # a job in the foreground; adopts to renders/previs/
toast build <project> --output reel.mp4     # the same, for the whole reel
toast slice <project> 1-02A 1               # a generation block's clip -> one take per shot
toast generate <project> 1-02A 2 --dry-run  # a paid block generation, within the budget (docs/generation.md)
toast assemble <project> SC-030             # a new, kept version of the scene from its chosen takes
toast jobs list [<project>]
toast jobs cancel <job>                     # works from any shell
toast jobs retry <job>                      # a new attempt with the same parameters
toast jobs adopt <job> [--overwrite]
```

In the control room, "Render video" on a shot's previs starts a job, and the
jobs tray in the corner shows progress, with cancel, retry and adopt.

Job records live in `~/.local/state/cine-toaster/` (or `$XDG_STATE_HOME`).
Deleting them loses job history, never the film. If the program that ran a
job dies, the next one to start marks the job **interrupted** and stops any
encoder it left behind. Work does not continue after the application exits.
See SPEC-0008.
