#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# ///
"""Sound-to-picture sync sheet — Claude's "ears".

Usage: sync_sheet.py <workdir> <final.mp4>

Writes <workdir>/sync_sheet.png (Read it to see the result) and prints a table.
One image lines up, per 30s row: the final mix waveform, the voice waveform,
music beats, cuts, cards (and inner events), and SFX markers, with a thumbnail of
the picture at every SFX. For each SFX it measures, from the FINAL mix:
  level    with stems (written by mix.py): SFX vs voice+music in the SFX's own band
           at its transient -> audible (>=0 dB) / faint (-6..0) / BURIED (<-6)
  sounds   when the transient is actually heard relative to "at"
  d_vis    offset to the nearest card start / event (target <= 40 ms)
  d_beat   offset to the nearest music beat (informational)
Reads overlays.json, sound_plan.json, beats.json, edl_tight.json (or edl.json),
and cut.mp4 (voice) from <workdir> when present.
"""
import json, os, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import HOP, LATENCY, NFFT, SR, load_mono  # noqa: E402

ROW_S, PX_PER_S, LANE_H, THUMB_W = 30, 80, 70, 96
COL = {"bg": (18, 18, 22), "grid": (45, 45, 55), "mix": (124, 92, 255), "voice": (90, 200, 160),
       "beat": (110, 110, 120), "cut": (240, 240, 240), "card": (124, 92, 255),
       "sfx": (255, 150, 60), "bad": (255, 70, 70), "text": (220, 220, 225)}


def load(workdir, *names):
    for n in names:
        p = os.path.join(workdir, n)
        if os.path.exists(p):
            return json.load(open(p))
    return None


