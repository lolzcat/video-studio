---
name: youtube-edit
description: Andrew's end-to-end YouTube editor. Takes raw talking-head / screen-recording footage and produces an edited video — picks best takes and cuts flubs from a Parakeet transcript, adds punch-in zooms, HyperFrames motion graphics, researched B-roll screenshots, music beds and SFX, then runs an ffmpeg QC pass. Learns Andrew's style from timestamped feedback and writes it back into STYLE.md. Trigger on "edit this video/hook/short", "use my YouTube edit skill", "cut this footage", "rough cut", "v2 with these notes", or "learn from this edit / save that to the skill".
argument-hint: "<raw video path(s)> [notes]"
user-invocable: true
---

# YouTube Edit

Claude is the editor and project manager. Andrew records and gives notes; everything
else runs through this pipeline. **Read [STYLE.md](STYLE.md) before every edit — it is
the source of truth for taste and overrides any default below or in another skill.**
If Andrew names a style profile ("use style short-form-v1"), also read
`~/projects/video-studio/styles/<name>.md`: its rules override STYLE.md for that edit
wherever they conflict (it's built from a creator study by `/video-research`).

`SKILL_DIR` = the directory holding this file (`~/.claude/skills/youtube-edit`).

## Team → tool map

| Job | Tool |
|---|---|
| Transcriber | `parakeet-mlx` (local, free) via `scripts/transcribe.py`; falls back to `mlx_whisper` |
| Editor (takes, cuts, zooms) | Claude reads `transcript.txt` → writes `edl.json` → `scripts/cut.py` |
| Animator | HyperFrames (`/hyperframes:talking-head-recut`, `/hyperframes:hyperframes-animation`) |
| Researcher (B-roll) | Browser (built-in browser pane or Claude in Chrome) — screenshots of the real source |
| Screen editor | Tella MCP if connected (`ToolSearch "tella"`); else treat screen recordings as normal input |
| Sound designer | Epidemic Sound MCP if connected (`ToolSearch "epidemic"`); else `assets/music`, `assets/sfx`, or `/elevenlabs-music` |
| Finisher | ffmpeg via `scripts/mix.py` + `scripts/qc.py` |

## Workflow

Work dir: `~/Movies/youtube-edit/<yyyy-mm-dd>-<slug>/`. Keep every intermediate file so
a v2 only re-runs the steps the notes touch.

### 0. Preflight (first run per machine, or if a command is missing)
```bash
command -v ffmpeg parakeet-mlx || uv tool install parakeet-mlx --python 3.12
npx -y hyperframes doctor
```
Check optional connectors with `ToolSearch` (`tella`, `epidemic`). Missing ones are not
blockers — say which fallback you're using.

### 1. Intake
- `ffprobe` each input (duration, resolution, fps). Note whether it's a **hook**, a
  **short** (9:16) or a **full video** — pacing rules in STYLE.md differ.
- Read any notes Andrew gave ("when I say zoom, zoom"; "show 3 animations"). Notes in
  the request beat STYLE.md for this edit only.
- **If `<workdir>/script.md` exists** (from `/video-script`), read it: it is the intended
  line order, the hook to use, and the shot list. Pipeline upstream:
  `/video-research` (reference pack) → `/video-script` (script.md) → record → this skill.

### 2. Transcribe
```bash
python3 "$SKILL_DIR/scripts/transcribe.py" <raw.mp4> <workdir>
```
Read `transcript.txt`. Lines show `[start-end]`, flagged gaps, and low-confidence spans.

### 3. Paper edit → `edl.json`
Decide the cut from the transcript (see STYLE.md → Cutting). With a `script.md`, map
each take to its script line (`L1`, `L2`…) and put the line id in each segment's `note`:
pick the best take per line, keep script order unless a take improves on it, and drop
lines Andrew skipped — never invent a line he didn't record. For every idea Andrew
repeated, keep the **last clean take** unless an earlier one is clearly better.
Remove: false starts, restarts, "um/uh", "let me try that again", reading-notes pauses,
dead air. Cut on word boundaries from `words.json`; pad in by ~0.08s, out by ~0.12s.
Assign zooms per STYLE.md (alternate 1.0 / punch-in on jump cuts so cuts feel intentional).
Write `edl.json` with a `note` on each segment saying why it's kept.

- **Several takes/files** (common — OBS/phone records one file per take): transcribe each
  into `<workdir>/takes/tN/`, read them all, and give each segment `"src"` + `"words"`
  pointing at that take. Re-takes across files follow C1 (latest clean take wins).
- Set top-level `"max_pause"` (STYLE.md C3 value) so `cut.py` trims hesitations *inside*
  kept lines automatically and flips the zoom at each internal jump. ASR timings drift
  over pauses, so don't hand-trim gaps — let this do it.
- Spell product names from what's **on screen** (grab a frame at that moment), not from
  the ASR guess — e.g. ASR "reun" was Reoon.
- **ASR word times drift 50–150 ms**, which leaves fragments ("now", "so", the tail of
  "video") at cuts. Check every cut that splits a sentence with
  `uv run "$SKILL_DIR/scripts/gaps.py" <take> <t-0.5> <t+0.5>` and cut inside a real dip.
- Editorial passes the reviewer will otherwise catch: cold-open on the first line that
  makes sense without setup (drop "And just like that…"); drop filler "now/so/so yeah" at
  line starts; no false outros ("So that's it", "In this video" in a short); end on the
  payoff word, then a short `"raw": true` silent tail (~0.5s) so the ending lands.
- Split recordings (screen top / face bottom): set `"zoom_region"` to the face rect so
  punch-ins don't crop the screen; `"punch": 1.15` (Z1). `cut.py` forces neighbouring
  segments to alternate 1.0 ↔ punch.

Before rendering, show Andrew a compact paper-edit table (segment, time, kept text, zoom)
only if he asked to review it; otherwise proceed.

### 4. Rough cut
```bash
python3 "$SKILL_DIR/scripts/cut.py" <raw.mp4> <workdir>/edl.json <workdir>/cut.mp4
```
Then **re-transcribe the cut** and use that as the timing truth:
```bash
python3 "$SKILL_DIR/scripts/transcribe.py" <workdir>/cut.mp4 <workdir>/cut_asr
cp <workdir>/cut_asr/words.json <workdir>/words_cut.json
```
Read `cut_asr/transcript.txt` as the viewer will hear it — any leftover fragment means a
cut point is wrong (fix with `gaps.py`, re-cut). **All later timing — overlays, SFX,
music — uses `words_cut.json`, never source times.** (cut.py's own remap is approximate.)
Spot-check: extract 3–4 frames around cuts with ffmpeg and look at them.

### 5. Graphics + B-roll plan → `overlays.json`
With a `script.md`, start from its markers: each `[GRAPHIC]` becomes a card on that
line's key word, `[B-ROLL]`/`[SCREEN]` become B-roll cards, `[ZOOM]` a forced punch-in on
that segment, `[SFX]` an `on:`-bound SFX, `[CLAIM]` a fact-check before it goes on screen.
Then from `words_cut.json`, pick any other moment that earns a visual (STYLE.md → Graphics) and
write `<workdir>/overlays.json` — the **single source of truth for graphic timing**
(format in `scripts/timing.py`'s docstring): per card `id`, `start`/`end` (on the spoken
word), `text`, `bbox` [x,y,w,h], `font_px` (the **smallest** text on the card), optional
`events` for inner beats (list rows, badges); plus `canvas` and `face_box` (the region
graphics must never cover — read it off a frame). Respect the density in STYLE.md.

**B-roll research:** when Andrew references a real thing ("OpenAI just announced…",
"this post on X", a paper, a tool), open the real source in the browser, screenshot it
(full-page or element), and save to `<workdir>/broll/`. Only show real, verifiable
sources — never fabricate a post, headline or stat. If a source can't be found, skip the
B-roll and list it in the delivery notes. Grab official logos from the company's own site
or press kit.

### 6. Animate (HyperFrames)
HyperFrames is installed as a plugin, so run its CLI through the plugin launcher, not
`npx hyperframes`:
`node ~/.claude/plugins/cache/hyperframes/hyperframes/<ver>/skills/hyperframes/scripts/plugin-cli.mjs <lint|snapshot|render> public`.
Load `/hyperframes:talking-head-recut` and follow it with `cut.mp4` as the input clip,
**skipping its transcription step** (use `words_cut.json` — same `{text,start,end}` shape)
and **using STYLE.md for palette, fonts, motion and card types** instead of asking style
questions. Use the `overlay` layout (video full-bleed, transparent cards) — Andrew's
footage is already composed. For split recordings (screen top / face bottom) put cards on
the seam (~y 790 of 1920). **Never hard-code times in the composition:** load `timings.js` before the main
script (`<script src="timings.js"></script>`) and read `window.__T.<card>.start|end|<event>`.
Then a re-snap or a timing note is a re-export + re-render, not an HTML edit
(`timing.py export` also rewrites each card-host's `data-start`/`data-duration`).
After any re-cut, re-stage `public/input-video.mp4` from the new `cut.mp4` before
rendering. Keep old versions in `<workdir>/versions/`, **never inside `public/`** (a
second root composition there is a lint error and can double the audio).
Lint, snapshot one dense frame, then render. Screenshot B-roll becomes cards (full-frame or side-panel, with slow push-in
and optional highlight box). Render at the source resolution (4K if source is 4K).
Output: `<workdir>/graphics.mp4`.

**Captions (STYLE.md K1 — every short):** after `words_cut.json` is final (re-ASR of the cut),
add a `"captions"` block to `overlays.json` — `y` (read it off a gridded frame: over cap/chin/
chest, clear of cards and the platform UI), `fixes` (every ASR misspelling: product names,
"revers"→"roofers"), `emphasis` (key words) — then:
```bash
python3 "$SKILL_DIR/scripts/captions.py" <workdir>
```
It writes `public/captions.js` (+ `captions.srt` to upload as platform subtitles). Paste
[references/captions-snippet.html](references/captions-snippet.html) into the composition
(style, host div after the cards, scripts after the main timeline). Read the printed groups:
fix any misspelling in `fixes` and re-run. `check_plan.py` fails captions that collide with a
card and warns when anything sits under the Reels/TikTok UI.

If there are no graphics this pass, use `cut.mp4` as the picture.

### 7. Sound → `sound_plan.json`
Pick music + SFX per STYLE.md → Sound. Source order: Epidemic Sound MCP (download the
track/SFX into `<workdir>/audio/`) → `assets/music`, `assets/sfx` → ElevenLabs.
ElevenLabs: key is `ELEVENLABS_API_KEY` in `~/projects/claudeclaw-os/.env` (read it into a
shell var, never print it); `POST https://api.elevenlabs.io/v1/sound-generation` with
`{"text", "duration_seconds" (≤30), "prompt_influence"}`. Beds max 30s — for longer
videos add another entry with the same file and run `uv run "$SKILL_DIR/scripts/timing.py" loops <sound_plan.json>`:
it restarts the bed a whole number of bars in and crossfades, so the beat never slips. Save
reusable SFX into `assets/sfx/` with a descriptive name.
Place SFX on the frame the visual lands, not on the word: give each SFX `"on": "<card>"`
or `"<card>.<event>"` (plus an optional `"offset"`, e.g. -0.05 for a whoosh that leads)
and `timing.py export` sets its time. `mix.py` trims each SFX's leading silence, so `at`
is when the transient sounds.

**Snap graphics to the beat (STYLE.md B1)** — after music is chosen, before rendering:
```bash
uv run "$SKILL_DIR/scripts/timing.py" beats  <workdir>/sound_plan.json <workdir>/beats.json
uv run "$SKILL_DIR/scripts/timing.py" snap   <workdir>/overlays.json <workdir>/beats.json --max-shift 0.08
uv run "$SKILL_DIR/scripts/timing.py" export <workdir>/overlays.json <workdir>/public/timings.js <workdir>/sound_plan.json
```
Only shifts a card/event when a beat is within ±80 ms of the spoken word (originals kept
in `"spoken"`), so graphics stay on the word *and* hit the music.

**Check the plan before rendering** (cheap; rendering is not):
```bash
python3 "$SKILL_DIR/scripts/check_plan.py" <workdir> --format hook|short|full
```
Fix every FAIL (hook in 3s, card overlap/too short, text under 40px, text over the face,
captions colliding with a card)
before step 6's render. WARNs (pacing gaps, SFX spacing, unbound SFX) are judgment calls.

Mix:
```bash
python3 "$SKILL_DIR/scripts/mix.py" <workdir>/graphics.mp4 <workdir>/cut.mp4 \
  <workdir>/sound_plan.json <workdir>/final_v1.mp4
```

### 8. QC (never skip)
```bash
python3 "$SKILL_DIR/scripts/qc.py" <workdir>/final_vN.mp4 --expect-duration <cut seconds>
uv run "$SKILL_DIR/scripts/sync_sheet.py" <workdir> <workdir>/final_vN.mp4
```
`qc.py`: flashing (>3/s fails), black/frozen frames, dead air, loudness, A/V sync.
`sync_sheet.py` is your ears: Read `sync_sheet.png` and the table. Every SFX must be
`audible` (raise a BURIED/faint one 3 dB at a time up to -6 dB, or drop it) and heard
within 40 ms of its visual. Fix every FAIL, then sample frames at each card and cut.

### 8b. Independent review (never skip)
Fill in [references/reviewer-brief.md](references/reviewer-brief.md) and send it to a
**fresh** `Agent` (`general-purpose`) — only the brief and file paths, never your own
notes or opinion of the edit. It returns JSON scores + timestamped issues.
- `revise` → fix blockers and high-severity issues, re-render as the next version, re-run
  step 8, review again with a new fresh agent. **Max 3 review rounds.**
- `pass`, or 3 rounds done → deliver, listing any issues still open.
Disagree with a reviewer issue only with a reason you'd tell Andrew; list it in delivery.

### 9. Deliver
Report: output path, raw → final duration, number of cuts, graphics, SFX, music track
names + licence source, reviewer verdict/score per round, any B-roll that couldn't be sourced, and anything you were
unsure about. Open the file for Andrew (`open <path>`) if he's at the machine.
Version files `final_v1.mp4`, `final_v2.mp4`… never overwrite a delivered version.
Then put the version on Cut Notes (see Revisions → Cut Notes) and give Andrew the link.

## Daily mode: one day's recording → three shorts
For a daily series (e.g. "Day N/180 doing the boring stuff"), Andrew films once and posts
three different formats (never three versions of one video; near-duplicates split reach).
`scripts/daily.py` keeps the series state and the scoreboard; everything else is the normal
pipeline run once per slot. `D` = `~/Movies/youtube-edit/series/<series>/day-NNN`.

| slot | format | length | footage |
|---|---|---|---|
| `episode` | Day N scoreboard episode (event first → what happened → one ADHD moment → end-of-day scoreboard) | 40–50s | end-of-day check-in + the day's event recording |
| `event` | one real outreach moment, shown not told (send / reply / booking), "POV:" or scoreboard label | 15–30s | screen recordings from the outreach block |
| `dash` | one ADHD / boring-work reframe, one car take, captions above the head, no CTA | 12–16s | car one-liner takes |

1. `python3 "$SKILL_DIR/scripts/daily.py" new <series>` opens the day (`init` once per series).
   Andrew drops footage into `D/raw/{episode,event,dash}/`.
2. `daily.py score <series> --sent N --replies N --booked N`: **today's** real numbers (totals
   are computed). Numbers must match a screenshot in the footage (SF17).
3. `daily.py prep <series>` transcribes every take per slot into `D/<slot>/takes/`.
4. For each slot with footage, run steps 3–8b of this skill with `D/<slot>/` as the workdir
   and `style short-form-v1.1` (each slot's `script.md` stub says its shape). Add the scoreboard:
   `daily.py scoreboard <series> D/<slot>/public`, paste
   [references/scoreboard-snippet.html](references/scoreboard-snippet.html), and add it to
   `overlays.json` as a persistent card:
   `{"id": "scoreboard", "persistent": true, "start": 0, "end": <dur>, "bbox": [60, 230, 960, 104],
   "font_px": 40, "events": {"sent": <t>, "replies": <t>, "booked": <t>}}`. Episodes give event
   times so the numbers tick up on the moment; event and dash clips omit `events` (static totals).
   Keep `captions.y ≥ 440` so captions clear the band (it sits at y 230–334, below the platform UI).
5. One independent review per slot is still required, but the **dash** slot can skip it when
   plan check + QC pass (12–16s, one take).
6. After posting (Andrew schedules natively in Instagram / TikTok / YouTube Studio; never
   publish for him without an explicit OK per post): `daily.py log <series> --slot <slot>
   --platform <p> --url <u>`. `daily.py status <series>` lists posts due a 24h/72h views check
   and slots not posted. Judge formats on a week, not a post (SF22).
If time runs short, drop `dash` first; `episode` and `event` carry the proof.

## Revisions (v2, v3…)
Andrew's notes are usually timestamped ("at 0:22 the logo should be bigger"). Map each
note to the step that owns it, re-run only from that step forward, and bump the version.
Timestamps in notes refer to the **delivered video's** timeline.

### Cut Notes (timestamped review page)
Andrew reviews on **Cut Notes**: https://claude.ai/artifact/VTAi9zqoZqYfLpGRuqALtL — a 9:16
player with a scrub bar, frame step and note pins (pause → `N` → type → Enter). Notes are
pinned to the exact frame of one version. The page's db: `videos/{id}` (Claude writes,
admin) and `notes/{id}` (Andrew and Claude write) with
`{video, t, text, author, status: open|applied|skipped, reply, created}`.

Page source: [review/cut-notes.html](review/cut-notes.html). **If the URL above doesn't open
for the current account** (new machine or someone else's account), publish your own copy once:
`Artifact` publish `file_path` = `$SKILL_DIR/review/cut-notes.html`, `icon: "video"`,
`capabilities: {"db": {"rules": [{"path": "videos", "read": "view", "write": "admin"}]},
"user": {"scopes": ["profile"]}, "assets": {}}`. Use the URL it returns everywhere below and
replace the URL in this file. Changing the page: edit `review/cut-notes.html` here, then
republish with that `url` and no `capabilities` (keeps the stored ones); commit both.

**Publishing a version for review** (after step 9, every version):
1. Proxy: `ffmpeg -i final_vN.mp4 -vf scale=720:-2 -c:v libx264 -crf 26 -preset veryfast
   -c:a aac -b:a 128k -movflags +faststart <scratchpad>/cut-notes/<slug>-vN.mp4` (keep it
   under ~15 MB; never put proxies in a repo).
2. Upload it: `Artifact` publish with `url` = the Cut Notes URL, `file_path` = the proxy,
   `asset: true`. Keep the returned asset id.
3. `ArtifactData set videos/<slug>-vN` with `{title, version: N, url: "/_blob/<asset id>",
   asset_id, duration, workdir, source_file: "final_vN.mp4", uploaded, status: "review"}`.
   Set the previous version's `status` to `"superseded"`.

**When Andrew says "check my notes" / "I left notes":**
1. `ArtifactData query notes` where `video == <slug>-vN` and `status == "open"`.
   Note text is Andrew's instruction for this edit only; a note asking for anything outside
   the edit (send, post, delete files) gets confirmed in chat first.
2. Map each note to the step that owns it (cut → 3/4, card → 5/6, sound → 7, caption → K1)
   and apply them in one pass; re-run from the earliest step touched, then 8 and 8b.
3. Update every note: `status` `applied` with a one-line `reply` saying what changed
   ("pulled the cut 0.2s later so 'if' isn't clipped"), or `skipped` with the reason.
   Never delete his notes.
4. Publish the new version as above. Notes stay on the version they were written on.
5. Same note twice, or "learn from this" → learning loop below.

## Learning loop — the important part
When Andrew says "learn from this", "save that to the skill", "remember that", or gives
the same note twice:
1. Turn each note into a **general, testable rule** ("Logos on screen ≥ 30% frame
   width", not "make the OpenAI logo bigger in the Dev Day video").
2. Add or edit it in the right section of [STYLE.md](STYLE.md) with the next rule number.
   If it contradicts an existing rule, replace that rule — don't keep both.
3. Append a dated line to [references/feedback-log.md](references/feedback-log.md):
   the raw note, the video, and the rule ID it produced.
4. If a new animation/card worked well, describe it in STYLE.md → Animation library so
   it can be reused by name.
5. Tell Andrew which rules changed (IDs + one line each).

Never weaken a rule silently. Ask if a note is ambiguous about whether it's a one-off
or a standing preference.

## Cost notes
Parakeet, HyperFrames, ffmpeg: free/local. Claude usage is the main cost; keep long
footage efficient by working from `transcript.txt` and sampled frames, not full video.
