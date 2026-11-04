#!/usr/bin/env python3
"""Burned-in captions: chunk words_cut.json into short caption groups for the composition.

Usage: captions.py <workdir> [--max-words 4] [--max-s 2.2] [--gap 0.45]

Reads <workdir>/words_cut.json (ASR of the cut) and the optional "captions" block of
<workdir>/overlays.json:
  "captions": {
    "y": 1310,                       # centre line of the caption band (px); default 68% of height
    "fixes": {"revers": "roofers", "Reune": "Reoon"},   # ASR spelling fixes (case-insensitive)
    "emphasis": ["Lumrid", "free"],  # words shown in the accent colour (numbers always are)
    "max_words": 4,
    "glue": ["US", "ripped"],        # never end a caption on these here ("US / Open")
    "max_merge": 4,                  # short groups merge up to this many words (default max_words+3)
    "max_chars": 22,                 # one line only: break/merge by characters (76px Inter ≈ 22)
    "plain": true                    # K2: no accent words when a headline card owns the accent
  }
Writes:
  <workdir>/public/captions.js   window.__CAPS = [{in, out, words: [{t, em}]}]   (composition reads it)
  <workdir>/captions.srt         the same captions as a subtitle file for platform upload
Grouping (after HyperFrames' caption-grouping rules, tightened for short-form): new group at a
pause >= --gap, at . ? !, at a comma followed by a pause, or when a group hits --max-words
words or --max-s seconds. One group on screen at a time; filler (um/uh) is dropped.
"""
import json, os, re, sys

FILLER = {"um", "uh", "erm", "uhh", "umm", "hmm"}
# A caption shouldn't end on a word that leans on the next one ("The problem with these / lists").
WEAK = {"the", "a", "an", "to", "of", "with", "for", "in", "on", "at", "and", "or", "but", "so", "is",
        "are", "was", "that", "these", "those", "this", "our", "my", "your", "we", "i", "i'm", "we're",
        "gonna", "be", "if", "as", "from", "about", "really", "very", "some", "use"}


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def tidy(word, fixes):
    core = re.sub(r"^[^\w$]+|[^\w%]+$", "", word)
    tail = word[len(word.rstrip(".,!?;:")):]
    fixed = fixes.get(core.lower())
    if fixed:
        word = fixed + tail
    m = re.fullmatch(r"(\$?)(\d{4,})([.,!?]?)", word)
    if m:  # 1100 -> 1,100
        word = f"{m[1]}{int(m[2]):,}{m[3]}"
    return word


def srt_time(t):
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"


