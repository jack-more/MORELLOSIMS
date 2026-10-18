# An original 20-second bed for the ZUMA spot, synthesized from scratch: 120 BPM, E minor, cut to the picture.
# 0-1 TV static and power-on thunk; 1-15.5 groove (kick, clap, hats, saw bass, offbeat stabs, hits on the slams,
# riser into the star wipe); 15.2 tape-stop; 15.7 logo chord with a sparkle on the chrome sweep; fade to 20 s.
import numpy as np, wave
from scipy.signal import butter, lfilter

SR, DUR, BPM = 44100, 20.0, 120
BEAT = 60 / BPM
N = int(SR * DUR)
mix = np.zeros((N, 2))
rng = np.random.default_rng(7)
t_all = np.arange(N) / SR

def lp(sig, f, order=2): b, a = butter(order, min(f, SR / 2 - 100) / (SR / 2)); return lfilter(b, a, sig)
def hp(sig, f, order=2): b, a = butter(order, f / (SR / 2), 'high'); return lfilter(b, a, sig)
def bp(sig, lo, hi): b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band'); return lfilter(b, a, sig)
def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR); j = min(N, i + len(sig)); s = sig[:j - i] * gain
    mix[i:j, 0] += s * (1 - max(0, pan)); mix[i:j, 1] += s * (1 + min(0, pan))
def env(n, a, d): e = np.exp(-np.arange(n) / (d * SR)); k = int(a * SR); e[:k] *= np.linspace(0, 1, k) if k else 1; return e
def saw(f, n): ph = np.cumsum(np.full(n, f) / SR) if np.isscalar(f) else np.cumsum(f / SR); return 2 * (ph % 1) - 1
def note(m): return 440 * 2 ** ((m - 69) / 12)

def kick():
    n = int(.4 * SR); tt = np.arange(n) / SR; f = 45 + 110 * np.exp(-tt * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 9) + .25 * np.exp(-tt * 200) * rng.standard_normal(n) * .3
def clap():
    n = int(.25 * SR); s = bp(rng.standard_normal(n), 900, 3500); e = np.zeros(n)
    for k in (0, .011, .022): i = int(k * SR); e[i:] += np.exp(-np.arange(n - i) / (.045 * SR)) * (.7 if k else 1)
    return s * e * .9
def hat(open_=False): n = int((.22 if open_ else .05) * SR); return hp(rng.standard_normal(n), 7000) * env(n, 0, .07 if open_ else .012) * .5
def bassnote(m, dur):
    n = int(dur * SR); s = saw(note(m), n) + .5 * saw(note(m) * 1.005, n)
    return lp(s, 900, 2) * env(n, .004, .18) * .55
def stab(ms, dur=.18):
    n = int(dur * SR); s = sum(saw(note(m), n) + saw(note(m) * 1.007, n) for m in ms) / len(ms)
    return lp(s, 2600) * env(n, .003, .07) * .45
def impact():
    n = int(1.2 * SR); tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-tt * 12)) / SR) * np.exp(-tt * 3)
    crash = hp(rng.standard_normal(n), 3000) * np.exp(-tt * 4) * .35
    return boom * .9 + crash
def whoosh(dur, up=True):
    n = int(dur * SR); s = rng.standard_normal(n); out = np.zeros(n); seg = int(.02 * SR)
    for i in range(0, n, seg):
        k = i / n if up else 1 - i / n; f = 300 + 7000 * k ** 2
        out[i:i + seg] = bp(s[i:i + seg] if i + seg <= n else s[i:], max(200, f * .6), min(18000, f * 1.4))[:len(out[i:i + seg])]
    return out * (np.linspace(0, 1, n) ** 2 if up else np.linspace(1, 0, n) ** 2) * .5
def pad(ms, dur):
    n = int(dur * SR); s = sum(saw(note(m), n) + saw(note(m) * 1.004, n) + saw(note(m) * .996, n) for m in ms) / (3 * len(ms))
    e = np.minimum(1, np.arange(n) / (.03 * SR)) * np.exp(-np.arange(n) / (2.2 * SR))
    return lp(s, 3000) * e * .55
