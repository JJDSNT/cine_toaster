# The screenplay editor

`/app/script.html`, or **Open in the screenplay editor** in the Script room,
edits the production's screenplay: the file `paths.script` names, or each file
of a screenplay split by act or arc, in tabs.

- **Your text, exactly.** Saving writes what you typed, byte for byte. Nothing
  is parsed and written back, so notes, boneyard, sections and spacing you did
  not touch stay as they were. A file's line endings and byte-order mark are
  kept (ADR 0016).
- **No silent overwrite.** If the file changed since you opened it -- another
  editor, a generator, a `git pull` -- saving is refused and nothing is
  written. Reload to see the other version.
- **What the save did to the film.** Shots quote the screenplay to say what
  they cover (SPEC-0006). After a save, the right-hand panel lists links that
  broke or recovered: a quoted line that no longer exists, a line that
  drifted, dialogue no shot covers.
- **The outline** lists sections and scenes, and marks each scene heading
  with the production scenes linked to it. Click one to jump.
- `Ctrl`/`Cmd`+`S` saves.

A screenplay made by a tool is opened **read only**. Declare it in
`project.yaml`, so an edit is never lost to the next generation:

```yaml
screenplay_generated_by: roteiro/v4/monta_v4.py
```

Writing to the breakdowns or to `project.yaml` is not possible here: only
screenplay files are editable.
