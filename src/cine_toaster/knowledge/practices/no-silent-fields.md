+++
id = "no-silent-fields"
title = "A field nothing reads is reported, never dropped"
domain = "format"
status = "convention"
enforced_by = ["shot_field_undeclared"]
+++

A breakdown accretes fields. Someone needs a light turned off in one shot and
writes `apaga_luz`; someone needs a character's body noted and writes `corpo`.
Each one was right at the moment it was written, and the application has no
opinion about any of them.

The danger is not the field. It is the silence. A key that nothing reads and
nothing reports looks identical, from the author's chair, to a key that works.
The author writes it, the shot generates, and the instruction was never applied.

This is the data version of a rule the production already paid to learn: a
command that does nothing must fail rather than succeed. Measured on a real
feature, 359 shots carried 56 distinct keys, eighteen of them used three times
or fewer; a schema that silently ignored the tail would have ignored most of
what the author was actually saying.

So the field is kept, shown, and reported until someone decides what it is:
declare it under `shot_fields` and it becomes part of the film's own
vocabulary, or move it into a field the schema knows and it becomes checkable.
