#!/bin/bash
# encode the four segments, join open+lock, render HD stills for the spec
cd "$(dirname "$0")/.."
PY=../bl/bin/python
for v in cut ext; do
  ffmpeg -v error -y -framerate 24 -i anim/$v-open/f_%04d.png -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p anim/$v-open.mp4
  ffmpeg -v error -y -framerate 24 -i anim/$v-lock/f_%04d.png -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p anim/$v-lock.mp4
  # open segment, short dissolve, lock segment
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 anim/$v-open.mp4)
  off=$(python3 -c "print(round($d-0.35,3))")
  ffmpeg -v error -y -i anim/$v-open.mp4 -i anim/$v-lock.mp4 -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.35:offset=$off,format=yuv420p[o]" -map "[o]" -c:v libx264 -crf 16 -preset slow -movflags +faststart anim/$v.mp4
done
mkdir -p stills
for st in locked open pressed; do
  env STATE=$st PANEL=6 RX=1200 RY=1500 SAMPLES=40 CAM_D=0.42 CAM_TH=-118 TEXT_TH=-28 SLOT_TH=-60 CLIP=1 OUT=$PWD/stills/cut-$st.png $PY mech.py > stills/cut-$st.log 2>&1
done
for st in locked open; do
  env STATE=$st PANEL=6 RX=1200 RY=1500 SAMPLES=40 CAM_D=0.42 CAM_TH=-100 TEXT_TH=-90 SLOT_TH=-60 CLIP=0 OUT=$PWD/stills/ext-$st.png $PY mech.py > stills/ext-$st.log 2>&1
done
echo FINISHED > anim/finish.done
