#!/bin/sh
# Run from this folder on the Mac (signed in to the Scale plan).  usage: ./run.sh 01-bags-backlit [cost|go]
# Always run with "cost" first and get a founder's yes before "go".
set -e
P="prompts/$1.txt"; MODE="${2:-cost}"
R="--image-references refs/mood-1-pale-arch-lab.png --image-references refs/mood-2-90s-lab.jpg --image-references refs/bag-1-seethru-over-lab.png --image-references refs/bag-2-over-white.png --image-references refs/bag-3-over-stripes.png --image-references refs/bag-4-over-provence.png --image-references refs/bag-5-front-print-flat.png --image-references refs/bag-6-crest-and-address.png --image-references refs/vial-rt3.png --image-references refs/label-rt3-rev4.png"
if [ "$MODE" = "go" ]; then
  higgsfield generate create gpt_image_2_6 --prompt "$(cat "$P")" $R --quality high --resolution 2k --aspect_ratio 9:16 --wait
else
  higgsfield generate cost gpt_image_2_6 --prompt "$(cat "$P")" $R --quality high --resolution 2k --aspect_ratio 9:16
fi
