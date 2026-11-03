#!/usr/bin/env python3
"""Pre-render rule check: validate the edit plan against STYLE.md before rendering.

Usage: check_plan.py <workdir> [--format hook|short|full]

Reads <workdir>/overlays.json, sound_plan.json, and edl_tight.json (or edl.json).
Exit 1 on any FAIL. Rule IDs refer to STYLE.md; thresholds are the STYLE.md values.
"""
import json, os, sys

FMT = {  # max seconds without a visual change (STYLE.md G2)
    "hook": 4.0, "short": 4.0, "full": 8.0,
}
HOOK_BY = 3.0        # H1: first visual change / on-screen hook within 3s
MIN_CARD = 1.2       # G1
MIN_FONT_1080 = 40   # T1: smallest text at 1080px canvas width (~14pt on a phone)
SFX_GAP = 2.0        # S3
SFX_ALIGN = 0.10     # SFX should land within 100ms of a visual


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
    for a, b in zip(cards, cards[1:]):
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
