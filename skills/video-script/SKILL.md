---
name: video-script
description: Stage 2 of Andrew's video pipeline — turn an idea or a raw voice-note riff (plus an optional reference pack from /video-research) into hook options, a script in Andrew's own voice, a shot list with graphic/B-roll/zoom/SFX markers that /youtube-edit reads, and a recording checklist. Trigger on "script this", "write the script for", "turn my voice note into a video", "use this reference pack", "plan the video".
argument-hint: "<idea | voice-note text or audio file> [reference pack path]"
user-invocable: true
---

# Video script — idea to shootable script

Read first, every time:
- `~/Obsidian/Luxvoni/Content/content-engine-plan.md` — pillars, signature angle, the
  **anti-AI-slop rules** and banned words. They override anything below.
- `~/.claude/skills/youtube-edit/STYLE.md` — H1 (3s hook), G1–G6, T1, A1: the script must
  set the edit up to pass them.
- The reference pack, if given (`~/Obsidian/Luxvoni/Research/References/*.md`).
- [references/voice.md](references/voice.md) — how Andrew actually talks on camera (from
  his real takes) and the AI tells that make a script sound written instead of said.

`SKILL_DIR` = this folder.

Output: `script.md` from [references/script-template.md](references/script-template.md),
saved to `~/Movies/youtube-edit/<yyyy-mm-dd>-<slug>/script.md` (the folder the edit will
use) and copied to `~/Obsidian/Luxvoni/Content/Scripts/<yyyy-mm-dd>-<slug>.md`.

## 1. Get Andrew's raw material
**Andrew's own words beat anything written for him** (content-engine plan: "Andrew riffs
raw 60s → I shape his transcript"). In order of preference:
1. A voice note / riff — text, or an audio/video file: transcribe it with
   `python3 ~/.claude/skills/youtube-edit/scripts/transcribe.py <file> <dir>`.
2. Bullet notes or a one-line idea → ask him for a 60-second riff on it first; only draft
   from scratch if he says so, and mark those lines `[DRAFT — say it your way]`.
Ask for anything only he has: the real number, the real tool, the real result, the failure.

## 2. Brief (5 lines)
Audience · the one promise · format + target length (short ≤ 60s / long) · pillar(s) ·
the reference pattern being used (from the pack) — or "none".

## 3. Hooks — write 3, recommend 1
Different types, each ≤ 2 sentences, each makes sense with **no setup** (no "And just
like that", no "In this video"), and each pairs with something that hits the screen by 1s:
result-first ("I got 226 good emails out of 1,100 for $0"), number-shock, challenge,
myth-bust, "you're doing X wrong". If a reference pack exists, one hook uses its proven
hook *type* — in Andrew's words, with his numbers.

## 4. Beat outline with a time budget
Hook (0–3s) → setup → turn/problem → proof (the screen, the number) → payoff → CTA.
Shorts: ≤ 6 beats, ~150 words/min of Andrew's natural pace. Note where the reference's
beats were, so the pacing is a deliberate choice.

## 5. The script + shot list
Numbered lines `L1, L2 …`, written the way **he** talks (voice.md): connectors ("So…",
"Alright…", "And…"), "gonna", plain cause-and-effect, honest hedges, concrete numbers —
some lines long and rambly, some short. No slogan triplets, mic-drop fragments, mirrored
taglines, "not X, it's Y", em dashes, or hype words. Under each line, the markers `/youtube-edit` consumes:
- `[GRAPHIC: <1–3 word pop or number card>]` — what text hits the screen (G4, T1)
- `[B-ROLL: <real source URL or "my screen: …">]` — real sources only (G6)
- `[SCREEN: <what to show in the screen recording while saying this>]`
- `[ZOOM]` on emphasis lines · `[SFX: pop|whoosh|click]` sparingly (S3)
- `[CLAIM: <stat/name to verify>]` — anything factual (A1)
No marker means face + voice only. Keep graphics ≤ 1 per line.

**Voice check (never skip):**
```bash
python3 "$SKILL_DIR/scripts/voice_check.py" <script.md> --ref <reference transcript.txt>
```
Fix every flag (or keep a line only if Andrew really says it that way), re-run until PASS.
`--ref` also catches 4-word phrases lifted from the reference video.

## 6. Recording checklist
Setup (layout, e.g. screen top / face bottom; mic; lighting) · say every hook **2–3 times**
· pause ~1s between lines (clean cut points) · the screen actions to perform, in order ·
lines to repeat if stumbled · total takes expected.

## 7. Teleprompter + extras
A plain teleprompter block (lines only, no markers). Then, from the same material:
3 title options (≤ 60 chars), a thumbnail idea (one image + ≤ 4 words), and — for long
videos — 4–6 short cut-down moments (line ranges + standalone hook each).

## 8. Flags
Everything Andrew must confirm: numbers, names, claims, any `[DRAFT]` line.

## Keep the voice guide growing
After each recording, add 5–10 of Andrew's best natural lines from the edit's
`cut_asr/transcript.txt` to **Real lines** in voice.md, and any new AI tell he calls out to
the "does NOT sound like him" list. The more real lines it holds, the more scripts sound
like him.

## Rules
- Never write in the banned-filler voice (see content-engine plan). No guru-speak.
- Reference packs give **structure**; the words, numbers and examples are Andrew's.
  Never reuse a reference's script lines or put its creator's income in Andrew's mouth.
- Chinese-remake scripts are localized to US platforms, tools and money (see the pack's
  Localization table).
