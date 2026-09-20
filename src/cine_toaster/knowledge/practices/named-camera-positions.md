+++
id = "named-camera-positions"
title = "Shots reuse named camera positions, they do not invent viewpoints"
domain = "continuity"
status = "convention"
enforced_by = ["unknown_camera"]
+++

A scene has a small set of fixed camera positions with names. Every shot says
which one it is from. Two shots of the same character from the same position cut
together; two from positions invented per shot do not.

This also gives every later stage something stable to hang on to: one master
image per position, one background per direction, one lens per angle.
