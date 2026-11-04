#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# ///
"""Shot-by-shot breakdown of one pulled reference video (a pack folder from pull.py).

Usage: shots.py <pack-video-dir> [--scene 0.25]
(weaker scene changes are verified by before/after frame similarity; see the shots section)

Writes into the folder:
  shots.json        every shot [{n, start, end, dur}] + word timing + audio read (below)
  shots_sheet.jpg   one labelled frame per shot (mid-shot), in order — Read it
  hook_strip.jpg    frames every 0.25s from 0 to 3s, labelled — Read it
  words.json        word-level timing (Parakeet, English) if not already present
Measured (not judged): cut times, shot lengths, words per 5s window, pauses > 0.4s,
music-bed estimate (energy in speech gaps vs speech), SFX candidates (sharp high-band
transients away from word onsets). Judge shot TYPE / B-roll meaning from the frames.
"""
import json, os, re, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TRANSCRIBE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "youtube-edit", "scripts", "transcribe.py")
SR = 16000


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def frame(video, t, w):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1",
                          "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    try:
        import io
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None


def sheet(frames_labels, cols, path, w):
    font = ImageFont.load_default(size=14)
    imgs = [(f, l) for f, l in frames_labels if f]
    if not imgs:
        return
    h = imgs[0][0].height
    rows = (len(imgs) + cols - 1) // cols
    out = Image.new("RGB", (cols * w, rows * (h + 20)), (15, 15, 18))
    d = ImageDraw.Draw(out)
    for i, (f, label) in enumerate(imgs):
        x, y = (i % cols) * w, (i // cols) * (h + 20)
        out.paste(f.resize((w, h)), (x, y + 20))
        d.text((x + 4, y + 3), label, fill=(240, 240, 240), font=font)
    out.save(path, quality=85)


def main():
    d = os.path.normpath(sys.argv[1])
    scene = float(sys.argv[sys.argv.index("--scene") + 1]) if "--scene" in sys.argv else 0.25
    video = os.path.join(d, "video.mp4")
    if not os.path.exists(video):
        sys.exit(f"no video.mp4 in {d} (video may have been blocked — audio-only pack)")
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]).stdout or 0)

    # Letterboxed footage (phone filming a laptop, black bars) dilutes the scene score and
    # hides cuts: detect the active picture area first and score only that.
    crop = ""
    cd = run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(min(dur, 20)), "-i", video, "-an",
              "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"]).stderr
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", cd)
    if m:
        w, h, x, y = map(int, m[-1])
        if h < 0.85 * int(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=height", "-of", "csv=p=0", video]).stdout.strip() or h):
            crop = f"crop={w}:{h}:{x}:{y},"
    # Shots, two tiers: scene score >= --scene (0.25) is a cut. Weaker candidates (>= 0.12) —
    # cuts between similar dark/letterboxed frames — count only if the frames 0.1s either
    # side look different (correlation < 0.6). Handheld motion stays highly correlated
    # (0.7–0.9) even when its scene score spikes, so it isn't mistaken for a cut.
    log = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
               f"{crop}scale=320:-2,select='gt(scene,0.12)',metadata=print:key=lavfi.scene_score:file=-",
               "-f", "null", "-"]).stdout
    cand = list(zip([float(x) for x in re.findall(r"pts_time:([\d.]+)", log)],
                    [float(x) for x in re.findall(r"scene_score=([\d.]+)", log)]))

    def gray(t):
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1",
                            "-vf", f"{crop}scale=48:48,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        return np.frombuffer(b, np.uint8).astype(float) if len(b) == 2304 else None

    def similar(t):
        a, b = gray(t - 0.1), gray(t + 0.1)
        if a is None or b is None:
            return 1.0
        a, b = a - a.mean(), b - b.mean()
        return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))

    raw_cuts = [t for t, sc in cand if sc >= scene or similar(t) < 0.6]
    cuts = []
    for c in raw_cuts:  # a 1–2 frame flash produces two cuts ~0.03s apart: keep one
        if not cuts or c - cuts[-1] > 0.1:
            cuts.append(c)
    bounds = [0.0] + [c for c in cuts if 0.15 < c < dur - 0.1] + [dur]
    shots = [{"n": i + 1, "start": round(a, 2), "end": round(b, 2), "dur": round(b - a, 2)}
             for i, (a, b) in enumerate(zip(bounds, bounds[1:]))]

    # Words (English): Parakeet word timing for pace / pauses / SFX-vs-speech
    wpath = os.path.join(d, "words.json")
    if not os.path.exists(wpath):
        lang = json.load(open(os.path.join(d, "meta.json"))).get("transcript_lang", "en") if os.path.exists(
            os.path.join(d, "meta.json")) else "en"
        if (lang or "en").startswith("en"):
            run(["python3", TRANSCRIBE, video, os.path.join(d, "_asr")])
            src = os.path.join(d, "_asr", "words.json")
            if os.path.exists(src):
                os.replace(src, wpath)
            subprocess.run(["rm", "-rf", os.path.join(d, "_asr")])
    words = json.load(open(wpath)) if os.path.exists(wpath) else []
    pace = []
    for t0 in np.arange(0, dur, 5.0):
        n = sum(1 for w in words if t0 <= w["start"] < t0 + 5)
        pace.append({"t": round(float(t0), 1), "wpm": round(n * 12)})
    pauses = [{"at": round(a["end"], 2), "len": round(b["start"] - a["end"], 2)}
              for a, b in zip(words, words[1:]) if b["start"] - a["end"] > 0.4]

    # Audio read: music bed (gap energy vs speech energy) + SFX candidates
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.float32)
    hop = 320  # 20 ms
    fr = len(x) // hop
    rms = np.sqrt((x[:fr * hop].reshape(fr, hop) ** 2).mean(1)) + 1e-9
    db = 20 * np.log10(rms)
    speech = np.zeros(fr, bool)
    for w in words:
        speech[int(w["start"] / 0.02):int(w["end"] / 0.02) + 1] = True
    music = None
    if words and (~speech).sum() > 25:
        gap_db, sp_db = float(np.median(db[~speech])), float(np.median(db[speech]))
        rel = gap_db - sp_db
        music = {"gap_vs_speech_db": round(rel, 1),
                 "read": ("music bed OR steady background noise (car, room, wind) — check frames/ear"
                          if rel > -22 else "no bed / near-silent gaps")}
    nfft = 1024
    n = 1 + (len(x) - nfft) // hop
    sfx = []
    if n > 2:
        idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
        mag = np.log1p(np.abs(np.fft.rfft(x[idx] * np.hanning(nfft)[None, :], axis=1)) * 10)
        hi = mag[:, int(3000 * nfft / SR):]
        flux = np.concatenate([[0], np.maximum(0, np.diff(hi, axis=0)).sum(1)])
        thr = np.percentile(flux, 99)
        onsets = {round(w["start"], 1) for w in words}
        last = -1
        for i in np.where(flux > thr)[0]:
            t = i * hop / SR
            if t - last < 0.3:
                continue
            near_word = any(abs(t - o) < 0.08 for o in onsets)
            near_cut = any(abs(t - c) < 0.1 for c in cuts)
            if not near_word:
                sfx.append({"at": round(t, 2), "on_cut": near_cut})
                last = t

    out = {"duration": round(dur, 2), "letterbox_crop": crop.rstrip(",") or None, "shots": shots, "cuts": len(shots) - 1,
           "median_shot": round(float(np.median([s["dur"] for s in shots])), 2),
           "shots_first_3s": sum(1 for s in shots if s["start"] < 3),
           "pace_wpm_per_5s": pace, "pauses": pauses, "music": music, "sfx_candidates": sfx[:30]}
    json.dump(out, open(os.path.join(d, "shots.json"), "w"), indent=1)

    labels = [(frame(video, (s["start"] + s["end"]) / 2, 180), f"#{s['n']} {s['start']:.1f}s ({s['dur']:.1f})")
              for s in shots[:60]]
    sheet(labels, 8, os.path.join(d, "shots_sheet.jpg"), 180)
    sheet([(frame(video, t, 180), f"{t:.2f}s") for t in np.arange(0, min(3.01, dur), 0.25)], 7,
          os.path.join(d, "hook_strip.jpg"), 180)
    print(f"{os.path.basename(d)}: {len(shots)} shots, median {out['median_shot']}s, "
          f"{out['shots_first_3s']} shots in first 3s, {len(sfx)} sfx candidates, music: {(music or {}).get('read')}")


if __name__ == "__main__":
    main()
