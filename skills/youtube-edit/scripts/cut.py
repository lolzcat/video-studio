#!/usr/bin/env python3
"""Render a rough cut from an edit decision list (EDL).

Usage: cut.py <default_video> <workdir>/edl.json <out.mp4>

edl.json:
{
  "segments": [
    {"in": 1.20, "out": 6.85, "zoom": 1.0, "note": "hook line 1, take 2"},
    {"src": "/abs/take3.mp4", "words": "/abs/work/t3/words.json",
     "in": 9.40, "out": 14.10, "zoom": 1.15, "focus": [0.5, 0.4]}
  ]
}
  src     source file for this segment (default: <default_video>); use it to
          assemble one edit from several takes
  words   that source's words.json (default: <workdir>/words.json)
  in/out  source seconds (cut on word boundaries from words.json, pad ~0.05-0.12s)
  zoom    static punch-in for the whole segment (1.0 = none)
  focus   punch-in centre as [x, y] fractions of the zoom area (default centre)
  zoom_lock  keep this segment's zoom even if it matches its neighbour
  raw     skip pause-tightening for this segment (e.g. a held silent tail at the end)
  zoom_match_prev  use the previous segment's zoom (a continuation, not a jump)
Top level (all optional):
  max_pause    shorten every pause inside kept segments to this many seconds and
               trim edge silence; writes edl_tight.json
  punch        punch-in used when alternating framing on jump cuts (default 1.15, Z1)
  soft_cuts    (default true) a cut that keeps the same framing gets a 3-frame dissolve — a simple
               "morph cut" — so the head doesn't jolt in place; framing changes stay hard cuts
  smooth_motion  true: webcam/call footage often repeats ~1 in 4 frames (recorded below the file's
               rate), so motion goes move-move-move-hold — sped up, it reads as shake. Drops the
               repeats (mpdecimate) and rebuilds the in-betweens (motion-compensated minterpolate,
               scene-change aware so it never blends across a hard cut). ~3 s of render per second.
  speed        e.g. 1.25: speed the whole cut up with the voice pitch kept (Premiere's
               "Maintain Audio Pitch") — Rubber Band R3 if installed (brew install rubberband),
               else ffmpeg atempo. Re-transcribe the cut afterwards as usual (timing truth).
  level_voice  true: gain-match every piece's speech level to the median (±6 dB), so lines
               joined from louder/quieter parts of a long recording don't step in volume
  zoom_region  [x, y, w, h] — punch in only inside this rect (e.g. the face half of a
               screen-top / face-bottom recording) and leave the rest of the frame at 1.0
Every cut between two segments with the same zoom is a jump in place, so neighbours
are forced to alternate 1.0 <-> punch (unless zoom_lock).

All sources must share resolution. Also writes <workdir>/words_cut.json: the
kept words remapped onto the cut timeline, which is what overlays, captions and
SFX timing must use.
"""
import json, os, re, subprocess, sys

FADE = 0.012  # short audio fades at every cut to kill clicks
MIN_SAVE = 0.15  # only jump-cut a pause if it saves >= 150 ms (smaller cuts read as jitter)


def probe(video):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                   "-show_entries", "stream=width,height,r_frame_rate:"
                                   "stream_side_data=rotation", "-of", "json", video])
    s = json.loads(out)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    w, h = s["width"], s["height"]
    # Phone footage is often stored sideways with a rotation flag; ffmpeg auto-rotates on
    # decode, so the frames we filter are the displayed size, not the stored one.
    rot = next((abs(int(d.get("rotation", 0))) for d in s.get("side_data_list", [])), 0)
    if rot % 180 == 90:
        w, h = h, w
    return w, h, float(num) / float(den)


def silences(src, cache={}):
    if src not in cache:
        log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-af",
                              "silencedetect=n=-40dB:d=0.2", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
        en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
        cache[src] = list(zip(st, en))
    return cache[src]


