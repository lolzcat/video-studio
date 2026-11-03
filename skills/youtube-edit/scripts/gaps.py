#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Show where speech really starts/stops around a cut point (ASR word times drift
50-150 ms, which leaves "now"/"so" fragments at cuts).

Usage: gaps.py <video> <start_s> <end_s>

Prints one symbol per 20 ms, levels relative to the take's own loud speech (raw takes
are often recorded quiet, so fixed dB thresholds lie):
  #  speech      .  quiet (-18..-30 dB)      _  silence (< -30 dB)
Cut in the middle of a `_`/`.` run between the words you want to separate; if there's
no dip at all the words run together — pick another cut point or keep both words.
A dip of <= 60 ms (marked `^` below its row) is usually a consonant CLOSURE inside a
word (the silence before the burst of t/d/k/z), not a word gap: cutting there clips the
word ("conta-", "lead-"). When a word ends in a stop or sibilant, cut AFTER the burst
that follows the dip, before the next word's energy.
"""
import subprocess, sys

import numpy as np


def main():
    video, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    n = 320  # 20 ms
    fr = len(x) // n
    db = 20 * np.log10(np.sqrt((x[:fr * n].reshape(fr, n) ** 2).mean(1)) + 1e-9)
    ref = np.percentile(db, 95)
    cells = []
    for i in range(round(a / 0.02), min(fr, round(b / 0.02))):
        rel = db[i] - ref
        cells.append(f"{i * 0.02:.2f}{'_' if rel < -30 else '.' if rel < -18 else '#'}")
    kinds = [c[-1] for c in cells]
    short = set()
    i = 0
    while i < len(kinds):
        if kinds[i] != "#":
            j = i
            while j < len(kinds) and kinds[j] != "#":
                j += 1
            if 0 < i and j < len(kinds) and j - i <= 3:  # <= 60 ms, speech on both sides
                short.update(range(i, j))
            i = j
        else:
            i += 1
    for k in range(0, len(cells), 10):
        print(" ".join(cells[k:k + 10]))
        marks = "".join(("^" if (k + m) in short else " ").center(6) for m in range(min(10, len(cells) - k)))
        if marks.strip():
            print(marks + "  ^ short dip: likely a consonant closure, not a word gap")


if __name__ == "__main__":
    main()
