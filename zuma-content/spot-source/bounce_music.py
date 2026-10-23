# Original 15-second bed for the ZUMA bounce video, synthesized from scratch: 120 BPM, E minor.
# 0-1 TV static and power-on thunk; 1-17.5 groove (kick, clap, hats, saw bass, offbeat stabs, hits on the slams,
# riser into the star wipe); 17.2 tape-stop; 17.55 flower bloom and chord, 18.7 logo with a sparkle on the chrome sweep; fade to 23.5 s.
import numpy as np, wave
from scipy.signal import butter, lfilter

SR, DUR, BPM = 44100, 15.0, 120
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


# groove from the first landing (0.5 s) to the end card (11.5 s)
bass_line = [40, 40, 43, 45, 48, 47, 45, 43]
chords = [[64, 67, 71], [64, 67, 71], [60, 64, 67], [62, 66, 69]]
nb = int((11.5 - 0.5) / BEAT)
for b in range(nb):
    at = 0.5 + b * BEAT
    add(kick(), at, .9)
    if b % 2 == 1: add(clap(), at, .5, pan=.05)
    for h in range(2): add(hat(open_=(h == 1 and b % 2 == 1)), at + h * BEAT / 2, .3, pan=.4 if h else -.2)
    for e in range(2): add(bassnote(bass_line[(b * 2 + e) % 8], BEAT / 2 * .9), at + e * BEAT / 2, .7)
    if b % 2 == 0: add(stab(chords[(b // 2) % 4]), at + BEAT * .5, .4, pan=-.25 if b % 4 else .25)

# the drop in: a falling whistle into the first landing
n = int(.5 * SR); tt = np.arange(n) / SR
add(np.sin(2 * np.pi * np.cumsum(1800 * (1 - tt / .5) ** 1.5 + 300) / SR) * .25 * np.linspace(.3, 1, n), 0.0)

# every landing: a pop, a short boing, and a plucked note that climbs the scale vial by vial
scale = [64, 66, 67, 69, 71, 72, 74, 76, 78, 79, 81]
def pop():
    n = int(.09 * SR); tt = np.arange(n) / SR
    return hp(rng.standard_normal(n), 1500) * np.exp(-tt * 70) * .6 + np.sin(2 * np.pi * np.cumsum(900 * np.exp(-tt * 30) + 120) / SR) * np.exp(-tt * 40) * .7
def boing():
    n = int(.25 * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(260 + 140 * np.sin(tt * 60) * np.exp(-tt * 9)) / SR) * np.exp(-tt * 12) * .35
def pluck(m):
    n = int(.6 * SR); tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * note(m) * k * tt) * g for k, g in ((1, 1), (2, .35), (3, .15))) * np.exp(-tt * 7) * .3
for k in range(11):
    at = 0.5 + k
    add(pop(), at, .8); add(boing(), at + .01, .6, pan=(k % 3 - 1) * .3); add(pluck(scale[k]), at, .7, pan=(k % 2 - .5) * .4)
    add(whoosh(.3, True), at + .62, .25)                # the hop's way down, into the next landing

# the last landing becomes the logo: big hit, chord, sparkle, two chimes
add(impact(), 11.5, .9)
add(pad([52, 59, 64, 67, 71, 74], 3.5), 11.5, 1.0)
for i, m in enumerate((88, 91, 95, 98, 100)): chime(m, 12.45 + i * .07, .12)
chime(76, 13.0, .2); chime(83, 13.5, .22)

L = mix.copy()
pk = np.max(np.abs(L)) or 1; L /= pk
L = np.tanh(L * 1.6) / np.tanh(1.6)
fade = np.ones(N); k = int(1.0 * SR); fade[-k:] = np.linspace(1, 0, k) ** 1.5; L *= fade[:, None]
L *= .89 / (np.max(np.abs(L)) or 1)
pcm = (L * 32767).astype('<i2')
with wave.open('bounce.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('bounce.wav', DUR, 's')