def speed_up(path, speed, fps):
    """Retime a rendered cut by `speed` in place: video PTS/speed at the same fps, voice
    time-stretched with pitch kept."""
    import shutil, tempfile
    tmp = tempfile.mkdtemp(prefix="speed_", dir=os.path.dirname(os.path.abspath(path)))
    src, wav, fast = os.path.join(tmp, "in.mp4"), os.path.join(tmp, "in.wav"), os.path.join(tmp, "fast.wav")
    shutil.move(path, src)
    if shutil.which("rubberband"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "2", "-ar", "48000", wav], check=True)
        subprocess.run(["rubberband", "-q", "-3", "-T", str(speed), wav, fast], check=True)  # R3: finest engine
        audio_in, audio_f = ["-i", fast], []
        engine = "rubberband R3"
    else:
        audio_in, audio_f = [], ["-af", f"atempo={speed}"]
        engine = "ffmpeg atempo"
    args = ["ffmpeg", "-v", "error", "-y", "-i", src, *audio_in, "-filter:v", f"setpts=PTS/{speed},fps={fps}",
            "-map", "0:v", "-map", "1:a" if audio_in else "0:a", *audio_f,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
            "-shortest", path]
    subprocess.run(args, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return engine


def smooth_motion(path, fps):
    import shutil, tempfile
    tmp = tempfile.mkdtemp(prefix="smooth_", dir=os.path.dirname(os.path.abspath(path)))
    src = os.path.join(tmp, "in.mp4")
    shutil.move(path, src)
    vf = ("mpdecimate=hi=1280:lo=512:frac=0.5,"
          f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-c:v", "libx264", "-preset", "medium",
                    "-crf", "18", "-c:a", "copy", path], check=True)
    shutil.rmtree(tmp, ignore_errors=True)


def rms_db(src, a, b):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(a), "-to", str(b), "-i", src, "-vn",
                          "-af", "astats=measure_perchannel=none", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"RMS level dB: (-?[\d.]+)", log)
    return float(m[-1]) if m else None


