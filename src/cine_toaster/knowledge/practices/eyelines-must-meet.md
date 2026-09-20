+++
id = "eyelines-must-meet"
title = "Each character looks toward their interlocutor"
domain = "continuity"
status = "convention"
enforced_by = ["eyeline_mismatch", "eyeline_subject_missing"]
+++

In a conversation, a shot puts the absent character somewhere off frame. If the
close on A places B to the right of frame, the reverse on B must place A to the
left. When both land on the same side, the two appear to look the same way
rather than at one another.

This is the mistake that survives every individual review, because each shot is
correct on its own and only the pair is wrong. It is also the one a text prompt
will not reliably fix: the direction of a gaze follows the starting image more
than the words.

Declare `subject` and `looks_at` on the shot and the geometry answers it before
anything is generated. Put the two frames side by side afterwards anyway.
