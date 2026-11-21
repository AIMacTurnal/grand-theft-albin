"""Renders the site's original G-funk style loop ("Radio Malmö FM") to a WAV file.
Pure Python (no numpy). Usage: python3 render_music.py out.wav
"""
import math, random, struct, sys, wave
from array import array

SR = 44100
BPM = 94
STEP = 60 / BPM / 4
BARS = 24
SWING = 0.14
LOOP_N = int(round(BARS * 16 * STEP * SR))
TAIL = int(2.5 * SR)
N = LOOP_N + TAIL

L = array('f', bytes(4 * N)); R = array('f', bytes(4 * N))
VERB = array('f', bytes(4 * N)); DLY = array('f', bytes(4 * N))
random.seed(42)
NOISE = array('f', [random.uniform(-1, 1) for _ in range(SR)])
TWO_PI = 2 * math.pi
sin = math.sin; exp = math.exp


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def t_of(step):
    s = step % 16
    return step * STEP + (STEP * SWING if s % 2 else 0)


def add(buf_l, buf_r, start, samples, pan=0.0, verb=0.0, delay=0.0):
    gl = math.cos((pan + 1) * math.pi / 4); gr = math.sin((pan + 1) * math.pi / 4)
    i0 = int(start * SR)
    for k, v in enumerate(samples):
        i = i0 + k
        if i >= N: break
        buf_l[i] += v * gl; buf_r[i] += v * gr
        if verb: VERB[i] += v * verb
        if delay: DLY[i] += v * delay


# ---------------- instruments ----------------
def kick(t, vol=0.9):
    n = int(0.45 * SR); out = []; ph = 0.0
    for k in range(n):
        x = k / SR
        f = 45 + 95 * exp(-x / 0.035)
        ph += TWO_PI * f / SR
        a = exp(-x / 0.16)
        click = NOISE[k] * exp(-x / 0.002) * 0.3
        out.append((sin(ph) * a + click) * vol)
    add(L, R, t, out)


def snare(t, vol=0.5):
    n = int(0.35 * SR); out = []; ph = 0.0; prev = 0.0; hp = 0.0
    for k in range(n):
        x = k / SR
        nz = NOISE[(k * 7) % SR]
        hp = 0.85 * (hp + nz - prev); prev = nz
        ph += TWO_PI * 190 / SR
        # clap-like double hit
        env = exp(-x / 0.07) + (0.6 * exp(-(x - 0.012) / 0.05) if x > 0.012 else 0)
        out.append((hp * env * 0.8 + sin(ph) * exp(-x / 0.04) * 0.5) * vol)
    add(L, R, t, out, pan=0.05, verb=0.35)


def hat(t, open_=False, vol=0.16, pan=0.3):
    n = int((0.3 if open_ else 0.06) * SR); out = []; p1 = p2 = 0.0; h1 = h2 = 0.0
    tau = 0.07 if open_ else 0.012
    for k in range(n):
        nz = NOISE[(k * 13 + 5000) % SR]
        h1 = 0.6 * (h1 + nz - p1); p1 = nz
        h2 = 0.6 * (h2 + h1 - p2); p2 = h1
        out.append(h2 * exp(-k / SR / tau) * vol)
    add(L, R, t, out, pan=pan)


def shaker(t, vol=0.05):
    n = int(0.09 * SR); out = []
    for k in range(n):
        x = k / SR
        env = (x / 0.03) if x < 0.03 else exp(-(x - 0.03) / 0.02)
        out.append(NOISE[(k * 3 + 9000) % SR] * env * vol)
    add(L, R, t, out, pan=-0.4)


