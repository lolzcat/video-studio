#!/usr/bin/env python3
"""Transcribe a video with Parakeet (MLX) into word-level timestamps.

Usage: transcribe.py <video> <workdir>

Writes into <workdir>:
  audio16k.wav     mono 16 kHz audio used for ASR
  words.json       [{text, start, end, conf}]  (source timeline, seconds)
  transcript.txt   one line per sentence: "[start-end] (gap before) text"
                   long pauses are flagged so retakes/flubs are easy to spot
Falls back to mlx_whisper if parakeet-mlx is not installed.
"""
import json, os, re, shutil, subprocess, sys

GAP_FLAG = 0.7  # seconds of silence worth flagging in transcript.txt


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def parakeet(wav, workdir):
    run(["parakeet-mlx", wav, "--output-format", "json", "--output-dir", workdir])
    data = json.load(open(os.path.join(workdir, "audio16k.json")))
    words = []
    for sent in data["sentences"]:
        for tok in sent["tokens"]:
            t = tok["text"]
            # Parakeet emits sub-word tokens; a leading space starts a new word.
            # Digits/currency glued to a word ("got226", "has$500") are a separate word.
            if words and (t[:1].isdigit() or t[:1] in "$€£¥") and words[-1]["text"][-1:].isalpha():
                t = " " + t
            if words and not t.startswith(" ") and not t.strip() == "":
                w = words[-1]
                w["text"] += t
                w["end"] = tok["end"]
                w["conf"] = min(w["conf"], tok.get("confidence", 1.0))
            elif t.strip():
                words.append({"text": t.strip(), "start": tok["start"], "end": tok["end"],
                              "conf": tok.get("confidence", 1.0)})
    return words


def whisper(wav, workdir):
    run(["mlx_whisper", wav, "--word-timestamps", "True", "--output-format", "json",
         "--output-dir", workdir, "--model", "mlx-community/whisper-large-v3-turbo"])
    data = json.load(open(os.path.join(workdir, "audio16k.json")))
    return [{"text": w["word"].strip(), "start": w["start"], "end": w["end"],
             "conf": w.get("probability", 1.0)}
            for seg in data["segments"] for w in seg.get("words", [])]


def silences(wav):
    """ffmpeg silencedetect -> [(start, end)]; ASR tends to stretch words over pauses."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                          "silencedetect=n=-40dB:d=0.3", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(starts, ends))


def clamp_to_silence(words, sil):
    """Trim word edges that ASR extended into a detected silence."""
    for w in words:
        for a, b in sil:
            if w["start"] < a < w["end"]:          # silence begins inside the word -> word ended there
                w["end"] = round(a + 0.05, 3)
            elif w["start"] < b < w["end"] and a <= w["start"] + 0.05:  # word really starts after silence
                w["start"] = round(b - 0.05, 3)
    return words


def sentences(words):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap_next = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 0
        if w["text"][-1:] in ".?!" or gap_next > GAP_FLAG:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main():
    video, workdir = sys.argv[1], sys.argv[2]
    os.makedirs(workdir, exist_ok=True)
    wav = os.path.join(workdir, "audio16k.wav")
    run(["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    words = parakeet(wav, workdir) if shutil.which("parakeet-mlx") else whisper(wav, workdir)
    words = clamp_to_silence(words, silences(wav))
    json.dump(words, open(os.path.join(workdir, "words.json"), "w"), indent=1)

    lines, prev_end = [], 0.0
    for s in sentences(words):
        gap = s[0]["start"] - prev_end
        flag = f" (gap {gap:.1f}s)" if gap > GAP_FLAG else ""
        low = " [low-conf]" if min(w["conf"] for w in s) < 0.5 else ""
        text = " ".join(w["text"] for w in s)
        lines.append(f"[{s[0]['start']:.2f}-{s[-1]['end']:.2f}]{flag}{low} {text}")
        prev_end = s[-1]["end"]
    open(os.path.join(workdir, "transcript.txt"), "w").write("\n".join(lines) + "\n")
    print(f"{len(words)} words, {len(lines)} lines -> {workdir}/transcript.txt")


if __name__ == "__main__":
    main()
