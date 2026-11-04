#!/usr/bin/env python3
"""Pre-render rule check: validate the edit plan against STYLE.md before rendering.

Usage: check_plan.py <workdir> [--format hook|short|full]

Reads <workdir>/overlays.json, sound_plan.json, and edl_tight.json (or edl.json).
Cards with "persistent": true (scoreboard, series title) are exempt from one-at-a-time but
must not be covered by another card or by captions.
Exit 1 on any FAIL. Rule IDs refer to STYLE.md; thresholds are the STYLE.md values.
"""
import json, os, re, sys

FMT = {  # max seconds without a visual change (STYLE.md G2)
    "hook": 4.0, "short": 4.0, "full": 8.0,
}
HOOK_BY = 3.0        # H1: first visual change / on-screen hook within 3s
MIN_CARD = 1.2       # G1
MIN_FONT_1080 = 40   # T1: smallest text at 1080px canvas width (~14pt on a phone)
SFX_GAP = 2.0        # S3
SFX_ALIGN = 0.10     # SFX should land within 100ms of a visual
CAP_HALF_H = 90      # K1: caption band = centre y +- 90px (two lines at 76px)
UI_TOP, UI_BOTTOM, UI_RIGHT = 220, 420, 140  # 9:16 Reels/TikTok UI: top bar, caption/handle area, button column


def load(workdir, *names):
    for n in names:
        p = os.path.join(workdir, n)
        if os.path.exists(p):
            return json.load(open(p))
    return None


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))


