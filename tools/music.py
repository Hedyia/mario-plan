"""Original, royalty-free background music for Aura reels and stories (synthesised, no samples).

Usage as a module:  make_track(preset, seconds, out_wav, seed=0)
CLI:                python3 music.py PRESET SECONDS OUT.wav [SEED]
Presets: calm_piano · warm_pad · soft_lofi · bright_soft
48 kHz stereo WAV, gentle fade in/out, peak-limited. Loudness is normalised later by ffmpeg (loudnorm).
"""
import math, sys, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000

def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)

PRESETS = {
    # bpm, swing, [(bass, [voicing]) ...] one chord per bar, layers
    "calm_piano": dict(bpm=72, swing=0.0, layers=("keys", "arp", "bass", "pad"),
                       chords=[(48, [60, 64, 67, 71]), (45, [57, 60, 64, 67]), (41, [53, 57, 60, 64]), (43, [55, 59, 62, 64])]),
    "warm_pad":   dict(bpm=64, swing=0.0, layers=("pad", "bell", "bass"),
                       chords=[(41, [53, 57, 60, 64, 67]), (50, [50, 53, 57, 60, 64]), (46, [58, 62, 65, 69]), (48, [55, 60, 62, 64, 69])]),
    "soft_lofi":  dict(bpm=78, swing=0.18, layers=("keys", "bass", "drums", "pad"),
                       chords=[(50, [57, 61, 62, 66]), (47, [57, 59, 62, 66]), (43, [55, 59, 62, 66]), (45, [57, 61, 64, 66])]),
    "bright_soft": dict(bpm=88, swing=0.0, layers=("arp", "keys", "bass", "pad", "drums_light"),
                       chords=[(43, [55, 59, 62, 67]), (54, [54, 57, 62, 66]), (40, [55, 59, 62, 64]), (48, [55, 59, 60, 64])]),
}

def env_adsr(n, a, d_tau, rel, sustain_n=None):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), np.exp(-(t - a) / d_tau))
    if rel > 0:
        r = int(rel * SR)
        e[-r:] *= np.linspace(1, 0, r) if r < n else 1
    return e

def tone(freq, dur, kind, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "keys":      # soft electric-piano: few partials, higher ones decay faster
        s = (np.sin(2*np.pi*freq*t) * np.exp(-t/1.6) + .30*np.sin(2*np.pi*2*freq*t) * np.exp(-t/0.7)
             + .08*np.sin(2*np.pi*3*freq*t) * np.exp(-t/0.35)) * (1 + .03*np.sin(2*np.pi*4.5*t))
        e = env_adsr(n, .012, 10, .25)
    elif kind == "arp":     # gentle pluck
        s = np.sin(2*np.pi*freq*t) + .18*np.sin(2*np.pi*2*freq*t)
        e = env_adsr(n, .006, .38, .05)
    elif kind == "bell":    # soft bell (inharmonic partial, slow decay)
        s = np.sin(2*np.pi*freq*t) + .25*np.sin(2*np.pi*2.76*freq*t)*np.exp(-t/0.6)
        e = env_adsr(n, .01, 1.4, .3)
    elif kind == "bass":
        s = np.sin(2*np.pi*freq*t) + .35*np.sin(2*np.pi*2*freq*t) + .1*np.sin(2*np.pi*3*freq*t)
        e = env_adsr(n, .015, 1.8, .2)
    elif kind == "pad":     # detuned slow pad
        s = sum(np.sin(2*np.pi*freq*(2**(c/1200))*t + ph) for c, ph in ((-7, 0), (0, 1.1), (7, 2.3))) / 3
        s += .2*np.sin(2*np.pi*2*freq*t)
        a = min(.9, dur/3)
        e = np.minimum(1, t/a) * np.minimum(1, (dur - t)/min(1.0, dur/3))
    else:
        raise ValueError(kind)
    return (s * e * vel).astype(np.float64)

def kick(vel=1.0):
    n = int(.35*SR); t = np.arange(n)/SR
    f = 45 + 75*np.exp(-t/0.04)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t/0.12) * vel

def hat(rng, vel=1.0):
    n = int(.06*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n)
    x = sosfilt(butter(4, 7000, "highpass", fs=SR, output="sos"), x)
    return x * np.exp(-t/0.018) * vel * .5

def rim(rng, vel=1.0):
    n = int(.12*SR); t = np.arange(n)/SR
    x = sosfilt(butter(2, [1500, 3500], "bandpass", fs=SR, output="sos"), rng.standard_normal(n))
    return x * np.exp(-t/0.04) * vel

