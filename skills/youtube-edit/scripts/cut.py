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


def tighten(segs, max_pause):
    """Trim silence at segment edges and split segments at internal pauses > max_pause.
    Pieces keep their segment's zoom; alternate_zooms() then fixes neighbours."""
    out = []
    for s in segs:
        if s.get("raw"):  # deliberate silence (held tail, beat before a punchline)
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
            out.append({**s, "in": round(pa, 3), "out": round(pb, 3), "zoom_lock": s.get("zoom_lock", False) and j == 0})
    return out


def alternate_zooms(segs, punch):
    """No two neighbouring segments may share a zoom (that cut is a jump in place)."""
    prev = None
    for s in segs:
        z = float(s.get("zoom", 1.0))
        if s.get("zoom_match_prev") and prev is not None:
            s["zoom"] = prev  # e.g. a held tail: same framing, no jump on the last frame
            continue
        if z > 1.0 and not s.get("zoom_lock"):
            z = punch  # one punch level keeps jump cuts consistent (Z1)
        if prev is not None and abs(z - prev) < 0.01 and not s.get("zoom_lock"):
            z = punch if prev <= 1.0 else 1.0
        s["zoom"] = z
        prev = z
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
    segs = alternate_zooms(segs, float(edl.get("punch", 1.15)))
    json.dump({"segments": segs}, open(os.path.join(workdir, "edl_tight.json"), "w"), indent=1)
    sources = []
    for s in segs:
        if s["src"] not in sources:
            sources.append(s["src"])
    w, h, fps = probe(sources[0])
    rx, ry, rw, rh = edl.get("zoom_region", [0, 0, w, h])
    parts, labels = [], []
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
        parts.append(v + f",fps={fps},format=yuv420p[v{i}]")
        d = b - a
        parts.append(f"[{k}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"afade=t=in:d={FADE},afade=t=out:st={max(0, d - FADE)}:d={FADE}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append("".join(labels) + f"concat=n={len(segs)}:v=1:a=1[v][a]")
    graph = os.path.join(workdir, "cut.filtergraph")
    open(graph, "w").write(";\n".join(parts))
    inputs = [x for src in sources for x in ("-i", src)]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", *inputs,
                    "-filter_complex_script", graph, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", out], check=True)

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
    json.dump(mapped, open(os.path.join(workdir, "words_cut.json"), "w"), indent=1)
    print(f"{len(segs)} segments from {len(sources)} source(s), {offset:.1f}s -> {out}")


if __name__ == "__main__":
    main()