def main():
    workdir = sys.argv[1]
    fmt = sys.argv[sys.argv.index("--format") + 1] if "--format" in sys.argv else "short"
    ov = load(workdir, "overlays.json") or {"cards": []}
    plan = load(workdir, "sound_plan.json") or {}
    edl = load(workdir, "edl_tight.json", "edl.json") or {"segments": []}
    cards = sorted(ov["cards"], key=lambda c: c["start"])
    fails, warns = [], []

    # Timeline of visual changes: cut points where zoom changes, card starts/ends, inner events.
    t, prev_zoom, changes = 0.0, None, []
    for s in edl["segments"]:
        z = s.get("zoom", 1.0)
        if prev_zoom is not None and z != prev_zoom:
            changes.append(round(t, 3))
        prev_zoom, t = z, t + s["out"] - s["in"]
    total = t or max((c["end"] for c in cards), default=0)
    for c in cards:
        changes += [c["start"], c["end"], *c.get("events", {}).values()]
    changes = sorted(set(round(x, 3) for x in changes if 0 <= x <= total))

    # H1 hook
    first = changes[0] if changes else None
    if first is None or first > HOOK_BY:
        fails.append(f"H1 nothing changes on screen in the first {HOOK_BY:.0f}s (first change at {first})")

    # G2 pacing
    pts = [0.0] + changes + [total]
    for a, b in zip(pts, pts[1:]):
        if b - a > FMT[fmt]:
            warns.append(f"G2 {b - a:.1f}s without a visual change ({a:.2f}-{b:.2f}s, max {FMT[fmt]:.0f}s for {fmt})")

    # G1 one at a time + min duration
    for c in cards:
        if c["end"] - c["start"] < MIN_CARD:
            fails.append(f"G1 {c['id']} on screen {c['end'] - c['start']:.2f}s (< {MIN_CARD}s)")
    # Persistent labels (scoreboard, series title) sit on screen the whole video by design.
    transient = [c for c in cards if not c.get("persistent")]
    persistent = [c for c in cards if c.get("persistent")]
    for p in persistent:
        for c in transient:
            if p.get("bbox") and c.get("bbox") and overlap(p["bbox"], c["bbox"]) > 0 \
                    and c["start"] < p["end"] and c["end"] > p["start"]:
                fails.append(f"G1 {c['id']} covers the persistent {p['id']} label — move one of them")
    for a, b in zip(transient, transient[1:]):
        if b["start"] < a["end"] - 0.01:
            fails.append(f"G1 {a['id']} and {b['id']} overlap ({b['start']:.2f} < {a['end']:.2f})")

    # T1 readability + G3 face
    width = ov.get("canvas", [1080, 1920])[0]
    face = ov.get("face_box")
    for c in cards:
        fp = c.get("font_px")
        if fp is None:
            warns.append(f"T1 {c['id']} has no font_px declared — can't check readability")
        elif fp * 1080 / width < MIN_FONT_1080:
            fails.append(f"T1 {c['id']} smallest text {fp}px (< {MIN_FONT_1080}px at 1080 wide) — unreadable on a phone")
        if face and c.get("bbox"):
            o = overlap(face, c["bbox"])
            if o > 0.02 * c["bbox"][2] * c["bbox"][3]:
                fails.append(f"G3 {c['id']} covers the face box ({o / (c['bbox'][2] * c['bbox'][3]):.0%} of the card)")

    # K1 captions: present on shorts, never under a card, inside the platform-safe area
    cap_path = os.path.join(workdir, "public", "captions.js")
    W, H = ov.get("canvas", [1080, 1920])
    vertical = H > W
    if os.path.exists(cap_path):
        txt = open(cap_path).read()
        caps = json.loads(re.search(r"window\.__CAPS = (\[.*?\]);", txt, re.S).group(1))
        ym = re.search(r"window\.__CAPS_Y = (\d+|null)", txt)
        cy = int(ym.group(1)) if ym and ym.group(1) != "null" else int(H * 0.68)
        band = [70, cy - CAP_HALF_H, W - 140, 2 * CAP_HALF_H]
        for c in cards:
            if not c.get("bbox"):
                continue
            hit = [k for k in caps if k["in"] < c["end"] and k["out"] > c["start"]]
            if hit and overlap(band, c["bbox"]) > 0:
                fails.append(f"K1 captions (y {cy}) collide with {c['id']} while both are on screen — "
                             f"move captions.y or the card")
        if vertical and (cy - CAP_HALF_H < UI_TOP or cy + CAP_HALF_H > H - UI_BOTTOM):
            warns.append(f"K1 caption band y {cy - CAP_HALF_H}-{cy + CAP_HALF_H} is under the Reels/TikTok UI "
                         f"(keep it inside {UI_TOP}-{H - UI_BOTTOM})")
        if face and overlap(band, face) > 0.5 * band[2] * band[3]:
            warns.append("K1 caption band sits mostly over the face box — check it covers chin/chest/cap, not eyes or mouth")
    elif fmt in ("short", "hook"):
        warns.append("K1 no captions (public/captions.js) — shorts caption every line; run captions.py")
    if vertical:
        for c in cards:
            x, y, w, h = c.get("bbox", [0, 0, 0, 0])
            if w >= W - 1:
                continue  # full-width B-roll/images are meant to fill the frame
            in_buttons = x + w > W - UI_RIGHT + 40 and y + h > 860 and y < H - UI_BOTTOM
            if h and (y + h > H - UI_BOTTOM or y < UI_TOP or in_buttons):
                warns.append(f"K1 {c['id']} reaches into the Reels/TikTok UI area — may be covered on phones")

    # S3 SFX spacing + alignment to visuals
    sfx = sorted(plan.get("sfx", []), key=lambda s: s["at"])
    for a, b in zip(sfx, sfx[1:]):
        if b["at"] - a["at"] < SFX_GAP:
            warns.append(f"S3 SFX {b['at'] - a['at']:.2f}s apart at {a['at']:.2f}/{b['at']:.2f}s (min {SFX_GAP}s)")
    visual_ts = [c["start"] for c in cards] + [v for c in cards for v in c.get("events", {}).values()]
    for s in sfx:
        d = min((abs(s["at"] - v) for v in visual_ts), default=99)
        if d > SFX_ALIGN and "on" not in s:
            warns.append(f"S3 SFX at {s['at']:.2f}s is {d * 1000:.0f}ms from any visual — bind it with \"on\"")
    for s in plan.get("music", []):
        if s.get("gain_db", -24) > -18:
            warns.append(f"S2 music bed at {s['gain_db']} dB is hot — voice must win")

    print(f"Plan check {workdir} ({fmt}, {total:.1f}s, {len(cards)} cards, {len(sfx)} sfx)")
    for x in fails:
        print("  FAIL  " + x)
    for x in warns:
        print("  WARN  " + x)
    print("  PASS" if not fails else "  -> fix FAIL items before rendering")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
