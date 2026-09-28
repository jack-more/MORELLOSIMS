#!/usr/bin/env python3
"""MorelloSims sim video: stadium cycle -> blueprint parse -> flip to the card.

12 s, 1080x1350 (4:5), 30 fps, H.264. Every frame is drawn with PIL and piped
to ffmpeg. All text, numbers and logos are typeset here from sourced data.

  python3 scripts/video/render_sim_video.py --pick-id 2026-09-26-mlb-TB-PHI-ml \
      [--plates DIR] [--clips DIR] [--out PATH] [--stills DIR] [--settled]

Beats
  0.0-3.7  stadium cycle: cuts through other parks, decelerating, then lands on
           the game's park with a slow push-in. Each park uses, in order:
           a flyover clip (--clips, {ABBR}-*.mp4) > an engraved plate
           (--plates, {ABBR}-*.png) > a to-scale outline drawn from the park's
           MLB Stats API fence distances. See scripts/video/assets.json.
  3.7-4.4  the plate shrinks into the card stock, the blue prints down over it
  4.4-9.0  blueprint parse (render_card_back.CardBack): park line work draws
           on, lineups type on, run distribution accumulates, WP locks
  9.0-9.9  3D card flip to the series card front (render_series_card.render)
  9.9-12   hold on the front; the last frame is the card, pixel for pixel

Numbers: see render_card_back.py. Projected runs and WP are stored model
output; the run distribution is derived from them (seeded NB draws).
"""

import argparse
import glob
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from render_cards_v2 import REPO, font, text_w, fit_font, TEAM_COLORS, hexrgb  # noqa: E402
from render_series_card import load_picks, render as render_front, team_ref, BG, CREAM  # noqa: E402
import render_card_back as rb  # noqa: E402
import sim_reference as ref  # noqa: E402
from build_asset_manifest import find_plate, find_clip, DEFAULT_PLATES, DEFAULT_CLIPS  # noqa: E402

FPS = 30
VW, VH = 1080, 1350
DURATION = 12.0

T_LAND = 2.2          # cycle ends, landing on the home park
T_SHRINK = 3.7        # plate -> card stock
T_PRINT = 4.0         # blue prints down
T_PARSE = 4.4
T_FLIP = 9.0
T_FLIP_END = 9.9
CYCLE_DURS = [0.20, 0.20, 0.22, 0.25, 0.30, 0.42, 0.61]      # decelerating cuts, sum = 2.2 s


def ease(t):
    return rb.ease(t)


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ffmpeg_bin():
    exe = shutil.which("ffmpeg")
    if exe:
        try:
            r = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and "libx264" in r.stdout:
                return exe
        except Exception:
            pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("no working ffmpeg with libx264: `pip install imageio-ffmpeg` or fix the system ffmpeg")


# ── beat 1: park "plates" ──────────────────────────────────────────────────

def plate_ink(img):
    """Median colour of the saturated ink pixels in an engraved plate."""
    a = np.asarray(img.convert("RGB").resize((400, 300)), dtype=np.int16).reshape(-1, 3)
    sat = a.max(1) - a.min(1)
    ink = a[(sat > 90) & (a.min(1) < 140)]
    if len(ink) < 50:
        return None
    lum = ink.sum(1)
    solid = ink[lum <= np.percentile(lum, 30)]           # the solid strokes, not the hatching
    return tuple(int(v) for v in np.median(solid, axis=0))


def crop_to_ink(img, pad=0.04):
    """Trim the plate's empty paper so the park fills the art box."""
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    sat = a.max(2) - a.min(2)
    mask = sat > 60
    rows, cols = np.where(mask.any(1))[0], np.where(mask.any(0))[0]
    if not len(rows):
        return img
    # ignore sparse stray pixels: keep rows/cols carrying real ink
    rsum, csum = mask.sum(1), mask.sum(0)
    rows = np.where(rsum > rsum.max() * 0.02)[0]
    cols = np.where(csum > csum.max() * 0.02)[0]
    y0, y1, x0, x1 = rows[0], rows[-1], cols[0], cols[-1]
    py, px = int((y1 - y0) * pad), int((x1 - x0) * pad)
    return img.crop((max(0, x0 - px), max(0, y0 - py), min(img.width, x1 + px), min(img.height, y1 + py)))