_bass_last = [40]
def bass(t, m, dur, slide=False, vol=0.38):
    n = int((dur + 0.05) * SR); out = []; ph = 0.0; lp = 0.0
    f0 = mtof(_bass_last[0] if slide else m); f1 = mtof(m); _bass_last[0] = m
    for k in range(n):
        x = k / SR
        f = f1 + (f0 - f1) * exp(-x / 0.05)
        ph += f / SR
        ph -= int(ph)
        saw = 2 * ph - 1
        cutoff = 0.02 + 0.09 * exp(-x / 0.12)
        lp += cutoff * (saw - lp)
        sub = sin(TWO_PI * ph)
        a = min(1, x / 0.005) * (1 if x < dur else exp(-(x - dur) / 0.02)) * (0.75 + 0.25 * exp(-x / 0.2))
        out.append((sub * 0.8 + lp * 0.6) * a * vol)
    add(L, R, t, out)


def rhodes(t, notes, dur, vol=0.05):
    n = int((dur + 0.6) * SR); out = [0.0] * n
    for j, m in enumerate(notes):
        f = mtof(m); det = 1 + 0.0015 * (j - 2)
        for k in range(n):
            x = k / SR
            idx = 1.6 * exp(-x / 0.25)
            mod = sin(TWO_PI * f * x) * idx
            a = min(1, x / 0.004) * exp(-x / 1.1) * (1 if x < dur else exp(-(x - dur) / 0.12))
            trem = 1 + 0.18 * sin(TWO_PI * 4.5 * x)
            out[k] += sin(TWO_PI * f * det * x + mod) * a * trem * vol
    add(L, R, t, out, pan=-0.2, verb=0.3)


_lead_last = [None]
def whine(t, m, dur, vol=0.12):
    n = int((dur + 0.15) * SR); out = []; ph = 0.0
    f1 = mtof(m); f0 = mtof(_lead_last[0]) if _lead_last[0] else f1; _lead_last[0] = m
    for k in range(n):
        x = k / SR
        vib = 1 + 0.01 * min(1, x / 0.25) * sin(TWO_PI * 5.6 * x)
        f = (f1 + (f0 - f1) * exp(-x / 0.045)) * vib
        ph += f / SR; ph -= int(ph)
        tri = 4 * abs(ph - 0.5) - 1
        v = 0.75 * sin(TWO_PI * ph) + 0.25 * tri
        a = min(1, x / 0.03) * (1 if x < dur else exp(-(x - dur) / 0.05))
        out.append(v * a * vol)
    add(L, R, t, out, pan=0.15, verb=0.25, delay=0.35)


def pluck(t, m, vol=0.045, pan=0.45):
    n = int(0.25 * SR); out = []; ph = 0.0; lp = 0.0; f = mtof(m)
    for k in range(n):
        x = k / SR
        ph += f / SR; ph -= int(ph)
        sq = 1 if ph < 0.5 else -1
        lp += (0.05 + 0.25 * exp(-x / 0.03)) * (sq - lp)
        out.append(lp * exp(-x / 0.09) * vol)
    add(L, R, t, out, pan=pan, delay=0.25)


# ---------------- composition (original) ----------------
# | Em9 | Cmaj9 | Am9 | B7b9 |
CHORDS = [[52, 55, 59, 62, 66], [48, 52, 55, 59, 62], [45, 48, 52, 55, 59], [47, 51, 54, 57, 60]]
ROOTS = [40, 36, 33, 35]
BASS = [(0, 0, 3, False), (3, 0, 1, False), (6, 12, 1, True), (7, 0, 1, True), (10, 7, 2, False), (13, 10, 1, False), (14, 12, 2, True)]
LEAD_A = [
    [(0, 83, 4), (4, 81, 2), (6, 79, 2), (8, 78, 6), (14, 76, 2)],
    [(0, 79, 6), (6, 76, 2), (8, 71, 8)],
    [(0, 84, 4), (4, 83, 4), (8, 81, 4), (12, 76, 4)],
    [(0, 87, 6), (6, 84, 2), (8, 83, 8)],
    [(0, 88, 4), (4, 86, 2), (6, 83, 2), (8, 81, 4), (12, 79, 4)],
    [(0, 78, 6), (6, 79, 2), (8, 76, 8)],
    [(0, 81, 2), (2, 84, 2), (4, 88, 8), (12, 86, 4)],
    [(0, 83, 6), (6, 81, 2), (8, 75, 4), (12, 71, 4)],
]
ARP = [0, 2, 1, 3, 2, 4, 3, 1]