def add(buf, x, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= buf.shape[1]:
        return
    x = x[: buf.shape[1] - i]
    l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    buf[0, i:i+len(x)] += x * gain * l * 1.414
    buf[1, i:i+len(x)] += x * gain * r * 1.414

def block_comb(x, d, g):
    y = np.copy(x)
    for k in range(d, len(x), d):
        e = min(k + d, len(x))
        y[k:e] += g * y[k-d:e-d]
    return y

def block_allpass(x, d, g):
    y = np.zeros_like(x)
    xd = np.concatenate([np.zeros(d), x[:-d]])
    y[:d] = -g * x[:d] + xd[:d]
    for k in range(d, len(x), d):
        e = min(k + d, len(x))
        y[k:e] = -g * x[k:e] + xd[k:e] + g * y[k-d:e-d]
    return y

def reverb(x, mix=.22, seed=0):
    out = np.zeros_like(x)
    for ch in range(2):
        off = 0 if ch == 0 else 23
        combs = [(int((29.7+off*.05)*SR/1000), .80), (int((37.1+off*.07)*SR/1000), .78),
                 (int((41.1+off*.03)*SR/1000), .77), (int((43.7+off*.09)*SR/1000), .76)]
        wet = sum(block_comb(x[ch], d, g) for d, g in combs) / 4
        wet = block_allpass(wet, int(5.0*SR/1000), .7)
        wet = block_allpass(wet, int(1.7*SR/1000), .7)
        wet = sosfilt(butter(2, 5000, "lowpass", fs=SR, output="sos"), wet)
        out[ch] = (1 - mix) * x[ch] + mix * wet
    return out

def make_track(preset, seconds, out_wav, seed=0):
    p = PRESETS[preset]
    rng = np.random.default_rng(seed)
    beat = 60 / p["bpm"]; bar = 4 * beat
    total = seconds + 2.5
    buf = np.zeros((2, int(total * SR)))
    chords = p["chords"]
    shift = int(rng.integers(0, len(chords)))
    nbars = int(math.ceil(total / bar))
    for b in range(nbars):
        bass, voic = chords[(b + shift) % len(chords)]
        t0 = b * bar
        L = p["layers"]
        if "pad" in L:
            for m in voic:
                add(buf, tone(mtof(m), bar + .8, "pad"), t0, .055, pan=rng.uniform(-.5, .5))
        if "keys" in L:
            for hit, v in ((0, 1.0), (2.5 if preset == "soft_lofi" else 2, .7)):
                st = t0 + hit * beat
                for k, m in enumerate(voic):
                    add(buf, tone(mtof(m), 2.6, "keys", v * rng.uniform(.8, 1)), st + k * .012, .11, pan=-.25 + .5 * k / len(voic))
        if "bell" in L:
            for hit in (0, 2):
                m = voic[int(rng.integers(0, len(voic)))] + 12
                add(buf, tone(mtof(m), 3, "bell", rng.uniform(.5, .8)), t0 + hit * beat, .07, pan=rng.uniform(-.6, .6))
        if "arp" in L:
            notes = [m + 12 for m in voic]
            seq = notes + notes[-2:0:-1]
            for e in range(8):
                if rng.random() < .12:
                    continue
                st = t0 + e * beat / 2 + (p["swing"] * beat / 2 if e % 2 else 0)
                add(buf, tone(mtof(seq[e % len(seq)]), .9, "arp", rng.uniform(.5, .8)), st, .085, pan=.45 if e % 2 else -.45)
        if "bass" in L:
            add(buf, tone(mtof(bass), bar * .9, "bass"), t0, .16)
            if preset in ("soft_lofi", "bright_soft"):
                add(buf, tone(mtof(bass), beat * 1.2, "bass", .7), t0 + 2.5 * beat, .12)
        if "drums" in L or "drums_light" in L:
            light = "drums_light" in L
            for q in (0, 2):
                add(buf, kick(), t0 + q * beat, .22 if not light else .14)
            if not light:
                for q in (1, 3):
                    add(buf, rim(rng), t0 + q * beat, .05)
            for e in range(8):
                st = t0 + e * beat / 2 + (p["swing"] * beat / 2 if e % 2 else 0)
                add(buf, hat(rng, rng.uniform(.5, 1)), st, .05 if not light else .03, pan=.3)
    # stereo slap delay on everything (subtle width)
    d = int(.011 * SR)
    buf[1, d:] = .85 * buf[1, d:] + .15 * buf[1, :-d]
    buf = reverb(buf, mix=.24, seed=seed)
    sos = butter(2, 9500, "lowpass", fs=SR, output="sos")
    sos_hp = butter(2, 70, "highpass", fs=SR, output="sos")
    buf = np.stack([sosfilt(sos_hp, sosfilt(sos, ch)) for ch in buf])
    n = int(seconds * SR)
    buf = buf[:, :n]
    fi, fo = int(.6 * SR), int(min(1.4, seconds / 4) * SR)
    buf[:, :fi] *= np.linspace(0, 1, fi)
    buf[:, -fo:] *= np.linspace(1, 0, fo)
    buf /= (np.max(np.abs(buf)) + 1e-9)
    buf = np.tanh(buf * 1.2) / np.tanh(1.2) * .89     # gentle limiter, peak ≈ -1 dBFS
    pcm = (buf.T * 32767).astype("<i2")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return out_wav

if __name__ == "__main__":
    make_track(sys.argv[1], float(sys.argv[2]), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 0)