def outline_art(abbr, ink, box=(1000, 720)):
    """Fallback art: the park's fence and diamond, to scale, from fieldInfo."""
    v = ref.venue_for_team(abbr)
    knots = rb.fence_knots(v["fieldInfo"])
    ad = rb.fence_curve(knots)
    fence = [rb.polar(a, d) for a, d in ad]
    S = 2
    bw, bh = box[0] * S, box[1] * S
    ys = [y for _, y in fence]
    xs = [abs(x) for x, _ in fence]
    k = min((bh - 70 * S) / max(ys), (bw - 150 * S) / (2 * max(xs)))
    hx, hy = bw / 2, bh - 30 * S
    P = lambda x, y: (hx + x * k, hy - y * k)  # noqa: E731
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lf, rf = knots[0], knots[-1]
    # hatched fair territory, engraving-ish: parallel strokes clipped to the fan
    poly = [P(0, 0)] + [P(x, y) for x, y in fence] + [P(0, 0)]
    m = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    hatch = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for x in range(-bh, bw, 9 * S):
        hd.line((x, bh, x + bh, 0), fill=ink + (70,), width=S)
    hatch.putalpha(Image.composite(hatch.getchannel("A"), Image.new("L", (bw, bh), 0), m))
    img.alpha_composite(hatch)
    d.line([P(x, y) for x, y in fence], fill=ink, width=6 * S, joint="curve")
    d.line((P(0, 0), P(*rb.polar(lf[0], lf[1]))), fill=ink, width=3 * S)
    d.line((P(0, 0), P(*rb.polar(rf[0], rf[1]))), fill=ink, width=3 * S)
    b = 90 / math.sqrt(2)
    infield = [P(0, 0), P(b, b), P(0, 2 * b), P(-b, b)]
    d.polygon(infield, fill=CREAM, outline=ink, width=3 * S)
    arc = [P(*(np.array(rb.polar(a, 95)) + np.array((0, 60.5)))) for a in np.arange(-72, 72.1, 2)]
    d.line(arc, fill=ink, width=3 * S)
    f = font("cond", 30 * S)
    for a, dist, _ in knots:
        x, y = P(*rb.polar(a, dist + 30 / k * S))
        t = str(int(dist))
        bb = d.textbbox((0, 0), t, font=f)
        d.text((x - (bb[2] - bb[0]) / 2 - bb[0], y - (bb[3] + bb[1]) / 2), t, font=f, fill=ink)
    return img.resize(box, Image.LANCZOS)


