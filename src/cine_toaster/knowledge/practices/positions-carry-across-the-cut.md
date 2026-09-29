+++
id = "positions-carry-across-the-cut"
title = "Where a shot leaves a character is where the next shot finds them"
domain = "continuity"
status = "convention"
enforced_by = ["cut_screen_flip", "framed_subject_missing", "unknown_mark", "movement_subject_missing"]
evidence = ["SPEC-0005", "CT-0022"]
+++

A character's position does not reset at the cut. If they cross to the stack in
one shot, the next shot finds them at the stack, unless the story skips time and
says so. Most continuity errors between generated clips are this: each shot is
generated from the scene's opening plan, so the character teleports back.

A character on the right of frame at the end of one shot and on the left at the
start of the next reads as a jump, even when the camera never crossed the line.

A shot that names who it is on, while its camera frames neither where they
start nor where they end, is framing an empty room.

Movement is declared, never read from the action text. A mark or subject the
geometry does not know is an error, because the check would otherwise be run
against a position that does not exist.

The Echo Chamber demo showed the gap this closes: its two-shot framed where
Mara ends her walk, the next shot framed where she began, and nothing could see
it while a character had one position for the whole scene.