for bar in range(BARS):
    ci = bar % 4; base = bar * 16
    section = bar // 8  # 0 intro groove, 1 lead, 2 lead + arps
    for s in range(16):
        t = t_of(base + s)
        if s in (0, 10) or (s == 7 and bar % 2) or (s == 15 and bar % 4 == 3): kick(t)
        if s in (4, 12): snare(t)
        if s % 2 == 0: hat(t, open_=(s == 14))
        elif section > 0 and s in (3, 11): hat(t, vol=0.08)
        if s % 4 == 2: shaker(t)
        if section != 1 and s % 2 == 0:
            ch = CHORDS[ci]
            pluck(t, ch[ARP[(s // 2) % 8] % len(ch)] + 12)
    for st, iv, ln, sl in BASS:
        bass(t_of(base + st), ROOTS[ci] + iv, ln * STEP * 0.95, sl)
    rhodes(t_of(base), CHORDS[ci], STEP * 5.5)
    rhodes(t_of(base + 6), CHORDS[ci][1:], STEP * 2.5, vol=0.035)
    rhodes(t_of(base + 10), CHORDS[ci][1:], STEP * 4, vol=0.035)
    if section >= 1:
        phrase = LEAD_A[(bar - 8) % 8] if section == 1 else LEAD_A[(bar - 16 + 4) % 8]
        for st, m, ln in phrase:
            whine(t_of(base + st), m, ln * STEP * 0.95)
    print('bar', bar + 1, 'of', BARS, flush=True)

# ---------------- effects ----------------
print('delay...', flush=True)
d = int(STEP * 3 * SR); fb = 0.38
for i in range(d, N):
    DLY[i] += DLY[i - d] * fb
for i in range(N):
    L[i] += DLY[i] * 0.45; R[i] += DLY[i - 331 if i > 331 else i] * 0.45; VERB[i] += DLY[i] * 0.15

print('reverb...', flush=True)
def freeverb(src, combs, aps):
    out = array('f', bytes(4 * N))
    for dl in combs:
        buf = [0.0] * dl; idx = 0; store = 0.0
        for i in range(N):
            y = buf[idx]
            store = y * 0.8 + store * 0.2
            buf[idx] = src[i] + store * 0.82
            out[i] += y
            idx += 1
            if idx == dl: idx = 0
    for dl in aps:
        buf = [0.0] * dl; idx = 0
        for i in range(N):
            b = buf[idx]; x = out[i]
            out[i] = -x + b
            buf[idx] = x + b * 0.5
            idx += 1
            if idx == dl: idx = 0
    return out
vl = freeverb(VERB, [1116, 1277, 1422, 1557], [556, 441])
vr = freeverb(VERB, [1139, 1300, 1445, 1580], [579, 464])
for i in range(N):
    L[i] += vl[i] * 0.07; R[i] += vr[i] * 0.07

# wrap the tail onto the start so the loop is seamless
for i in range(TAIL):
    L[i] += L[LOOP_N + i]; R[i] += R[LOOP_N + i]

peak = max(max(abs(v) for v in L[:LOOP_N]), max(abs(v) for v in R[:LOOP_N]))
g = 1.1 / peak
print('peak', peak, flush=True)
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    frames = bytearray()
    for i in range(LOOP_N):
        a = math.tanh(L[i] * g) * 0.92; b = math.tanh(R[i] * g) * 0.92
        frames += struct.pack('<hh', int(a * 32767), int(b * 32767))
    w.writeframes(bytes(frames))
print('done', LOOP_N / SR, 'seconds', flush=True)
