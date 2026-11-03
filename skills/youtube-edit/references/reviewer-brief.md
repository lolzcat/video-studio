# Independent reviewer brief

The editor (main session) fills in `{…}` and sends this as the prompt to a **fresh**
agent (`Agent`, `general-purpose`). Send only this brief — never the editor's notes,
reasoning, or opinion of the edit. The reviewer's job is to find what's wrong.

---

You are reviewing an edited YouTube video for Andrew. You did not make it and have no
stake in it. Find what's wrong; do not praise. Be concrete: every issue needs a
timestamp (on the delivered video's timeline) and the STYLE.md rule it breaks.

**Files**
- Video: `{workdir}/{final}`  ({duration}s, {format}: hook | short | full)
- Andrew's rules: `~/.claude/skills/youtube-edit/STYLE.md` — the standard you judge against
- What is said, with word times: `{workdir}/words_cut.json`
- Graphic plan: `{workdir}/overlays.json` (card times, text, boxes)
- Sound sync sheet: `{workdir}/sync_sheet.png` (+ its table: `{sync_table}`)
- Automated checks already run: `{check_plan_output}` / `{qc_output}`
- Source of any on-screen claim/B-roll: `{sources}`

**How to look** (you can't watch video — sample it):
1. `ffmpeg -ss <t> -i <video> -frames:v 1 -vf scale=540:-2 <out>.jpg` at: 0.5s, 1.5s,
   2.5s, the middle of every card, 0.1s after every card start, and either side of a few
   cuts. Read the images. Also build one contact sheet of 1 frame every 2s
   (`-vf fps=0.5,scale=180:-2,tile=8x<rows>`) for pacing.
2. Read `words_cut.json` as a script: does the edit make sense, does any line start or
   end mid-thought, any repeated idea, any leftover filler?
3. Read the sync sheet image and table.

**Score 1–10 each (10 = Andrew would post it untouched):**
| category | what to check |
|---|---|
| hook | first 3s: is there a reason to keep watching, and does something hit the screen (H1)? |
| story | cut makes sense, no mid-thought ends, no repeats, no filler left (C1–C5) |
| pacing | visual change every 2–4s in shorts/hooks (G2); no dead stretches |
| readability | every word readable at phone size (T1), contrast, nothing clipped off-frame |
| graphics | spelling vs on-screen/transcript, numbers match what's said, one at a time (G1), never over the face (G3), look matches L1–L4 |
| sound | SFX audible and on the visual (sync sheet), music under voice (S1–S5), nothing harsh |
| accuracy | every on-screen claim/stat/name is supported by the source; flag anything stronger than what was said |
| polish | jump-cut framing, zoom crops, transitions, ending lands |

**Verdict.** `pass` only if overall ≥ 8.0, no category below 6, and no blocker.
Blocker = factual error, misspelled name, text over the face, unreadable text, black/
frozen frame, inaudible voice, or an ending that cuts off a word.

**Reply with exactly this JSON** (then nothing else):
```json
{
  "verdict": "pass" | "revise",
  "overall": 0.0,
  "scores": {"hook": 0, "story": 0, "pacing": 0, "readability": 0, "graphics": 0, "sound": 0, "accuracy": 0, "polish": 0},
  "blockers": [{"t": "0:06", "rule": "G3", "issue": "...", "fix": "..."}],
  "issues":   [{"t": "0:14", "rule": "T1", "severity": "high|med|low", "issue": "...", "fix": "..."}],
  "best_moment": "0:22 — one line on what works, so the editor doesn't break it"
}
```
