#!/usr/bin/env python3
"""Pull reference videos into a reference pack Claude can study.

Usage: pull.py <url-or-file> [<url-or-file> ...] --out <packdir> [--max-seconds 900]

Works with anything yt-dlp supports (YouTube, Shorts, TikTok, X, Instagram, Bilibili,
Xiaohongshu, Kuaishou...) and local files (videos Andrew uploads). Douyin needs a
cookies file: add --cookies <cookies.txt> (Andrew exports it himself).

Per video, in <packdir>/<id>/:
  meta.json        title, channel, views, likes, upload date, duration, language
  video.mp4        <=360p copy, first --max-seconds (analysis only — never reused in an edit)
  transcript.txt   "[m:ss] text" — captions if available, else ASR (Parakeet for
                   English, Whisper for other languages, original language kept)
  hook.jpg         frames at 0, 0.5 ... 3.0s (the hook)
  sheet.jpg        contact sheet across the whole video
  stats.json       cuts/min, median shot length, first cut, words-or-chars/min, LUFS
And <packdir>/index.md: one table row per video.
"""
import json, os, re, shutil, statistics, subprocess, sys, time

SKILLS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRANSCRIBE = os.path.join(SKILLS, "youtube-edit", "scripts", "transcribe.py")
BILI_PAUSE_S = 6


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ytdlp_meta(src, cookies):
    r = run(["yt-dlp", "--no-warnings", "--skip-download", "--dump-json", "--no-playlist",
             *(["--cookies", cookies] if cookies else []), src])
    return json.loads(r.stdout.splitlines()[0]) if r.returncode == 0 and r.stdout.strip() else None


def fetch(src, d, max_s, cookies):
    """Return (meta, video_path, caption_srt_or_None)."""
    if os.path.exists(src):
        p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src])
        dur = float(p.stdout.strip() or 0)
        dst = os.path.join(d, "video" + os.path.splitext(src)[1])
        shutil.copy(src, dst)
        return {"title": os.path.basename(src), "source": "upload", "duration": dur}, dst, None
    v = ytdlp_meta(src, cookies) or {}
    base = os.path.join(d, "video")
    ck = ["--cookies", cookies] if cookies else []
    # Whole file at <=360p, trimmed locally: YouTube 403s ffmpeg's ranged requests,
    # so --download-sections is unreliable across sites.
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist", "-f",
           "bv*[height<=360]+ba[abr<=160]/b[height<=360]/wv*+ba/w", "--merge-output-format", "mp4",
           "-o", base + ".%(ext)s", *ck]
    r = run(cmd + [src])
    # Captions are best-effort and separate: a rate-limited subtitle request (HTTP 429)
    # must not sink the whole pull — ASR covers it.
    run(["yt-dlp", "--no-warnings", "--no-playlist", "--skip-download", "--write-subs",
         "--write-auto-subs", "--sub-langs", "en,en-orig,zh-Hans,zh-CN,ai-zh", "--convert-subs", "srt",
         "-o", base + ".%(ext)s", *ck, src])
    vids = [f for f in os.listdir(d) if f.startswith("video.") and f.endswith((".mp4", ".mkv", ".webm"))]
    if not vids:
        # Some CDNs (Bilibili HTTP 567 risk control) block video but still serve audio:
        # keep the transcript + pace, take the cover image, and flag the pack.
        err = (r.stderr or "download failed").strip().splitlines()[-1]
        run(["yt-dlp", "--no-warnings", "--no-playlist", "-f", "ba/bestaudio", "-x", "--audio-format", "m4a",
             "--write-thumbnail", "--convert-thumbnails", "jpg", "-o", os.path.join(d, "audio.%(ext)s"), *ck, src])
        auds = [f for f in os.listdir(d) if f.startswith(("audio.", "video.f")) and f.endswith((".m4a", ".mp3", ".opus"))]
        if not auds:
            raise RuntimeError(err)
        meta = {k: v.get(k) for k in ("title", "channel", "uploader", "view_count", "like_count",
                                        "comment_count", "channel_follower_count", "upload_date",
                                        "duration", "webpage_url", "language", "extractor_key")}
        meta.update(channel=meta.get("channel") or meta.get("uploader"), source=src,
                    video_blocked=err[:200])
        thumb = os.path.join(d, "audio.jpg")
        if os.path.exists(thumb):
            os.replace(thumb, os.path.join(d, "cover.jpg"))
        return meta, os.path.join(d, auds[0]), None
    if (v.get("duration") or 0) > max_s:
        full, cut = os.path.join(d, vids[0]), os.path.join(d, "video_cut.mp4")
        run(["ffmpeg", "-y", "-v", "error", "-i", full, "-t", str(max_s), "-c", "copy", cut])
        os.replace(cut, os.path.join(d, "video.mp4"))
        if full != os.path.join(d, "video.mp4"):
            os.remove(full)
        vids = ["video.mp4"]
    # Prefer the creator's original-language track; YouTube may hand back .vtt instead of .srt.
    srts = sorted((f for f in os.listdir(d) if f.endswith((".srt", ".vtt"))),
                  key=lambda f: (".orig." not in f and "-orig." not in f, f))
    meta = {k: v.get(k) for k in ("title", "channel", "uploader", "view_count", "like_count",
                                    "comment_count", "channel_follower_count", "upload_date",
                                    "duration", "webpage_url", "language", "extractor_key")}
    meta["channel"] = meta.get("channel") or meta.get("uploader")
    meta["source"] = src
    return meta, os.path.join(d, vids[0]), os.path.join(d, srts[0]) if srts else None


