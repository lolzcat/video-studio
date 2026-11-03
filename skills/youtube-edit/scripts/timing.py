#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Music beats + snapping graphics to the beat + exporting timings.

  timing.py beats  <sound_plan.json> <beats.json>
      Detect beats in every music bed and map them onto the CUT timeline.
  timing.py snap   <overlays.json> <beats.json> [--max-shift 0.08]
      Move each card start / event to the nearest beat if it is within
      --max-shift seconds (STYLE.md B1). Originals are kept in "spoken" so
      re-snapping is idempotent. Rewrites overlays.json in place.
  timing.py loops  <sound_plan.json>
      For consecutive music entries using the same file (a bed looped to cover a
      long video), start each repeat a whole number of bars after the previous one
      and crossfade over its "fade", so the beat grid never slips at the loop.
  timing.py export <overlays.json> <public/timings.js> [<sound_plan.json>]
      Write window.__T for the HyperFrames composition, rewrite the card-host
      data-start/data-duration attributes in the index.html next to timings.js
      (HyperFrames gates visibility on them, and they can't read JS), and move
      every SFX that has "on": "<card>" or "<card>.<event>" onto that visual's time.

overlays.json (Claude writes this in step 5; it is the source of truth for
graphic timing — the composition reads times from timings.js, never literals):
{
  "canvas": [1080, 1920],
  "face_box": [140, 1000, 800, 920],          # region graphics must not cover
  "cards": [
    {"id": "c1", "start": 2.30, "end": 4.45, "word": "eleven",
     "text": "1,100 roofers", "bbox": [150, 790, 780, 160], "font_px": 104,
     "events": {"r2": 23.35}}                  # optional inner beats (rows, badges)
  ]
}
"""
import json, os, subprocess, sys

import numpy as np

SR, HOP, NFFT = 22050, 256, 2048
LATENCY = 0.075  # seconds from frame start to attack, see detect_beats


def load_mono(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_envelope(x):
    n = 1 + (len(x) - NFFT) // HOP
    if n <= 1:
        return np.zeros(1)
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(NFFT)[None, :]
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)) * 10)
    d = np.maximum(0, np.diff(mag, axis=0))
    low_bins = int(150 * NFFT / SR) + 1  # kick region: graphics should land on kicks, not hats

    def norm(f):
        f = np.concatenate([[0], f])
        f = np.maximum(f - np.convolve(f, np.ones(32) / 32, mode="same"), 0)  # local mean removal
        return f / (f.max() or 1)

    return norm(d[:, :low_bins].sum(axis=1)) + 0.35 * norm(d.sum(axis=1))


def detect_beats(path):
    """Fit a steady beat grid (library/generated beds hold tempo): coarse tempo
    from autocorrelation, then a fine search over fractional period and phase
    that maximises onset energy on the grid. Returns (bpm, beat times)."""
    env = onset_envelope(load_mono(path))
    fps = SR / HOP
    lags = np.arange(int(fps * 60 / 180), int(fps * 60 / 60) + 1)  # 60-180 BPM
    ac = np.array([np.dot(env[:-l], env[l:]) for l in lags])
    ac = ac * np.exp(-0.5 * (np.log2((60 * fps / lags) / 100)) ** 2)  # mild prior near 100 BPM
    p0 = float(lags[int(np.argmax(ac))])
    xs = np.arange(len(env))

    def score(period, phase):
        grid = np.arange(phase, len(env) - 1, period)
        return np.interp(grid, xs, env).sum()

    best = (-1.0, p0, 0.0)
    for period in np.linspace(p0 * 0.98, p0 * 1.02, 81):
        for phase in np.arange(0, period, 0.25):
            sc = score(period, phase)
            if sc > best[0]:
                best = (sc, period, phase)
    _, period, phase = best
    # Spectral-flux peaks trail the true attack by a fixed amount for this
    # NFFT/HOP; calibrated on synthetic click and kick tracks (error < 10 ms).
    centre = LATENCY
    beats = [round(t / fps + centre, 3) for t in np.arange(phase, len(env), period)]
    return float(60 * fps / period), beats


def cmd_beats(plan_path, out_path):
    plan = json.load(open(plan_path))
    beats, bpms = [], []
    for m in plan.get("music", []):
        if m.get("beats") is False:  # ambient/tension beds have no beat to snap to
            continue
        bpm, bt = detect_beats(m["file"])
        bpms.append(round(bpm, 1))
        span = m["end"] - m["start"]
        beats += [round(m["start"] + t, 3) for t in bt if t <= span]
    merged = []
    for t in sorted(beats):  # overlapping (looped) beds report the same beat twice
        if not merged or t - merged[-1] > 0.05:
            merged.append(t)
    beats = merged
    json.dump({"bpm": bpms, "beats": beats}, open(out_path, "w"), indent=1)
    print(f"{len(beats)} beats, bpm {bpms} -> {out_path}")


def nearest(beats, t):
    i = int(np.searchsorted(beats, t))
    cands = [beats[j] for j in (i - 1, i) if 0 <= j < len(beats)]
    return min(cands, key=lambda b: abs(b - t)) if cands else None


def cmd_snap(ov_path, beats_path, max_shift):
    ov, beats = json.load(open(ov_path)), json.load(open(beats_path))["beats"]
    moved = 0
    for c in ov["cards"]:
        spoken = c.setdefault("spoken", {"start": c["start"], **c.get("events", {})})
        for key, t0 in spoken.items():
            b = nearest(beats, t0)
            t = b if b is not None and abs(b - t0) <= max_shift else t0
            if key == "start":
                c["start"] = round(t, 3)
            else:
                c["events"][key] = round(t, 3)
            if t != t0:
                moved += 1
                print(f"  {c['id']}.{key}: {t0:.3f} -> {t:.3f} ({(t - t0) * 1000:+.0f} ms)")
    json.dump(ov, open(ov_path, "w"), indent=1)
    print(f"snapped {moved} visual(s) to the beat (max shift {max_shift * 1000:.0f} ms)")


def cmd_loops(plan_path):
    plan = json.load(open(plan_path))
    music, cache = plan.get("music", []), {}
    for prev, cur in zip(music, music[1:]):
        if cur["file"] != prev["file"]:
            continue
        if prev["file"] not in cache:
            cache[prev["file"]] = detect_beats(prev["file"])[0]
        bar = 4 * 60 / cache[prev["file"]]
        fade = cur.get("fade", 1.0)
        k = int((prev["end"] - fade - prev["start"]) // bar)
        cur["start"] = round(prev["start"] + k * bar, 3)
        prev["end"] = round(cur["start"] + fade, 3)
        print(f"  loop of {os.path.basename(cur['file'])}: repeat at {cur['start']:.3f}s "
              f"({k} bars of {bar:.3f}s), crossfade to {prev['end']:.3f}s")
    json.dump(plan, open(plan_path, "w"), indent=1)


def cmd_export(ov_path, js_path, plan_path=None):
    ov = json.load(open(ov_path))
    T = {c["id"]: {"start": c["start"], "end": c["end"], **c.get("events", {})} for c in ov["cards"]}
    open(js_path, "w").write("window.__T = " + json.dumps(T, indent=1) + ";\n")
    print(f"timings for {len(T)} cards -> {js_path}")
    html_path = os.path.join(os.path.dirname(os.path.abspath(js_path)), "index.html")
    if os.path.exists(html_path):
        import re
        html, n = open(html_path).read(), 0
        for cid, t in T.items():
            pat = re.compile(r'(class="card-host[^"]*" data-card-id="%s" )data-start="[\d.]+" data-duration="[\d.]+"' % re.escape(cid))
            html, k = pat.subn(lambda m: f'{m.group(1)}data-start="{t["start"]}" data-duration="{round(t["end"] - t["start"], 3)}"', html)
            n += k
        open(html_path, "w").write(html)
        print(f"updated data-start/data-duration on {n} card hosts in {html_path}")
    if plan_path:
        plan, n = json.load(open(plan_path)), 0
        for s in plan.get("sfx", []):
            if "on" in s:
                cid, _, ev = s["on"].partition(".")
                s["at"] = T[cid][ev or "start"] + s.get("offset", 0.0)
                n += 1
        json.dump(plan, open(plan_path, "w"), indent=1)
        print(f"re-timed {n} bound SFX in {plan_path}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "beats":
        cmd_beats(*args[:2])
    elif cmd == "snap":
        ms = float(args[args.index("--max-shift") + 1]) if "--max-shift" in args else 0.08
        cmd_snap(args[0], args[1], ms)
    elif cmd == "loops":
        cmd_loops(args[0])
    elif cmd == "export":
        cmd_export(*args[:3])
    else:
        sys.exit(__doc__)
