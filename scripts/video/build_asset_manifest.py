#!/usr/bin/env python3
"""Write scripts/video/assets.json: every generated asset the sim video can use.

Park names and cities come from data/reference/mlb_teams_2026.json (MLB Stats
API). Nothing here is generated; the manifest lists the slots to fill in
Higgsfield and whether each one already exists on disk.

  python3 scripts/video/build_asset_manifest.py [--plates DIR] [--clips DIR]
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import sim_reference as ref  # noqa: E402

DESIGN = os.path.expanduser("~/Desktop/sport-info-DESIGN")
DEFAULT_PLATES = os.path.join(DESIGN, "plates", "mlb")
DEFAULT_CLIPS = os.path.join(DESIGN, "clips", "mlb")
MANIFEST = os.path.join(HERE, "assets.json")

PLATE_PROMPT = ("3/4 aerial isometric view of {park}, {city}, baseball stadium, detailed vintage copperplate "
                "engraving, fine crosshatching and linework, single ink colour on plain off-white paper, "
                "isolated object, no text, no logos, no people, even lighting, centred")
CLIP_PROMPT = ("Image-to-video from the input plate of {park}, {city}. Slow aerial push-in and gentle orbit "
               "toward home plate, ending on a steady 3/4 view that matches the input framing. Keep the "
               "copperplate engraving look and the single ink on off-white paper exactly as in the input; "
               "line work stays crisp, no photoreal textures, no text, no logos, no people, no scoreboard "
               "content, no camera shake.")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def find_plate(plates_dir, abbr):
    """Newest non-raw plate for a team: {ABBR}-*.png, skipping *raw* / *compare*."""
    if not plates_dir or not os.path.isdir(plates_dir):
        return None
    c = [p for p in glob.glob(os.path.join(plates_dir, f"{abbr}-*.png"))
         if not re.search(r"raw|compare", os.path.basename(p))]
    return sorted(c)[-1] if c else None


def find_clip(clips_dir, abbr):
    if not clips_dir or not os.path.isdir(clips_dir):
        return None
    c = sorted(glob.glob(os.path.join(clips_dir, f"{abbr}-*.mp4")) + glob.glob(os.path.join(clips_dir, f"{abbr}.mp4")))
    return c[-1] if c else None


def build(plates_dir=DEFAULT_PLATES, clips_dir=DEFAULT_CLIPS):
    teams = ref.teams()
    plates, clips = [], []
    for abbr, t in sorted(teams.items()):
        park, city = t["venue"], f"{t['venue_city']}, {t['venue_state']}"
        refs_dir = os.path.join(DESIGN, "reference", "stadiums", "mlb", abbr)
        found_refs = sorted(glob.glob(os.path.join(refs_dir, "*.jpg")) + glob.glob(os.path.join(refs_dir, "*.png")))
        plate = find_plate(plates_dir, abbr)
        clip = find_clip(clips_dir, abbr)
        plates.append({
            "slot": f"plates/mlb/{abbr}-{slug(park)}.png",
            "team": abbr, "park": park, "venue_id": t["venue_id"], "city": city,
            "kind": "still", "aspect": "4:3", "min_size": "2400x1792",
            "used_in": "beat 1: stadium cycle (0.2-0.55 s cut) or landing (1.5 s push-in) when this is the home park",
            "status": "exists" if plate else "missing", "path": plate,
            "prompt": PLATE_PROMPT.format(park=park, city=city),
            "image_input": found_refs or f"save 2-5 real 3/4 aerial photos (Wikimedia Commons, check licence) to {refs_dir}/ and pass one as the image input",
            "post": "isolate the ink to one colour in code (TEAM_COLORS) on cream #F3ECDC, like PHI v2",
        })
        clips.append({
            "slot": f"clips/mlb/{abbr}-flyover.mp4",
            "team": abbr, "park": park, "venue_id": t["venue_id"], "city": city,
            "kind": "video", "aspect": "4:5 (1080x1350); 1:1 or 9:16 also accepted, centre-cropped",
            "duration_s": 3.0, "fps": "24-30",
            "used_in": "beat 1: first 0.2-0.55 s as a cycle cut; first 1.5 s as the landing shot when home park",
            "status": "exists" if clip else "missing", "path": clip,
            "prompt": CLIP_PROMPT.format(park=park, city=city),
            "image_input": f"plates/mlb/{abbr}-{slug(park)}.png (generate the plate first)",
        })
    return {
        "_about": "Generated-asset slots for scripts/video/render_sim_video.py. Park names/cities from "
                  "data/reference/mlb_teams_2026.json (MLB Stats API). Text, numbers and logos are never "
                  "generated: the renderer typesets them.",
        "video": {"size": "1080x1350", "aspect": "4:5", "fps": 30, "codec": "H.264 yuv420p", "duration_s": 12},
        "search": {"plates_dir": plates_dir, "clips_dir": clips_dir,
                   "plate_match": "{ABBR}-*.png, newest, skipping *raw*/*compare*",
                   "clip_match": "{ABBR}-*.mp4 or {ABBR}.mp4"},
        "fallback": "Any park with no plate or clip is drawn by code as a to-scale fence/diamond outline "
                    "from its MLB Stats API fieldInfo, in the team ink on cream.",
        "plates": plates,
        "clips": clips,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", default=DEFAULT_PLATES)
    ap.add_argument("--clips", default=DEFAULT_CLIPS)
    a = ap.parse_args()
    m = build(a.plates, a.clips)
    json.dump(m, open(MANIFEST, "w"), indent=1, ensure_ascii=False)
    have = [p["team"] for p in m["plates"] if p["status"] == "exists"]
    print(MANIFEST, f"plates present: {have or 'none'}; clips present: "
          f"{[c['team'] for c in m['clips'] if c['status'] == 'exists'] or 'none'}")
