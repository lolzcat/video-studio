#!/usr/bin/env python3
"""Finisher QC pass on a rendered video. Prints a report; exit 1 on hard failures.

Usage: qc.py <video.mp4> [--expect-duration SECONDS]

Checks: flashing (WCAG >3/s), black frames, frozen frames, dead air (>1.2s silence), loudness vs
-14 LUFS, true peak, audio/video stream length mismatch (sync drift).
"""
import json, re, subprocess, sys


def ff(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                       capture_output=True, text=True)
    return r.stderr


def stream_durations(video):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,duration", "-of", "json", video])
    return {s["codec_type"]: float(s.get("duration", 0)) for s in json.loads(out)["streams"]}


def flashes(video):
    """WCAG 2.3.1-style flash count: a flash is a pair of opposing frame-to-frame
    luminance jumps of >=10% within 0.5s. Returns worst flashes-per-second and when."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                          "scale=160:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]
    ys = [float(x) for x in re.findall(r"YAVG=([\d.]+)", out)]
    jumps = [(ts[i], ys[i] - ys[i - 1]) for i in range(1, min(len(ts), len(ys)))
             if abs(ys[i] - ys[i - 1]) >= 25.5]
    flash_t = [b[0] for a, b in zip(jumps, jumps[1:])
               if a[1] * b[1] < 0 and b[0] - a[0] <= 0.5]
    worst, at = 0, None
    for i, t in enumerate(flash_t):
        n = sum(1 for u in flash_t[i:] if u - t < 1.0)
        if n > worst:
            worst, at = n, t
    return worst, at


def main():
    video = sys.argv[1]
    expect = float(sys.argv[sys.argv.index("--expect-duration") + 1]) if "--expect-duration" in sys.argv else None
    hard, warn = [], []

    d = stream_durations(video)
    if "audio" not in d:
        hard.append("no audio stream")
    elif abs(d.get("video", 0) - d["audio"]) > 0.1:
        hard.append(f"A/V length mismatch: video {d['video']:.2f}s vs audio {d['audio']:.2f}s")
    if expect and abs(d.get("video", 0) - expect) > 0.25:
        warn.append(f"duration {d.get('video', 0):.2f}s, expected {expect:.2f}s")

    log = ff(["-i", video, "-vf", "blackdetect=d=0.1:pix_th=0.08,freezedetect=n=0.003:d=2",
              "-af", "silencedetect=n=-45dB:d=1.2,ebur128=peak=true"])
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", log):
        hard.append(f"black frames {float(m[1]):.2f}-{float(m[2]):.2f}s")
    for m in re.finditer(r"freeze_start: ([\d.]+)", log):
        warn.append(f"frozen picture from {float(m[1]):.2f}s (ok if it's a still B-roll card)")
    for m in re.finditer(r"silence_start: ([\d.]+)", log):
        warn.append(f"dead air from {float(m[1]):.2f}s")
    n_flash, flash_at = flashes(video)
    if n_flash > 3:
        hard.append(f"{n_flash} flashes within 1s at {flash_at:.2f}s (photosensitivity limit is 3)")
    elif n_flash:
        warn.append(f"{n_flash} flash(es)/s at {flash_at:.2f}s (limit 3)")
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
    if lufs:
        i = float(lufs[-1])
        (warn if abs(i + 14) > 1.0 else []).append(f"integrated loudness {i} LUFS (target -14)")
    if peak and float(peak[-1]) > -0.5:
        hard.append(f"true peak {peak[-1]} dBFS (clipping risk)")

    print(f"QC {video}\n  streams: " + ", ".join(f"{k} {v:.2f}s" for k, v in d.items()))
    if lufs:
        print(f"  loudness: {lufs[-1]} LUFS, peak {peak[-1] if peak else '?'} dBFS")
    for x in hard:
        print("  FAIL  " + x)
    for x in warn:
        print("  WARN  " + x)
    print("  PASS" if not hard else "  -> fix FAIL items before delivering")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