def srt_to_lines(path):
    lines, t = [], None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        raw = raw.strip()
        m = re.match(r"(\d+):(\d+):(\d+)[,.]\d+ -->", raw)
        if m:
            t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
        elif raw and not raw.isdigit() and t is not None:
            txt = re.sub("<[^>]+>", "", raw)
            if not lines or lines[-1][1] != txt:  # auto-captions repeat rolling lines
                lines.append((t, txt))
    return lines


def asr(video, d, lang_hint):
    wav = os.path.join(d, "audio16k.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-ac", "1", "-ar", "16000", wav])
    if lang_hint in (None, "en") and shutil.which("parakeet-mlx"):
        run(["python3", TRANSCRIBE, video, os.path.join(d, "asr")])
        words = json.load(open(os.path.join(d, "asr", "words.json")))
        if words:  # Parakeet has no Chinese: an empty/garbled result falls through to Whisper
            ascii_ratio = sum(w["text"].isascii() for w in words) / len(words)
            if ascii_ratio > 0.8:
                out, cur, t0 = [], [], None
                for w in words:
                    t0 = w["start"] if t0 is None else t0
                    cur.append(w["text"])
                    if w["text"][-1:] in ".?!":
                        out.append((t0, " ".join(cur)))
                        cur, t0 = [], None
                if cur:
                    out.append((t0, " ".join(cur)))
                return out, "en"
    cmd = ["mlx_whisper", wav, "--model", "mlx-community/whisper-large-v3-turbo",
           "--output-format", "json", "--output-dir", d]
    if lang_hint and lang_hint != "en":
        cmd += ["--language", lang_hint]
    run(cmd)
    j = json.load(open(os.path.join(d, "audio16k.json")))
    return [(s["start"], s["text"].strip()) for s in j.get("segments", [])], j.get("language") or lang_hint


def scene_cuts(video):
    log = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
               "scale=320:-2,select='gt(scene,0.3)',showinfo", "-f", "null", "-"]).stderr
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", log)]


def lufs(video):
    log = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af", "ebur128", "-f", "null", "-"]).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    return float(m[-1]) if m else None


def frames(video, d, dur):
    hook = os.path.join(d, "hook_%d.jpg")
    for i, t in enumerate([0, 0.5, 1, 1.5, 2, 2.5, 3]):
        if t < dur:
            run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1",
                 "-vf", "scale=240:-2", hook % i])
    hs = sorted(f for f in os.listdir(d) if re.match(r"hook_\d+\.jpg", f))
    if hs:
        inputs = [x for f in hs for x in ("-i", os.path.join(d, f))]
        run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
             "".join(f"[{i}]" for i in range(len(hs))) + f"hstack={len(hs)}" if len(hs) > 1 else "null",
             os.path.join(d, "hook.jpg")])
        for f in hs:
            os.remove(os.path.join(d, f))
    step = max(2.0, dur / 24)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vf",
         f"fps=1/{step:.2f},scale=200:-2,tile=6x4", "-frames:v", "1", os.path.join(d, "sheet.jpg")])


