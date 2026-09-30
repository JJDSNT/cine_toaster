#!/bin/bash
# A: start, ask again, approve the second version, finish -- each step a new process.
. "$(dirname "$0")/run.sh"
echo "1 start:";   graph start t1
echo "2";          decide "$S/film" changes_requested 0
echo "3 resume:";  graph resume t1
echo "4";          decide "$S/film" approved 1
echo "5 resume:";  graph resume t1
echo "sent: $(tr '\n' ' ' < sent.log)"