def chime(m, at, gain=.25):
    n = int(1.5 * SR); tt = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * note(m + o) * tt) * g for o, g in ((0, 1), (12, .4), (19, .2))) * np.exp(-tt * 3)
    add(s, at, gain, pan=.3); add(s, at + .12, gain * .6, pan=-.3)

# 0-1: static, then the power-on thunk
st = hp(rng.standard_normal(int(.42 * SR)), 1500) * .22; add(st, 0)
n = int(.6 * SR); tt = np.arange(n) / SR; add(np.sin(2 * np.pi * 60 * tt) * np.exp(-tt * 8) * .8 + hp(rng.standard_normal(n), 4000) * np.exp(-tt * 30) * .2, .42)

# 1-15.5 groove
bass_line = [40, 40, 43, 45, 48, 47, 45, 43]   # E2 E2 G2 A2 C3 B2 A2 G2, eighth notes
chords = [[64, 67, 71], [64, 67, 71], [60, 64, 67], [62, 66, 69]]  # Em Em C D
b0 = 1.0
nbeats = int((15.2 - b0) / BEAT)
for b in range(nbeats):
    at = b0 + b * BEAT
    if 11.55 <= at < 12.0: continue                       # breath before the star-wipe drop
    add(kick(), at, .95)
    if b % 2 == 1: add(clap(), at, .55, pan=.05)
    for h in range(2):
        add(hat(open_=(h == 1 and b % 2 == 1)), at + h * BEAT / 2, .35, pan=.4 if h else -.2)
    for e in range(2):
        m = bass_line[(b * 2 + e) % 8]
        add(bassnote(m, BEAT / 2 * .9), at + e * BEAT / 2, .8)
    if b % 2 == 0: add(stab(chords[(b // 2) % 4]), at + BEAT * .5, .5, pan=-.25 if b % 4 else .25)

# slams: EVERY / LOT / TESTED.
for k, at in enumerate((5.0, 5.5, 6.0)):
    add(whoosh(.35, True), at - .35, .6); add(impact(), at, .6 if k < 2 else .9)
# fusion: shimmer chimes as colours swap
for at, m in ((8.0, 76), (9.0, 79), (10.0, 83), (11.0, 81)): chime(m, at, .18)
add(whoosh(.5, True), 11.1, .9); add(impact(), 11.6, .7)    # riser into the star wipe
# twelve pops on the grid: little bloops
for i in range(12):
    n = int(.12 * SR); tt = np.arange(n) / SR; f = note(72 + [0, 3, 5, 7, 10, 12, 10, 7, 5, 3, 0, 12][i]) * (1 + 1.5 * np.exp(-tt * 60))
    add(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 25) * .35, 11.62 + i * .25, .6, pan=(i % 6 - 2.5) / 3)
# 15.2 tape stop: pitch-down sweep then silence
n = int(.3 * SR); tt = np.arange(n) / SR; f = 220 * (1 - tt / .3) ** 2 + 30
add(lp(saw(f, n), 1200) * (1 - tt / .3) * .35, 15.2)
# 15.7 logo: big chord, sub hit, sparkle on the chrome sweep, final chimes
add(impact(), 15.7, .8)
add(pad([52, 59, 64, 67, 71, 74], 4.3), 15.7, 1.0)
for i, m in enumerate((88, 91, 95, 98, 100)): chime(m, 16.6 + i * .07, .12)
chime(76, 17.0, .2); chime(83, 17.6, .22)

# master: gentle glue compression, fade out, normalize
L = mix.copy()
pk = np.max(np.abs(L)) or 1; L /= pk
L = np.tanh(L * 1.6) / np.tanh(1.6)
fade = np.ones(N); k = int(1.2 * SR); fade[-k:] = np.linspace(1, 0, k) ** 1.5; L *= fade[:, None]
L *= .89 / (np.max(np.abs(L)) or 1)
pcm = (L * 32767).astype('<i2')
with wave.open('music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('music.wav', DUR, 's')