def main():
    workdir = sys.argv[1]
    words = json.load(open(os.path.join(workdir, "words_cut.json")))
    ov_path = os.path.join(workdir, "overlays.json")
    cfg = (json.load(open(ov_path)).get("captions", {}) if os.path.exists(ov_path) else {})
    fixes = {k.lower(): v for k, v in cfg.get("fixes", {}).items()}
    emph = {re.sub(r"[^\w$%']", "", e).lower() for e in cfg.get("emphasis", [])}
    max_w, max_s, gap = arg("--max-words", int(cfg.get("max_words", 4))), arg("--max-s", 2.2), arg("--gap", 0.45)
    # "glue": words that must stay with the next one for this video ("US" Open, "ripped" jeans)
    weak = WEAK | {g.lower() for g in cfg.get("glue", [])}
    # a too-short group merges into a neighbour up to this many words (default allows a 2-line
    # caption; set it to max_words to keep every caption on one line)
    max_merge = int(cfg.get("max_merge", max_w + 3))
    # "max_chars": keep every caption on one line — break a group before it would pass this many
    # characters, and never merge past it (~22 for 76px Inter across 940px)
    max_chars = cfg.get("max_chars")
    # "plain": no accent words at all (K2: a headline card owns the accent colour)
    plain = bool(cfg.get("plain", False))

    def chars(g):
        return len(" ".join(tidy(x["text"], fixes) for x in g))

    def fits(g):
        return max_chars is None or chars(g) <= int(max_chars)

    words = [w for w in words if re.sub(r"\W", "", w["text"]).lower() not in FILLER]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        pause = (nxt["start"] - w["end"]) if nxt else 99
        end_sent = tidy(w["text"], fixes)[-1:] in ".?!"   # a fix can add the full stop
        comma_pause = w["text"].endswith(",") and pause >= 0.25
        long = len(cur) >= max_w or (w["end"] - cur[0]["start"]) >= max_s \
            or (nxt is not None and not fits(cur + [nxt]))
        if not nxt or pause >= gap or end_sent or comma_pause:
            groups.append(cur)
            cur = []
        elif long:
            carry = []  # forced break: don't strand weak words at the end of the line
            while len(cur) > 2 and re.sub(r"[^\w']", "", tidy(cur[-1]["text"], fixes)).lower() in weak:
                carry.insert(0, cur.pop())
            groups.append(cur)
            cur = carry
    # Nothing may flash by: a group under 0.5s merges into its neighbour (next first, so the
    # phrase reads forward, up to max_w + 3 words = two lines), else into the previous one.
    def dur(g):
        return g[-1]["end"] - g[0]["start"]

    merged = list(groups)
    changed = True
    while changed:
        changed = False
        for i, g in enumerate(merged):
            if dur(g) >= 0.5 or len(merged) == 1:
                continue
            nxt = merged[i + 1] if i + 1 < len(merged) else None
            prv = merged[i - 1] if i > 0 else None
            if nxt and len(g) + len(nxt) <= max_merge and fits(g + nxt) and nxt[0]["start"] - g[-1]["end"] < gap \
                    and g[-1]["text"][-1:] not in ".?!":
                merged[i:i + 2] = [g + nxt]
            elif prv and len(prv) + len(g) <= max_merge - 1 and fits(prv + g) and g[0]["start"] - prv[-1]["end"] < gap:
                merged[i - 1:i + 1] = [prv + g]
            else:
                continue
            changed = True
            break

    caps = []
    for k, g in enumerate(merged):
        t_in = max(0.0, g[0]["start"] - 0.06)
        nxt_in = merged[k + 1][0]["start"] - 0.06 if k + 1 < len(merged) else g[-1]["end"] + 0.5
        t_out = g[-1]["end"] + 0.35
        if t_out >= nxt_in - 0.25:  # short gap: hold until the next group (a 1-frame blank reads as flicker)
            t_out = nxt_in
        ws = []
        for w in g:
            t = tidy(w["text"], fixes)
            bare = re.sub(r"[^\w$%']", "", t).lower()
            ws.append({"t": t, "em": not plain and (bool(re.search(r"\d", t)) or bare in emph)})
        # A cut that starts mid-sentence ("[Regarding the] dress code…") still opens a sentence on screen.
        if ws and (not caps or re.search(r"[.?!]$", caps[-1]["words"][-1]["t"])):
            ws[0]["t"] = ws[0]["t"][:1].upper() + ws[0]["t"][1:]
        caps.append({"in": round(t_in, 3), "out": round(min(max(t_out, t_in + 0.3), nxt_in), 3), "words": ws})

    cut = os.path.join(workdir, "cut.mp4")  # no cue may outlast the video (last one gets +0.5s)
    if os.path.exists(cut) and caps:
        import subprocess
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", cut], capture_output=True, text=True).stdout.strip() or 0)
        if dur:
            for c in caps:
                c["out"] = round(min(c["out"], dur - 0.05), 3)

    pub = os.path.join(workdir, "public")
    os.makedirs(pub, exist_ok=True)
    with open(os.path.join(pub, "captions.js"), "w") as f:
        f.write("window.__CAPS = " + json.dumps(caps, ensure_ascii=False) + ";\n")
        f.write(f"window.__CAPS_Y = {int(cfg.get('y', 0)) or 'null'};\n")
    with open(os.path.join(workdir, "captions.srt"), "w") as f:
        for n, c in enumerate(caps, 1):
            f.write(f"{n}\n{srt_time(c['in'])} --> {srt_time(c['out'])}\n{' '.join(w['t'] for w in c['words'])}\n\n")
    print(f"{len(caps)} caption groups from {len(words)} words -> {pub}/captions.js, {workdir}/captions.srt")
    for c in caps:
        print(f"  {c['in']:6.2f}-{c['out']:6.2f}  " + " ".join(("*" + w["t"] + "*") if w["em"] else w["t"] for w in c["words"]))


if __name__ == "__main__":
    main()