class ParkPlate:
    """One park's beat-1 screen: cream stock, team name above, park below,
    art (clip frames, plate PNG or code outline) in between."""

    ART_BOX = (50, 350, 1030, 1070)

    def __init__(self, abbr, plates_dir, clips_dir, footer=None):
        self.abbr = abbr
        t = ref.team(abbr)
        self.park = t["venue"]
        _, self.name, _ = team_ref(abbr)
        self.plate_path = find_plate(plates_dir, abbr)
        self.clip_path = find_clip(clips_dir, abbr)
        self.frames = None
        self.art = None
        ink = hexrgb(TEAM_COLORS.get(abbr, "#1C1816"))
        if self.clip_path:
            self.kind = "clip"
        elif self.plate_path:
            self.kind = "plate"
            self.art = crop_to_ink(Image.open(self.plate_path).convert("RGB"))
            ink = plate_ink(self.art) or ink
        else:
            self.kind = "outline"
        self.ink = ink
        if self.kind == "outline":
            bw, bh = self.ART_BOX[2] - self.ART_BOX[0], self.ART_BOX[3] - self.ART_BOX[1]
            self.art = outline_art(abbr, ink, (bw, bh))
        self.footer = footer
        self.type_layer = self._type()

    def _type(self):
        S = 2
        img = Image.new("RGBA", (VW * S, VH * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        on_clip = self.kind == "clip"
        col = CREAM if on_clip else self.ink
        top = "MORELLO SIMS · 2026 MLB SERIES"
        f = font("mono_b", 24 * S)
        d.text(((VW * S - text_w(d, top, f)) / 2, 96 * S), top, font=f, fill=col)
        nf = fit_font(d, self.name, "black", 112 * S, (VW - 160) * S, min_size=60 * S)
        bb = d.textbbox((0, 0), self.name, font=nf)
        d.text(((VW * S - (bb[2] - bb[0])) / 2 - bb[0], 180 * S), self.name, font=nf, fill=col)
        park = f"·  {self.park.upper()}  ·"
        pf = fit_font(d, park, "mono_b", 34 * S, (VW - 140) * S, min_size=22 * S)
        d.text(((VW * S - text_w(d, park, pf)) / 2, 1100 * S), park, font=pf, fill=col)
        if self.footer:
            ff = font("mono_b", 24 * S)
            d.text(((VW * S - text_w(d, self.footer, ff)) / 2, 1196 * S), self.footer, font=ff, fill=col)
        return img.resize((VW, VH), Image.LANCZOS)

    def load_clip(self, tmp, seconds):
        """Decode the first `seconds` of the clip to frames, cover-cropped to 4:5."""
        if self.frames is not None or not self.clip_path:
            return
        out = os.path.join(tmp, f"clip-{self.abbr}")
        os.makedirs(out, exist_ok=True)
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", self.clip_path, "-t", f"{seconds:.2f}",
                        "-vf", f"fps={FPS},scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH}",
                        os.path.join(out, "%04d.png")], check=True)
        self.frames = sorted(glob.glob(os.path.join(out, "*.png")))
        if not self.frames:                       # unreadable clip -> fall back
            self.kind = "plate" if self.plate_path else "outline"
            if self.kind == "plate":
                self.art = crop_to_ink(Image.open(self.plate_path).convert("RGB"))
            else:
                bw, bh = self.ART_BOX[2] - self.ART_BOX[0], self.ART_BOX[3] - self.ART_BOX[1]
                self.art = outline_art(self.abbr, self.ink, (bw, bh - 60))
            self.type_layer = self._type()

    def frame(self, t_local, zoom):
        """t_local: seconds into this park's shot; zoom: >=1 push-in on the art."""
        if self.kind == "clip" and self.frames:
            i = min(int(t_local * FPS), len(self.frames) - 1)
            img = Image.open(self.frames[i]).convert("RGBA")
            # soft top/bottom scrim so the cream type reads on any footage
            scrim = Image.new("L", (1, VH))
            for y in range(VH):
                e = max(0.0, 1 - y / 360) if y < VH / 2 else max(0.0, 1 - (VH - y) / 300)
                scrim.putpixel((0, y), int(170 * e ** 1.6))
            dark = Image.new("RGBA", (VW, VH), (22, 20, 18, 255))
            dark.putalpha(scrim.resize((VW, VH)))
            img.alpha_composite(dark)
        else:
            img = Image.new("RGBA", (VW, VH), CREAM + (255,))
            x0, y0, x1, y1 = self.ART_BOX
            bw, bh = x1 - x0, y1 - y0
            art = self.art
            k = min(bw / art.width, bh / art.height) * zoom
            w, h = int(art.width * k), int(art.height * k)
            a = art.resize((w, h), Image.LANCZOS).convert("RGBA")
            img.alpha_composite(a, (int(x0 + (bw - w) / 2), int(y0 + (bh - h) / 2)))
        img.alpha_composite(self.type_layer)
        return img


# ── beat 3: flip ───────────────────────────────────────────────────────────

