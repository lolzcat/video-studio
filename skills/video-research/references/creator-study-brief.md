# Creator study brief

The main session fills in `{…}` and sends this to one agent per creator (in parallel).
Output: `{dir}/study.md`. The main session then writes the cross-creator synthesis and
the style profile.

---

You are breaking down one short-form creator's videos at an obsessive level of detail, so
Andrew (AI + cold outreach + ADHD + making money online; films selfie/car talking-head
and split-screen tutorials) can learn the **style and structure**. Not their identity: no
catchphrases, branding or footage copied. Be concrete and timestamped. Separate what you
**measured** (from the json files) from what you **judged** (from frames and transcript).

**Creator:** {handle} — {who they are, follower count if known}
**Videos:** `{dir}/NN-<id>/` folders, one per video. Views per video (from the profile grid;
`null` = unknown): `{views_json}`
**In each folder:** `meta.json` (likes, comments, date), `transcript.txt`, `stats.json` (cuts/min,
LUFS…), `sheet.jpg` (whole-video contact sheet), `hook.jpg`.

**Step 1: run the shot tool on every video** (it writes `shots.json`, `shots_sheet.jpg`,
`hook_strip.jpg` and `words.json` into the folder):
```bash
uv run ~/projects/video-studio/skills/video-research/scripts/shots.py <folder>
```
Then Read `hook_strip.jpg`, `shots_sheet.jpg`, `transcript.txt` and `shots.json` for every
video. If a folder has no video (blocked), work from transcript and cover only, and say so.

**Step 2: per-video breakdown** — for EACH video, this exact block:
```
### NN · <id> · <views> views · <likes> likes · <comments> comments · <dur>s · <date>
- Topic / promise:
- Format family: (name the repeatable format, e.g. "car confession", "results receipt")
- HOOK 0–3s, quarter-second by quarter-second: what is SAID, what is SHOWN (framing,
  text on screen, graphic/image), any SOUND hit; first cut at Xs; hook type; WHY it stops the scroll
- Shot list: every shot from shots.json → type (A-roll face / punch-in / screen rec /
  proof screenshot / B-roll literal / B-roll metaphor / stock / meme / text card / montage
  clip), length, what it shows, why it's there
- B-roll & graphics: count, share of runtime, literal vs metaphorical, placement relative to
  the words (on the word / before / after), entry style
- Text on screen: persistent title label? captions (font, size, color, placement, words
  per chunk, emphasis), other text
- Sound: music bed (or room/road noise), music changes, SFX hits (from sfx_candidates +
  frames), pauses, pace curve (pace_wpm_per_5s)
- Structure: beat outline with timestamps; open loops; pattern interrupts; payoff time
- CTA: exact words, mechanic (comment keyword / follow / DM / link), placement
- Engagement read: comments ÷ likes, likes ÷ views; what that says (comment-keyword CTA
  inflates comments)
- What's working (3 bullets, specific) · What's weak (1–2 bullets)
```

**Step 3: channel synthesis** (`## Channel synthesis`):
- **Signature moves** (things in nearly every video) — with counts ("9/10 open on…")
- **Hits vs misses** — compare the top-third by views against the bottom-third on every
  dimension above; list differences that show up consistently, with numbers. Say plainly
  when the sample is too small to be sure.
- **Format families** — 2–5 repeatable formats, each with its skeleton (beats + timing)
- **Hook formulas** — the 3–6 hook templates they reuse, each with an example
- **Production fingerprint** — median cuts/min, median shot length, first-cut time, B-roll
  share, caption style, LUFS, setting (car/desk/outdoor), framing, lighting
- **Evolution** — older vs newer videos: what changed
- **What Andrew should steal** (structure only) and **what to leave** (their identity)

Write everything to `{dir}/study.md`. Reply with a 10-line summary: the 5 most important
findings and the 3 formats most transferable to Andrew.
