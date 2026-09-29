+++
id = "movement-is-derived-from-positions"
title = "Name the move you meant; the positions say the move you wrote"
domain = "camera"
status = "convention"
enforced_by = ["move_kind_mismatch", "move_value_unknown"]
evidence = ["SPEC-0005"]
+++

A dolly-in and a zoom-in both make the subject bigger and are not the same shot:
the dolly changes perspective, the zoom only crops. A truck and a pan both slide
the background and are not the same shot either. Written as prose, the two are
easily confused, and a generator will pick one for you.

The start and end positions decide which move it is. When the author also names
the move, the two must agree. A disagreement is a warning because either can be
the mistake: the name may be loose, or the end position may be in the wrong
place.

Tilt is the exception. Aim is a point on the plan, so a vertical move of the
lens cannot be seen in the geometry and is taken as declared.

Speed, rig and kind are closed vocabularies. A value outside them is an error
rather than a guess: "slwo" must not quietly become a steady move.