def hi_flux(x):
    """High-band (>2 kHz) spectral flux: where clicks/pops/whooshes show up over voice + bed."""
    n = 1 + (len(x) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    mag = np.log1p(np.abs(np.fft.rfft(x[idx] * np.hanning(NFFT)[None, :], axis=1)) * 10)
    lo = int(2000 * NFFT / SR)
    f = np.concatenate([[0], np.maximum(0, np.diff(mag[:, lo:], axis=0)).sum(axis=1)])
    return f, np.arange(len(f)) * HOP / SR + LATENCY


def stem_audibility(sfx, rest, at):
    """Where the SFX transient really sounds, and its level vs voice+music in the
    SFX's own band right at the transient (dB). Uses pre-normalisation stems."""
    a, b = int(max(0, at - 0.05) * SR), int((at + 0.15) * SR)
    seg = np.abs(sfx[a:b])
    if seg.size == 0 or seg.max() == 0:
        return None, -99.0
    env = np.convolve(seg, np.ones(64) / 64, mode="same")
    onset = a + int(np.argmax(env > 0.3 * env.max()))
    lo, hi = onset, min(len(sfx), onset + int(0.08 * SR))
    win = np.hanning(hi - lo)
    S = np.abs(np.fft.rfft(sfx[lo:hi] * win)) ** 2
    R = np.abs(np.fft.rfft(rest[lo:hi] * win)) ** 2 if hi <= len(rest) else S * 0 + 1e-12
    band = S >= 0.1 * S.max()
    snr = 10 * np.log10((S[band].sum() + 1e-12) / (R[band].sum() + 1e-12))
    return onset / SR, float(snr)


def frame_at(video, t, w):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1",
                          "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True).stdout
    try:
        import io
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def main():
    workdir, video = sys.argv[1], sys.argv[2]
    ov = load(workdir, "overlays.json") or {"cards": []}
    plan = load(workdir, "sound_plan.json") or {}
    beats = (load(workdir, "beats.json") or {}).get("beats", [])
    edl = load(workdir, "edl_tight.json", "edl.json") or {"segments": []}
    mix = load_mono(video)
    voice_path = os.path.join(workdir, "cut.mp4")
    voice = load_mono(voice_path) if os.path.exists(voice_path) else None
    dur = len(mix) / SR

    cuts, t = [], 0.0
    for s in edl["segments"]:
        t += s["out"] - s["in"]
        cuts.append(t)
    visuals = [(c["start"], c["id"]) for c in ov["cards"]] + \
              [(v, f"{c['id']}.{k}") for c in ov["cards"] for k, v in c.get("events", {}).items()] + \
              [(b["start"], f"broll{i + 1}") for i, b in enumerate(ov.get("broll", []))]  # band.py B-roll
    stem_dir = os.path.join(os.path.dirname(os.path.abspath(video)), "stems")
    sp, rp = os.path.join(stem_dir, "sfx.wav"), os.path.join(stem_dir, "rest.wav")
    stems = (load_mono(sp), load_mono(rp)) if os.path.exists(sp) and os.path.exists(rp) else None
    flux, ft = hi_flux(mix)
    base = np.median(flux) + 1e-6

    rows = []
    for s in sorted(plan.get("sfx", []), key=lambda s: s["at"]):
        at = s["at"]
        if stems:
            peak_t, ratio = stem_audibility(stems[0], stems[1], at)
            peak_t = at if peak_t is None else peak_t
            level = "audible" if ratio >= 0 else "faint" if ratio >= -6 else "BURIED"
        else:  # no stems: blind high-band transient search in the final mix
            w = (ft >= at - 0.06) & (ft <= at + 0.06)
            ratio = float(flux[w].max() / base) if w.any() else 0.0
            peak_t = float(ft[w][np.argmax(flux[w])]) if w.any() else at
            level = "audible" if ratio >= 3.0 else "BURIED"
        vis = min(visuals, key=lambda v: abs(v[0] - at)) if visuals else (None, "-")
        bt = min(beats, key=lambda b: abs(b - at)) if beats else None
        rows.append({"at": at, "name": os.path.basename(s["file"]), "intended_ms": s.get("offset", 0.0) * 1000,
                     "gain_db": s.get("gain_db", -12), "landed": level != "BURIED", "level": level, "ratio": ratio,
                     "peak_ms": (peak_t - at) * 1000, "vis": vis[1],
                     "d_vis": None if vis[0] is None else (at - vis[0]) * 1000,
                     "d_beat": None if bt is None else (at - bt) * 1000})

    # ---- draw ----
    font = ImageFont.load_default(size=14)
    n_rows = int(np.ceil(dur / ROW_S))
    row_h = LANE_H * 2 + 120 + THUMB_W * 16 // 9 + 30
    W = ROW_S * PX_PER_S + 120
    img = Image.new("RGB", (W, n_rows * row_h + 40), COL["bg"])
    d = ImageDraw.Draw(img)
    d.text((10, 10), f"Sync sheet  {os.path.basename(video)}  {dur:.1f}s   "
                     f"mix(purple) voice(green) beats(grey) cuts(white) cards(bars) sfx(orange; red=buried/off)",
           fill=COL["text"], font=font)

    def wave(sig, y0, color, t0):
        if sig is None:
            return
        for px in range(ROW_S * PX_PER_S):
            a, b = int((t0 + px / PX_PER_S) * SR), int((t0 + (px + 1) / PX_PER_S) * SR)
            if a >= len(sig):
                break
            amp = float(np.abs(sig[a:b]).max()) if b > a else 0
            h = int(min(1, amp) * (LANE_H / 2 - 2))
            d.line([(100 + px, y0 + LANE_H // 2 - h), (100 + px, y0 + LANE_H // 2 + h)], fill=color)

    for r in range(n_rows):
        t0, y = r * ROW_S, 40 + r * row_h
        X = lambda tt: 100 + int((tt - t0) * PX_PER_S)  # noqa: E731
        inrow = lambda tt: t0 <= tt < t0 + ROW_S  # noqa: E731
        for sec in range(ROW_S + 1):
            d.line([(X(t0 + sec), y), (X(t0 + sec), y + LANE_H * 2 + 90)], fill=COL["grid"])
            if sec % 5 == 0:
                d.text((X(t0 + sec) - 8, y + LANE_H * 2 + 92), f"{t0 + sec:d}s", fill=COL["text"], font=font)
        d.text((10, y + 25), "mix", fill=COL["text"], font=font)
        d.text((10, y + LANE_H + 25), "voice", fill=COL["text"], font=font)
        wave(mix, y, COL["mix"], t0)
        wave(voice, y + LANE_H, COL["voice"], t0)
        ly = y + LANE_H * 2
        for b in beats:
            if inrow(b):
                d.line([(X(b), ly), (X(b), ly + 12)], fill=COL["beat"])
        for c in cuts:
            if inrow(c):
                d.line([(X(c), y), (X(c), ly + 26)], fill=COL["cut"])
        for c in ov["cards"]:
            if c["end"] > t0 and c["start"] < t0 + ROW_S:
                a, b = X(max(c["start"], t0)), X(min(c["end"], t0 + ROW_S))
                d.rectangle([a, ly + 30, b, ly + 50], outline=COL["card"], fill=(50, 40, 90))
                d.text((a + 3, ly + 33), c["id"], fill=COL["text"], font=font)
                for k, v in c.get("events", {}).items():
                    if inrow(v):
                        d.line([(X(v), ly + 30), (X(v), ly + 50)], fill=COL["text"])
        sfx_in = [s for s in rows if inrow(s["at"])]
        for i, s in enumerate(sfx_in):
            ok = s["landed"] and abs((s["d_vis"] or 0) + s["peak_ms"] - s["intended_ms"]) <= 40
            color = COL["sfx"] if ok else COL["bad"]
            d.polygon([(X(s["at"]) - 5, ly + 56), (X(s["at"]) + 5, ly + 56), (X(s["at"]), ly + 68)], fill=color)
            d.line([(X(s["at"]), y), (X(s["at"]), ly + 56)], fill=color)
            th = frame_at(video, s["at"] + 0.12, THUMB_W)
            tx = min(max(100, X(s["at"]) - THUMB_W // 2), W - THUMB_W - 4)
            tx = max(tx, 100 + i * 0)  # keep inside canvas
            if th:
                img.paste(th, (tx, ly + 112))
                d.rectangle([tx, ly + 112, tx + th.width, ly + 112 + th.height], outline=color)
            d.text((tx, ly + 96), f"{s['at']:.2f}", fill=color, font=font)

    out = os.path.join(workdir, "sync_sheet.png")
    img.save(out)

    print(f"Sync sheet -> {out}")
    unit = "SNR dB (vs voice+music, in the SFX's band)" if stems else "transient/median (no stems)"
    print(f"  level = {unit}; sounds = when the transient is heard vs 'at'")
    print(f"  {'sfx_at':>7}  {'file':<22} {'level':<8} {'value':>6} {'sounds':>7} {'visual':<8} {'d_vis':>7} {'d_beat':>7}")
    issues = 0
    for s in rows:
        dv = "-" if s["d_vis"] is None else f"{s['d_vis']:+.0f}ms"
        db = "-" if s["d_beat"] is None else f"{s['d_beat']:+.0f}ms"
        heard_vs_vis = (s["d_vis"] or 0) + s["peak_ms"] - s["intended_ms"]  # declared lead/lag is fine
        flag = ""
        if not s["landed"]:
            flag, issues = "  <- not audible over voice/music", issues + 1
        elif abs(heard_vs_vis) > 40:
            flag, issues = f"  <- heard {heard_vs_vis:+.0f}ms off the visual", issues + 1
        elif s["level"] == "faint":
            flag = "  (faint)"
        elif stems and s["gain_db"] > -12 and s["ratio"] > 12:
            flag, issues = f"  <- HOT: raised to {s['gain_db']} dB but {s['ratio']:.0f} dB clear — back to -12..-16 (S4)", issues + 1
        print(f"  {s['at']:7.2f}  {s['name'][:22]:<22} {s['level']:<8} {s['ratio']:6.1f} {s['peak_ms']:+6.0f}ms "
              f"{s['vis']:<8} {dv:>7} {db:>7}{flag}")
    print(f"  {issues} sync issue(s)")


if __name__ == "__main__":
    main()
