---
name: video-research
description: Stage 1 of Andrew's video pipeline — pull reference videos to base a new video on and work out WHY they work. Two ways in — "find them for me" (YouTube search ranked by views/subscriber outliers, trending Chinese videos on Bilibili/Douyin/Xiaohongshu for English remakes that get ahead of the curve, plus the research agent's Daily Trends) or "here are my videos" (links or uploaded files). Produces a reference pack (hooks, beat structure, pacing stats, graphics style, title patterns, remake angles) for /video-script. Trigger on "find references for", "what's working on YouTube for", "pull these videos", "trending Chinese videos", "base a video on", "research a video idea".
argument-hint: "<topic | video links | files> [--cn] [--youtube]"
user-invocable: true
---

# Video research — reference pull

Goal: find videos that **over-performed** on an idea close to Andrew's, and extract the
**structure** that made them work (hook, beats, pacing, format) — never their words or
footage. Output is a reference pack that `/video-script` turns into Andrew's own video.

`SKILL_DIR` = this folder. Scripts: `scripts/find.py` (discover), `scripts/pull.py` (pull).
Pack template: [references/pack-template.md](references/pack-template.md).
Andrew's pillars, voice and anti-slop rules: `~/Obsidian/Luxvoni/Content/content-engine-plan.md`.

## 0. Pick the way in
If the request doesn't make it obvious, ask once (`AskUserQuestion`):
- **Find them for me** — on: YouTube / Chinese platforms (remake for English) / both
- **I'll give you videos** — links (any site yt-dlp supports) or files Andrew uploads/drops
Also ask the format if unclear: short (≤60s) or long-form.

## 1. Trend context (cheap, do first)
Read the newest `~/Obsidian/Luxvoni/Research/Daily Trends/*.md` and any matching
`Research/Last30Days/*.md` — the research agent's pain-point quotes are often the best
angle. For a fresh topic, run the `last30days` skill
(`python3 ~/.claude/skills/last30days/scripts/last30days.py "TOPIC" --emit=md --save-dir "$HOME/Obsidian/Luxvoni/Research/Last30Days"`).

## 2. Discover (find-for-me path)
Work dir: `~/Movies/youtube-edit/research/<yyyy-mm-dd>-<slug>/`.

**YouTube**
```bash
python3 "$SKILL_DIR/scripts/find.py" youtube "<query>" --n 15 --days 90 --out <dir>/yt.json
```
Rank by `outlier` (views ÷ subscribers; >1 strong, >5 exceptional) then views/day. Run
2–3 phrasings (the problem, the outcome, the tool). Shorts: add "#shorts" to the query.

**Chinese platforms — remake-for-English mode** (the "get ahead of the curve" play)
Translate the niche into 2–4 Chinese keyword sets, e.g. AI side income → `AI副业`,
`AI自动化 赚钱`, `AI接单`; cold outreach → `外贸开发信`, `客户开发 获客`, `冷邮件`;
ADHD → `ADHD 效率`, `多动症 自律`; tools → `AI工具 推荐`, `智能体 教程`.
```bash
python3 "$SKILL_DIR/scripts/find.py" bilibili "<中文 keywords>" --n 20 --days 60 --out <dir>/bili.json
python3 "$SKILL_DIR/scripts/find.py" bilibili-rank tech --out <dir>/bili-rank.json
```
- **Format trend** = the same format from ≥ 3 different creators inside 60 days (e.g.
  "couple does an AI side-gig challenge, month N, here's what we saved"). That beats any
  single viral video — it means the format travels.
- **Ahead-of-the-curve check:** translate the format into an English query and run
  `find.py youtube` on it. Few or weak English results = open lane; note it in the pack.
- **Douyin / Xiaohongshu / Kuaishou:** browse them in the built-in browser (search the
  Chinese keywords, read view/like counts on the page) and collect links. yt-dlp needs a
  cookies file for Douyin — Andrew exports it himself (`--cookies cookies.txt`); never
  read his browser's cookie store. Xiaohongshu/Kuaishou links usually pull without one.

