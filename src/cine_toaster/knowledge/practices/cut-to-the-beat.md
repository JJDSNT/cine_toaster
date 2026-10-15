+++
id = "cut-to-the-beat"
title = "A piece cut to music counts its shots in beats"
domain = "editing"
status = "convention"
enforced_by = ["beats_invalid", "beats_missing", "beats_mixed", "beats_music_not_at_start", "beats_past_end", "beats_without_music", "join_off_beat"]
evidence = ["CT-0067"]
+++

When a piece is cut to music, the music decides where the cuts fall. Written
in seconds, a cut lands on the beat only by arithmetic someone did once; the
next change of one shot moves every cut after it, and nobody notices until it
is heard. Written in beats, each cut is tied to the music and survives the
changes around it.

A straight cut falls on the beat. A transition is felt at its middle, so its
middle falls on the beat and it takes half of its length from each shot.

The beats are heard in the recording and kept beside it, with the checksum of
the file they were heard in: another mix of the track is another set of
beats. A transition longer than half a shot it joins is shortened when the
cut is made, and every join after it leaves the beat; that is said before the
cut is made, not discovered in it.
