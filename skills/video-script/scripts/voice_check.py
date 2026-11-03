#!/usr/bin/env python3
"""Flag lines in a script that sound written-by-AI instead of said-by-Andrew.

Usage: voice_check.py <script.md | lines.txt> [--ref <reference transcript.txt> ...]
                      [--allow "<trend phrase>" ...]

Reads the "## Teleprompter" block of a script.md (or every non-empty line of a .txt).
Per line it flags: hype/self-help vocabulary, em dashes/semicolons, "not X, it's Y"
framing, slogan triplets, mic-drop fragments, mirrored sentences, missing contractions.
Whole script: share of lines that start with a connector (So/And/Now/Alright…), and
whether line lengths vary like real speech. With --ref, flags any 4-word phrase copied
from a reference video's transcript (4-word phrases); --allow exempts a trend phrase the
video is MEANT to reuse (the shared line of a trend, e.g. "change your life in six months").
See references/voice.md for the why.
Exit 1 if anything is flagged.
"""
import re, statistics, sys

HYPE = ["unlock", "leverage", "game-changer", "game changer", "10x", "dive in", "dive into",
        "journey", "transform", "elevate", "level up", "mindset shift", "stupid simple",
        "here's the thing", "let that sink in", "the truth is", "real talk", "in today's world",
        "next level", "crush it", "grind", "hustle culture", "manifest", "unleash", "supercharge",
        "seamless", "harness", "embark", "delve", "the secret", "nobody talks about"]
CONNECTORS = ("so", "and", "but", "now", "alright", "all right", "because", "like", "okay", "ok",
              "look", "yeah", "honestly", "anyway", "then", "plus", "which", "if")
UNCONTRACTED = [r"\bI am\b", r"\bdo not\b", r"\bdoes not\b", r"\bit is\b", r"\bwe are\b",
                r"\byou are\b", r"\bthey are\b", r"\bcannot\b", r"\bwill not\b", r"\bI will\b",
                r"\bI have (?:been|done|tried|seen|heard|made|had|got|gotten|started|quit|built|spent)\b", r"\bthat is\b", r"\bthere is\b", r"\bwhat is\b"]
SAYS_OK = {"six months.", "day one.", "today's day one.", "today's day 1."}  # trend hooks are said this way


def lines_of(path):
    text = open(path).read()
    m = re.search(r"^## Teleprompter\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    block = m.group(1) if m else text
    out = []
    for raw in block.splitlines():
        s = re.sub(r"\(.*?\)", "", raw).strip().strip('"').strip()
        if s and not s.startswith(("#", "-", "|", "[", "---")):
            out.append(s)
    return out


def flags_for(line):
    f, low = [], line.lower()
    for w in HYPE:
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            f.append(f'hype word "{w}"')
    if "—" in line or "–" in line or ";" in line:
        f.append("em dash/semicolon (nobody speaks punctuation; use and/but/so)")
    if re.search(r"\b(not|isn't|aren't|wasn't)\b[^.?!]{0,40}[,.]\s*(it's|it is|i'm|we're|this is)\b", low) \
            or re.search(r"\bi'm not [^.?!]+\.\s*i'm\b", low):
        f.append('"not X, it\'s Y" framing')
    if re.search(r"^[\w' ]{1,20}, [\w' ]{1,20},? and [\w' ]{1,25}\.\s*\S", line) or "all three" in low:
        f.append("slogan triplet (list it inside a normal sentence, or cut to one)")
    words = re.findall(r"[\w']+", line)
    if len(words) <= 3 and not low.startswith(CONNECTORS) and low not in SAYS_OK and not line.endswith("?"):
        f.append("mic-drop fragment (join it to the line before or after)")
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
    if len(sents) >= 2:
        a, b = (re.findall(r"[\w']+", s.lower()) for s in sents[:2])
        if a[:2] == b[:2] or (len(a) == len(b) and len(a) <= 8 and a[0] == b[0]):
            f.append("mirrored sentences (reads like a tagline)")
    if re.search(r"\b\w+ on \w+day, \w+ by \w+day\b", low):
        f.append("mirrored sentences (reads like a tagline)")
    for pat in UNCONTRACTED:
        if re.search(pat, line, re.I):
            f.append(f'uncontracted "{re.search(pat, line, re.I).group(0)}"')
            break
    return f


def ngrams(text, n=4):
    w = re.findall(r"[\w']+", text.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def main():
    args = sys.argv[1:]
    path = args[0]
    refs = [args[i + 1] for i, a in enumerate(args) if a == "--ref"]
    allowed = set()
    for a in (args[i + 1] for i, x in enumerate(args) if x == "--allow"):
        allowed |= ngrams(a)
    lines = lines_of(path)
    ref_grams = set()
    for r in refs:
        ref_grams |= ngrams(re.sub(r"\[[\d:]+\]", " ", open(r).read()))
    total = 0
    print(f"Voice check {path} ({len(lines)} lines)")
    for i, line in enumerate(lines, 1):
        f = flags_for(line)
        copied = sorted(g for g in ngrams(line) if g in ref_grams and g not in allowed)
        if copied:
            f.append(f'copied from reference: "{copied[0]}"')
        if f:
            total += len(f)
            print(f"  {i:>2}. {line}\n      -> " + "; ".join(f))
    starts = sum(1 for l in lines if l.lower().startswith(CONNECTORS))
    share = starts / len(lines) if lines else 0
    if share < 0.3:
        total += 1
        print(f"  SCRIPT: only {share:.0%} of lines start with a connector (So/And/Now/Alright…) — "
              f"Andrew's real takes link lines; aim for 30%+")
    counts = [len(re.findall(r"[\w']+", l)) for l in lines]
    if len(counts) > 4 and statistics.pstdev(counts) < 3:
        total += 1
        print(f"  SCRIPT: line lengths too even (stdev {statistics.pstdev(counts):.1f} words) — "
              f"mix long rambly lines with short ones")
    print(f"  {total} flag(s)" if total else "  PASS — sounds said, not written")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