def perspective_coeffs(dst, src):
    """PIL PERSPECTIVE data mapping output points `dst` back to input `src`."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def flip_frame(back_card, front_card, shadow, u):
    """u in [0,1]: 0 = back facing, 1 = front facing. Rotation about the card's
    vertical axis with perspective and a slight lift."""
    theta = math.pi * ease_in_out(u)
    card, ang = (back_card, theta) if theta <= math.pi / 2 else (front_card, theta - math.pi)
    lift = 1 - 0.16 * math.sin(math.pi * ease_in_out(u))      # pull back so the near edge stays in frame
    cx0, cy0, cx1, cy1 = [v / 2 for v in rb.CARD]                   # 1x coords
    hw, hh = (cx1 - cx0) / 2, (cy1 - cy0) / 2
    cx, cy = VW / 2, VH / 2
    f = 3200.0
    SS = 2

    def proj(x, y):
        X, Z = x * math.cos(ang), x * math.sin(ang)
        k = f / (f + Z) * lift
        return ((cx + X * k) * SS, (cy + y * k) * SS)

    dst = [proj(-hw, -hh), proj(hw, -hh), proj(hw, hh), proj(-hw, hh)]
    src = [(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)]
    out = Image.new("RGBA", (VW, VH), BG + (255,))
    # shadow narrows with the card's projected width
    wfrac = max(abs(math.cos(ang)), 0.04)
    sh = shadow.resize((max(1, int(VW * wfrac)), VH), Image.LANCZOS)
    out.alpha_composite(sh, (int((VW - sh.width) / 2), 0))
    if abs(math.cos(ang)) > 0.012:
        big = card.resize((VW * SS, VH * SS), Image.BICUBIC)
        src2 = [(x * SS, y * SS) for x, y in src]
        warped = big.transform((VW * SS, VH * SS), Image.PERSPECTIVE, perspective_coeffs(dst, src2),
                               Image.BICUBIC)
        out.alpha_composite(warped.resize((VW, VH), Image.LANCZOS))
    return out.convert("RGB")


# ── timeline ───────────────────────────────────────────────────────────────

def cycle_teams(pick, plates_dir, clips_dir):
    """Parks to cut through before landing: ones with real art first, then a
    seeded pick of the rest; the away team's park goes last."""
    home, away = pick["home"], pick["away"]
    others = [a for a in ref.teams() if a not in (home, away)]
    rnd = random.Random(int(pick.get("game_pk") or 0))
    rnd.shuffle(others)
    others.sort(key=lambda a: 0 if (find_clip(clips_dir, a) or find_plate(plates_dir, a)) else 1)
    return others[: len(CYCLE_DURS) - 1] + [away]


