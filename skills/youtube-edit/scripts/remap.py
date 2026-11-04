#!/usr/bin/env python3
"""Move every graphic onto a re-cut's timeline.

Usage: remap.py <old words_cut.json> <new words_cut.json> <overlays.json>

After any re-cut (moved in/out points, tighter max_pause, dropped words), the old card times
point at the wrong words. This aligns the two transcripts word by word (difflib on normalised
text) and moves each card start/end, card event and B-roll start/end by the offset of the
nearest aligned word. Times with no aligned word within 1.5s are left alone and reported.
Rewrites overlays.json in place (drops stale "spoken" snapshots so timing.py snap starts fresh).
"""
import difflib, json, re, sys


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w["text"].lower())


def main():
    old, new, ovp = sys.argv[1:4]
    a, b = json.load(open(old)), json.load(open(new))
    pairs = []
    sm = difflib.SequenceMatcher(None, [norm(w) for w in a], [norm(w) for w in b], autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            pairs.append((a[blk.a + k]["start"], b[blk.b + k]["start"]))
    if not pairs:
        sys.exit("no words in common — is this the same clip?")

    misses = []

    def m(t, what):
        o, n = min(pairs, key=lambda p: abs(p[0] - t))
        if abs(o - t) > 1.5:
            misses.append(f"{what} {t:.2f}")
            return t
        return round(t - o + n, 3)

    ov = json.load(open(ovp))
    dur = b[-1]["end"] if b else None
    for c in ov.get("cards", []):
        if c.get("persistent"):
            continue
        c["start"], c["end"] = m(c["start"], c["id"] + ".start"), m(c["end"], c["id"] + ".end")
        for k, v in list(c.get("events", {}).items()):
            c["events"][k] = m(v, f"{c['id']}.{k}")
        c.pop("spoken", None)
    for i, br in enumerate(ov.get("broll", []), 1):
        br["start"], br["end"] = m(br["start"], f"broll{i}.start"), m(br["end"], f"broll{i}.end")
    json.dump(ov, open(ovp, "w"), indent=1, ensure_ascii=False)
    print(f"remapped {len(ov.get('cards', []))} cards, {len(ov.get('broll', []))} B-roll on {len(pairs)} aligned words"
          + (f"; left alone (no word nearby): {', '.join(misses)}" if misses else ""))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main()