def level_gains(segs):
    """dB per piece that brings each spoken piece to the median level (raw tails stay at 0)."""
    lv = [None if s.get("raw") or s["out"] - s["in"] < 0.4 else rms_db(s["src"], s["in"], s["out"]) for s in segs]
    vals = sorted(v for v in lv if v is not None)
    if not vals:
        return [0.0] * len(segs)
    med = vals[len(vals) // 2]
    return [0.0 if v is None else max(-6.0, min(6.0, med - v)) for v in lv]


def tighten(segs, max_pause):
    """Trim silence at segment edges and split segments at internal pauses > max_pause.
    Pieces keep their segment's zoom; alternate_zooms() then fixes neighbours."""
    out = []
    for s in segs:
        if s.get("raw"):  # deliberate silence (held tail, beat before a punchline)
            prev = out[-1] if out else None
            if prev and prev["src"] == s["src"] and 0 < s["in"] - prev["out"] < 0.3:
                # trimming moved the previous out earlier: start the tail there, or a 1-frame jump shows
                s = {**s, "in": prev["out"]}
            out.append(s)
            continue
        a, b = s["in"], s["out"]
        pieces, cur = [], a
        for sa, sb in silences(s["src"]):
            if sb <= a or sa >= b:
                continue
            if sa <= a + 0.05:                      # leading silence
                cur = max(cur, sb - 0.08)
            elif sb >= b - 0.05:                    # trailing silence
                b = min(b, sa + 0.12)
            elif sb - sa - max_pause >= MIN_SAVE:   # internal pause worth a jump cut
                pieces.append((cur, sa + max_pause / 2))
                cur = sb - max_pause / 2
        pieces.append((cur, b))
        for j, (pa, pb) in enumerate(pieces):
            if pb - pa < 0.15:
                continue
            out.append({**s, "in": round(pa, 3), "out": round(pb, 3), "zoom_lock": s.get("zoom_lock", False) and j == 0,
                        "trim_piece": j > 0})   # j > 0: only a pause was removed, not a real edit
    return out


MIN_ZOOM_HOLD = 2.5   # s between framing changes (Andrew 2026-11-04: "camera micro shakes")
MIN_FLIP_PIECE = 0.6  # a sliver shorter than this never gets its own framing


def alternate_zooms(segs, punch, speed=1.0):
    """Alternate framing on real edits so jump cuts look intentional (Z1), but never more often
    than every MIN_ZOOM_HOLD seconds: removed pauses and slivers keep the current framing."""
    prev, held = None, 0.0   # the opening framing holds too
    for s in segs:
        d = (s["out"] - s["in"]) / speed
        z = float(s.get("zoom", 1.0))
        if prev is not None and (s.get("zoom_match_prev") or s.get("trim_piece") or d < MIN_FLIP_PIECE
                                 or (held < MIN_ZOOM_HOLD and not s.get("zoom_lock"))):
            s["zoom"] = prev  # same framing: a held tail, a trimmed pause, a sliver, or too soon
            held += d
            continue
        if z > 1.0 and not s.get("zoom_lock"):
            z = punch  # one punch level keeps jump cuts consistent (Z1)
        if prev is not None and abs(z - prev) < 0.01 and not s.get("zoom_lock"):
            z = punch if prev <= 1.0 else 1.0
        held = 0.0 if prev is not None and abs(z - prev) >= 0.01 else held
        s["zoom"] = z
        prev = z
        held += d
    return segs


def main():
    video, edl_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    workdir = os.path.dirname(os.path.abspath(edl_path))
    edl = json.load(open(edl_path))
    segs = edl["segments"]
    for s in segs:
        s.setdefault("src", video)
    if edl.get("max_pause"):
        segs = tighten(segs, float(edl["max_pause"]))
    segs = alternate_zooms(segs, float(edl.get("punch", 1.15)), float(edl.get("speed", 1.0)))
    json.dump({"segments": segs}, open(os.path.join(workdir, "edl_tight.json"), "w"), indent=1)
    sources = []
    for s in segs:
        if s["src"] not in sources:
            sources.append(s["src"])
    w, h, fps = probe(sources[0])
    rx, ry, rw, rh = edl.get("zoom_region", [0, 0, w, h])
    parts, labels = [], []
    gains = level_gains(segs) if edl.get("level_voice") else [0.0] * len(segs)
    if any(abs(g) >= 1 for g in gains):
        print("voice levelling (dB): " + " ".join(f"{g:+.1f}" for g in gains))
    for i, s in enumerate(segs):
        k = sources.index(s["src"])
        a, b, z = s["in"], s["out"], float(s.get("zoom", 1.0))
        fx, fy = s.get("focus", [0.5, 0.5])
        v = f"[{k}:v]trim={a}:{b},setpts=PTS-STARTPTS,scale={w}:{h},setsar=1"
        if z > 1.0:
            cw, ch = int(rw / z) // 2 * 2, int(rh / z) // 2 * 2
            cx = rx + max(0, min(rw - cw, int(fx * rw - cw / 2)))
            cy = ry + max(0, min(rh - ch, int(fy * rh - ch / 2)))
            parts.append(v + f",split=2[b{i}][r{i}]")
            parts.append(f"[r{i}]crop={cw}:{ch}:{cx}:{cy},scale={rw}:{rh}:flags=lanczos,setsar=1[z{i}]")
            v = f"[b{i}][z{i}]overlay={rx}:{ry}"
        parts.append(v + f",fps={fps},format=yuv420p,settb=1/{fps}[v{i}]")   # one timebase for xfade
        d = b - a
        parts.append(f"[{k}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"volume={gains[i]:.2f}dB,afade=t=in:d={FADE},afade=t=out:st={max(0, d - FADE)}:d={FADE}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    # Join: hard cut where framing changes or the take simply continues; a short dissolve where a
    # cut keeps the framing (otherwise the head jumps in place — reads as camera shake).
    soft = edl.get("soft_cuts", True)
    D = round(3 / fps, 4)
    joins, rv, ra, length = [], "[v0]", "[a0]", segs[0]["out"] - segs[0]["in"]
    for i in range(1, len(segs)):
        p_, s_ = segs[i - 1], segs[i]
        d = s_["out"] - s_["in"]
        same_frame = abs(float(p_.get("zoom", 1)) - float(s_.get("zoom", 1))) < 0.01
        continuous = p_["src"] == s_["src"] and abs(s_["in"] - p_["out"]) < 0.02
        if soft and same_frame and not continuous and d > 2 * D and length > 2 * D:
            parts.append(f"{rv}[v{i}]xfade=transition=fade:duration={D}:offset={length - D:.4f}[jv{i}]")
            parts.append(f"{ra}[a{i}]acrossfade=d={D}:c1=tri:c2=tri[ja{i}]")
            length += d - D
            joins.append("soft")
        else:
            parts.append(f"{rv}{ra}[v{i}][a{i}]concat=n=2:v=1:a=1[cv{i}][ja{i}]")
            parts.append(f"[cv{i}]settb=1/{fps}[jv{i}]")
            length += d
            joins.append("hard")
        rv, ra = f"[jv{i}]", f"[ja{i}]"
        s_["join"] = joins[-1]
    parts.append(f"{rv}null[v]" if len(segs) > 1 else "[v0]null[v]")
    parts.append(f"{ra}anull[a]" if len(segs) > 1 else "[a0]anull[a]")
    json.dump({"segments": segs}, open(os.path.join(workdir, "edl_tight.json"), "w"), indent=1)  # with joins
    if joins.count("soft"):
        print(f"{joins.count('soft')} in-place cut(s) softened with a {D:.3f}s dissolve, {joins.count('hard')} hard")
    graph = os.path.join(workdir, "cut.filtergraph")
    open(graph, "w").write(";\n".join(parts))
    inputs = [x for src in sources for x in ("-i", src)]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", *inputs,
                    "-filter_complex_script", graph, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", out], check=True)
    speed = float(edl.get("speed", 1.0))
    if abs(speed - 1.0) > 0.001:
        out_fps = fps * speed   # every source frame kept (24 x 1.25 = 30); resampling to 24 drops 1 in 5 = stutter
        out_fps = min((24, 25, 30, 48, 50, 60), key=lambda r: abs(r - out_fps)) if abs(out_fps - round(out_fps)) > 0.01 else round(out_fps)
        print(f"speed {speed}x with pitch kept ({speed_up(out, speed, out_fps)}), {out_fps} fps")
    if edl.get("smooth_motion"):
        smooth_motion(out, probe(out)[2])
        print("motion smoothed (repeated frames rebuilt)")

    mapped, offset, cache = [], 0.0, {}
    for idx, s in enumerate(segs):
        wp = s.get("words", os.path.join(workdir, "words.json"))
        if wp not in cache:
            cache[wp] = json.load(open(wp)) if os.path.exists(wp) else []
        for wd in cache[wp]:
            if s["in"] <= (wd["start"] + wd["end"]) / 2 <= s["out"]:  # midpoint inside segment
                a, b = max(wd["start"], s["in"]), min(wd["end"], s["out"])
                mapped.append({**wd, "start": round(a - s["in"] + offset, 3),
                               "end": round(b - s["in"] + offset, 3), "seg": idx})
        offset += s["out"] - s["in"]
        if idx + 1 < len(segs) and segs[idx + 1].get("join") == "soft":
            offset -= D
    if abs(speed - 1.0) > 0.001:  # approximate until the re-ASR of the cut replaces it
        mapped = [{**wd, "start": round(wd["start"] / speed, 3), "end": round(wd["end"] / speed, 3)} for wd in mapped]
        offset /= speed
    json.dump(mapped, open(os.path.join(workdir, "words_cut.json"), "w"), indent=1)
    print(f"{len(segs)} segments from {len(sources)} source(s), {offset:.1f}s -> {out}")


if __name__ == "__main__":
    main()
