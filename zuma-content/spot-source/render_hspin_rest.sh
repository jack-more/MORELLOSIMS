#!/bin/sh
# Floating spin frames (transparent, 24 per turn) for the seven vials that did not have them yet: for the bounce video.
cd /tmp/claude-0/-home-user-MORELLOSIMS/28fcdcb0-1e78-54f5-bf93-2db9041de387/scratchpad/cyc
PY=../bpyenv/bin/python
for no in 02 08 06 10 07 12 03; do
  for k in $(seq 0 23); do kk=$(printf %02d $k); f=out15/hspin/$no-$kk.png
    [ -f "$f" ] || $PY vial.py floatspin:$k/24 $no $f 760 950 32 >/dev/null 2>&1
  done; echo "hspin $no done $(date +%H:%M)"
done