def build(pick, plates_dir, clips_dir, out_path, stills_dir=None, settled=False):
    tmp = tempfile.mkdtemp(prefix="simvid-")
    when = datetime.strptime(pick["date"], "%Y-%m-%d").strftime("%b %-d").upper()
    footer = f"{pick['away']} @ {pick['home']} · {when} · {pick.get('game_time') or ''}".strip(" ·")
    cyc = [ParkPlate(a, plates_dir, clips_dir) for a in cycle_teams(pick, plates_dir, clips_dir)]
    land = ParkPlate(pick["home"], plates_dir, clips_dir, footer=footer)
    for p, dur in zip(cyc, CYCLE_DURS):
        p.load_clip(tmp, dur + 0.1)
    land.load_clip(tmp, T_SHRINK - T_LAND + 0.8)

    back = rb.CardBack(pick)
    shadow = rb.card_shadow()
    front_full = render_front(pick, settled=settled)                  # exact card, BG included
    front_card = front_full.convert("RGBA")
    front_card.putalpha(rb.card_mask())
    back_final = back.card()

    starts = np.concatenate([[0], np.cumsum(CYCLE_DURS)])
    n_frames = int(round(DURATION * FPS))
    still_at = {"beat1-landing": 3.30, "beat2-parse": 7.55, "beat3-flip": 9.40, "final": DURATION - 1 / FPS}
    still_frames = {int(round(t * FPS)): name for name, t in still_at.items()}
    still_frames[n_frames - 1] = "final"
    stills = {}

    cmd = [ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-crf", "16", "-preset", "slow", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def land_frame(t):
        zoom = 1.0 + 0.07 * ease_out((t - T_LAND) / (T_SHRINK - T_LAND + 0.7))
        return land.frame(t - T_LAND, zoom)

    for fi in range(n_frames):
        t = fi / FPS
        if t < T_LAND:
            i = int(np.searchsorted(starts, t, side="right")) - 1
            p = cyc[i]
            tl = t - starts[i]
            img = p.frame(tl, 1.0 + 0.03 * tl / CYCLE_DURS[i]).convert("RGB")
        elif t < T_SHRINK:
            img = land_frame(t).convert("RGB")
        elif t < T_PARSE:
            # the landing shot shrinks into the card stock, then the blue prints down
            plate = land_frame(t)
            u = ease_in_out((t - T_SHRINK) / (T_PRINT - T_SHRINK))
            x0, y0, x1, y1 = [v / 2 for v in rb.CARD]
            rx0, ry0 = x0 * u, y0 * u
            rx1, ry1 = VW - (VW - x1) * u, VH - (VH - y1) * u
            sw, sh_ = int(rx1 - rx0), int(ry1 - ry0)
            frame = Image.new("RGBA", (VW, VH), BG + (255,))
            sh = shadow.copy()
            sh.putalpha(sh.getchannel("A").point(lambda a: int(a * u)))
            frame.alpha_composite(sh)
            scaled = plate.resize((sw, sh_), Image.LANCZOS)
            m = Image.new("L", (sw * 2, sh_ * 2), 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, sw * 2 - 1, sh_ * 2 - 1), radius=int(54 * 2 * u), fill=255)
            frame.paste(scaled, (int(rx0), int(ry0)), m.resize((sw, sh_), Image.LANCZOS))
            if t >= T_PRINT:
                w = ease_in_out((t - T_PRINT) / (T_PARSE - T_PRINT))
                layer = back.card(field=0, wall=0, draws=0, lock=0)
                edge = int(rb.FRAME[1] / 2 + (rb.FRAME[3] - rb.FRAME[1]) / 2 * w)
                m2 = Image.new("L", (VW, VH), 0)
                ImageDraw.Draw(m2).rectangle((0, 0, VW, edge), fill=255)
                # cream stock is already there; only the printed area wipes in
                pr = Image.new("L", (VW, VH), 0)
                ImageDraw.Draw(pr).rounded_rectangle([v / 2 for v in rb.FRAME], radius=20, fill=255)
                mask = Image.fromarray(np.minimum(np.asarray(m2), np.asarray(pr)))
                frame.paste(layer, (0, 0), mask)
                fd = ImageDraw.Draw(frame)
                if w < 1:
                    fd.line((rb.FRAME[0] / 2, edge, rb.FRAME[2] / 2, edge), fill=(255, 255, 255), width=3)
            img = frame.convert("RGB")
        elif t < T_FLIP:
            u = t - T_PARSE
            field = u / 1.8
            wall = (u - 1.3) / 1.5
            draws = ((u - 2.0) / 2.0)
            draws = min(max(draws, 0), 1) ** 2.2
            lock = (u - 3.6) / 0.7
            img = rb.on_background(back.card(field=min(max(field, 0), 1), wall=min(max(wall, 0), 1),
                                              draws=draws, lock=min(max(lock, 0), 1)))
        elif t < T_FLIP_END:
            img = flip_frame(back_final, front_card, shadow, (t - T_FLIP) / (T_FLIP_END - T_FLIP))
        else:
            img = front_full
        if fi in still_frames:
            stills[still_frames[fi]] = img.copy()
        proc.stdin.write(img.tobytes())
        if fi % 30 == 0:
            print(f"  frame {fi}/{n_frames}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    shutil.rmtree(tmp, ignore_errors=True)

    if stills_dir:
        os.makedirs(stills_dir, exist_ok=True)
        order = ["beat1-landing", "beat2-parse", "beat3-flip", "final"]
        for i, name in enumerate(order, 1):
            path = os.path.join(stills_dir, f"still-{i}-{name}.png")
            stills[name].save(path)
            print(path)
    kinds = {p.abbr: p.kind for p in cyc + [land]}
    return kinds


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", required=True)
    ap.add_argument("--plates", default=DEFAULT_PLATES, help="dir of {ABBR}-*.png engraved plates")
    ap.add_argument("--clips", default=DEFAULT_CLIPS, help="dir of {ABBR}-*.mp4 flyover clips")
    ap.add_argument("--out", default=None, help="output .mp4 (default posters/v2/video/sim-{id}.mp4)")
    ap.add_argument("--stills", default=None, help="dir for the 4 still frames (default: next to --out)")
    ap.add_argument("--settled", action="store_true", help="flip to the settled (stamped) front")
    a = ap.parse_args()
    pick = next((p for p in load_picks() if p["id"] == a.pick_id), None)
    if not pick:
        raise SystemExit(f"pick id not found: {a.pick_id}")
    out = a.out or os.path.join(REPO, "posters", "v2", "video", f"sim-{pick['id']}.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    kinds = build(pick, a.plates, a.clips, out, a.stills or os.path.dirname(os.path.abspath(out)), a.settled)
    print(out)
    print("beat-1 sources:", ", ".join(f"{k}={v}" for k, v in kinds.items()))
