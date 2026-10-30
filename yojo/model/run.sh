#!/bin/bash
cd "$(dirname "$0")/.."
PY=../bl/bin/python
common="STATE=anim PANEL=6 RX=640 RY=800 SAMPLES=14 CAM_D=0.42"
for job in "cut open -118 -28 1" "cut lock -118 -28 1" "ext open -100 -90 0" "ext lock -100 -90 0"; do
  set -- $job; name=$1; seg=$2; cth=$3; tth=$4; clip=$5
  mkdir -p anim/$name-$seg
  env STATE=anim PANEL=6 RX=640 RY=800 SAMPLES=14 CAM_D=0.42 SEG=$seg CAM_TH=$cth TEXT_TH=$tth SLOT_TH=-60 CLIP=$clip \
      OUT=$PWD/anim/$name-$seg/f_ $PY mech.py > anim/$name-$seg.log 2>&1
  echo "finished $name-$seg $(ls anim/$name-$seg | wc -l) frames" >> anim/progress.txt
done
echo ALLDONE >> anim/progress.txt
