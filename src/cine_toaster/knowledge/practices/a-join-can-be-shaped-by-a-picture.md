+++
id = "a-join-can-be-shaped-by-a-picture"
title = "A join shaped by a picture says which picture, and it is there"
domain = "editing"
status = "convention"
enforced_by = ["transition_input_missing", "transition_input_outside", "transition_matte_invalid"]
evidence = ["SPEC-0011"]
+++

A wipe drawn by a formula has the shape of the formula. A wipe drawn by a
picture -- smoke, ink, a splash, an object crossing the frame -- has the shape
of the picture, and that is what the Video Toaster's organic wipes were. The
picture is the matte: where it is white the next shot is seen.

A still matte gives the order in which the frame changes; a moving matte is
the change itself, frame by frame. Either way the two shots keep playing
through it. An overlay is a picture with transparency that rides the join on
top, like the Toaster's animated objects.

A matte or overlay named on a join belongs to the production and must be
there. A missing one would leave the join without the shape the editor chose,
and the cut would not say why it looks wrong.

The matte may also be drawn rather than found: a gradient (a clock, a
diamond, a circle) or a noise, written on the join (`matte: {noise: {kind:
perlin, scale: 4}}`). It is part of the join's own drawing, and a generator
that cannot be drawn is refused when the scene loads.