def fmt_t(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def process(n, src, d, max_s, cookies, lang):
    meta, video, srt = fetch(src, d, max_s, cookies)
    dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                     video]).stdout.strip() or 0)
    hint = lang or (meta.get("language") or "")[:2] or ("zh" if "bilibili" in src or "douyin" in src else None)
    if srt:
        lines, got = srt_to_lines(srt), "captions"
        meta["transcript_lang"] = (os.path.basename(srt).split(".")[-2] or hint or "?")
    else:
        lines, l2 = asr(video, d, hint)
        got, meta["transcript_lang"] = "asr", l2
    meta["transcript_source"] = got
    with open(os.path.join(d, "transcript.txt"), "w") as f:
        f.write("\n".join(f"[{fmt_t(t)}] {txt}" for t, txt in lines) + "\n")
    audio_only = bool(meta.get("video_blocked"))
    cuts = [] if audio_only else scene_cuts(video)
    shots = [b - a for a, b in zip([0.0] + cuts, cuts + [dur])]
    text = " ".join(t for _, t in lines)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    stats = {"duration": round(dur, 1), "cuts": None if audio_only else len(cuts),
             "cuts_per_min": None if audio_only else (round(len(cuts) / dur * 60, 1) if dur else 0),
             "median_shot_s": None if audio_only else (round(statistics.median(shots), 2) if shots else dur),
             "first_cut_s": round(cuts[0], 2) if cuts else None,
             "words_per_min" if cjk < 50 else "chars_per_min":
                 round((len(text.split()) if cjk < 50 else cjk) / dur * 60) if dur else 0,
             "lufs": lufs(video),
             "hook_text": " ".join(t for s, t in lines if s < 4)[:300]}
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(stats, open(os.path.join(d, "stats.json"), "w"), ensure_ascii=False, indent=1)
    if not audio_only:
        frames(video, d, dur)
    for junk in ("audio16k.wav", "audio16k.json", "asr"):  # ASR scratch, not part of the pack
        p = os.path.join(d, junk)
        shutil.rmtree(p) if os.path.isdir(p) else (os.remove(p) if os.path.exists(p) else None)
    row = ({"n": n, "dir": os.path.basename(d), **{k: meta.get(k) for k in
                  ("title", "channel", "view_count", "like_count", "upload_date")}, **stats,
                  "transcript": f"{got}/{meta['transcript_lang']}" + (" · VIDEO BLOCKED (audio+cover only)" if audio_only else "")})
    print(f"[{n}] {meta.get('title', '')[:60]} — {stats['duration']}s, "
          f"{'video blocked, audio only' if audio_only else str(stats['cuts_per_min']) + ' cuts/min'}, "
          f"transcript {got}/{meta['transcript_lang']} -> {d}")
    return row


def main():
    args = sys.argv[1:]
    out = args[args.index("--out") + 1]
    max_s = int(args[args.index("--max-seconds") + 1]) if "--max-seconds" in args else 900
    cookies = args[args.index("--cookies") + 1] if "--cookies" in args else None
    lang = args[args.index("--lang") + 1] if "--lang" in args else None
    skip = {out, str(max_s), cookies, lang}
    sources = [a for a in args if not a.startswith("--") and a not in skip]
    os.makedirs(out, exist_ok=True)
    index = []
    for n, src in enumerate(sources, 1):
        vid = re.sub(r"[^A-Za-z0-9_-]+", "_", (re.search(r"(BV\w+|[\w-]{11})(?:\?|$|/)", src) or [None, f"v{n}"])[1])[:40]
        d = os.path.join(out, f"{n:02d}-{vid}")
        os.makedirs(d, exist_ok=True)
        if n > 1 and ("bilibili" in src or "instagram" in src):
            time.sleep(BILI_PAUSE_S)  # back-to-back pulls trip Bilibili (HTTP 567) / Instagram rate limits
        try:
            index.append(process(n, src, d, max_s, cookies, lang))
        except Exception as e:  # noqa: BLE001 — report this video and keep going with the rest
            print(f"[{n}] FAILED {src}: {e}")
            index.append({"n": n, "src": src, "error": str(e)})
    with open(os.path.join(out, "index.md"), "w") as f:
        f.write("| # | title | channel | views | dur | cuts/min | median shot | first cut | pace | transcript |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in index:
            if "error" in r:
                f.write(f"| {r['n']} | FAILED: {r['src']} | | | | | | | | {r['error'][:60]} |\n")
                continue
            pace = r.get("words_per_min") or f"{r.get('chars_per_min')} chars"
            f.write(f"| {r['n']} | {(r['title'] or '')[:50]} | {r['channel'] or ''} | {r['view_count'] or ''} | "
                    f"{r['duration']}s | {r['cuts_per_min']} | {r['median_shot_s']}s | {r['first_cut_s']} | "
                    f"{pace}/min | {r['transcript']} |\n")
    json.dump(index, open(os.path.join(out, "index.json"), "w"), ensure_ascii=False, indent=1)
    print(f"pack -> {out}/index.md")


if __name__ == "__main__":
    main()
