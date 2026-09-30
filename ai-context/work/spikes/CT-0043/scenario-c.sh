#!/bin/bash
# C: the checkpoint store is lost while a gate waits; the gate is decided anyway.
. "$(dirname "$0")/run.sh"
echo "1 start:"; graph start t1
rm -f cp.sqlite*; echo "2 checkpoints deleted"
decide "$S/film" approved 0
echo "3 resume the same thread:"; graph resume t1 2>&1 | tail -1
echo "4 start again, new thread:"; graph start t2
echo "sent: $(tr '\n' ' ' < sent.log)"