Show Andrew the candidates as a table (views/day, outlier or save-rate, duration, date,
one line on why it's interesting) and let him pick 2–5. If he said "you pick", take the
top scorers that share a format, plus one wildcard.

## Creator discovery ("find good creators in my space")
1. **Candidates from reel search.** Search engines index Instagram reels, so in the built-in
   browser fetch `https://html.duckduckgo.com/html/?q=site:instagram.com/reel <niche query>`
   for 10–12 niche phrasings (the `.result__a` title starts with the creator name; the
   `.result__url` is the reel). TikTok search and topic pages need a login, so skip them. YouTube:
   `find.py youtube` (ignore channels with tiny absolute views — set a floor like 50K).
2. **Resolve handles + likes** without the browser:
   `yt-dlp --skip-download --print "%(channel)s\t%(like_count)s\t%(comment_count)s" <reel url>`.
   Rank by likes. Huge comments with low views means comment-bait; discard.
3. **Verify every candidate's grid** (`https://www.instagram.com/<handle>/reels/`). The
   pane renders lazily in the background, so take a tiny screenshot (scale 0.1), scroll,
   take another, THEN read `a[href*="/reel/"]` innerText (views) and the `og:description`
   follower count. Compute the recent median (skip the first 3, which are usually pinned),
   **median ÷ followers**, **hit rate** (share of reels at or above ⅓ of followers) and the best reel.
4. **Shortlist** by median ÷ followers and hit rate, compared within size bands (big accounts
   coast). Pull one reel per pick (`pull.py --max-seconds 60`) to check language and format
   before recommending. Hindi/Hinglish or clip pages are format references only.
5. Save the shortlist to `~/Obsidian/Luxvoni/Research/References/<date>-creator-shortlist.md`,
   then run creator study mode on the top 3.

## Creator study mode ("break down this creator")
For studying one creator's whole style (or several, side by side):
1. **List their videos with view counts.** YouTube/TikTok: `yt-dlp --flat-playlist` on the
   channel. Instagram blocks profile listing for yt-dlp, so open
   `https://www.instagram.com/<handle>/reels/` in the built-in browser, close the sign-up
   popup (never log in), and read the reel links + play counts from the grid
   (`a[href*="/reel/"]` → href + innerText). The first 3 are often pinned older hits.
2. **Pick 8–12 per creator**: their biggest hits AND their flops (the contrast is the
   point), plus any video Andrew sent. Save the counts to `<dir>/views.json`.
3. **Pull** each creator into its own folder (`pull.py … --out <dir>/<handle>`). Instagram and
   Bilibili pulls are paced automatically.
4. **One agent per creator, in parallel**, each given
   [references/creator-study-brief.md](references/creator-study-brief.md) filled in. Each runs
   `scripts/shots.py` on every video (real shot list, labelled per-shot frames, a hook strip
   every 0.25s, word-level pace and pauses, a music read, SFX candidates) and writes
   `<dir>/<handle>/study.md`: a breakdown of every video, then a channel synthesis (signature
   moves, hits vs misses, format families, hook formulas, production fingerprint, evolution).
5. **You write the cross-creator synthesis** and a **style profile**
   (`~/projects/video-studio/styles/<name>.md`, same rule format as youtube-edit/STYLE.md),
   which `/video-script` and `/youtube-edit` can be told to apply. Save the synthesis to
   `~/Obsidian/Luxvoni/Research/References/`.
Mimic **style and structure**, never identity: no catchphrases, branding, faces or footage.

## 3. Pull
```bash
python3 "$SKILL_DIR/scripts/pull.py" <url|file> [...] --out <dir>/pack --max-seconds 900
```
Per video: `meta.json`, `transcript.txt` (original language), `stats.json` (cuts/min,
median shot, first cut, words- or chars-per-min, LUFS, hook text), `hook.jpg` (0–3s),
`sheet.jpg` (whole video). Chinese ASR uses Whisper (auto). If YouTube returns 403,
update yt-dlp (`brew upgrade yt-dlp`) — YouTube breaks old versions every few months.

## 4. Study each video
Read `transcript.txt` (translate Chinese to English yourself; keep the original hook
line too), `hook.jpg`, `sheet.jpg`, `stats.json`. For each, pin down:
- **Hook** (first 1–3s): exact words + English, hook type (result-first, number-shock,
  challenge, myth-bust, question, "you're doing X wrong"), what's on screen.
- **Beats**: the outline with timestamps (setup → turn → proof → payoff → CTA).
- **Pacing**: cuts/min, median shot, first cut, talk speed — compare to Andrew's last edit.
- **Visual language**: from the sheet — text style, B-roll type, screen recording vs face,
  captions, zooms.
- **Why it worked** in one sentence, and the **comment demand** if visible.

## 5. Write the reference pack
Fill [references/pack-template.md](references/pack-template.md) and save it to
`~/Obsidian/Luxvoni/Research/References/<yyyy-mm-dd>-<slug>.md` (and copy to
`<dir>/pack.md`). The most important section is **What to take vs. leave**.

## 6. Hand off
Tell Andrew the top 1–2 angles in two lines each and offer `/video-script` with this pack.

## Rules (non-negotiable)
- **Structure, not substance.** Take the hook type, beat order, pacing and format. Never
  copy their script, jokes, titles word-for-word, thumbnails, or footage. The reference
  video files are for analysis only and never go into an edit.
- **Chinese remakes are Andrew's own videos**: same concept and format, his voice, his
  real examples and numbers, recorded by him. Never translate/dub and re-upload someone
  else's video — that's copyright infringement and YouTube demonetizes reused content.
- **Localize**: Chinese platforms and money don't transfer — 闲鱼/淘宝/抖音 gigs → Fiverr,
  Upwork, Etsy, TikTok Shop; RMB → USD at realistic US levels; Chinese tools → the US tool
  Andrew actually uses. Flag anything that doesn't have a US equivalent.
- **Check for paid promotion before calling anything a trend.** Course/tool funnels pay
  many creators to post the same testimonial format (Bilibili/Douyin especially): a named
  "teacher", "free trial class", "link in the pinned comment", certificates, student counts.
  When you see it, label the reference **sponsored funnel**, treat its numbers as marketing,
  and say whether the format trend is organic or bought. A bought trend can still be a
  great *contrarian* angle ("I tested what they're all selling").
- **Their income claims are theirs.** Never put another creator's numbers in Andrew's
  mouth; mark every claim from a reference as unverified (STYLE.md A1).
