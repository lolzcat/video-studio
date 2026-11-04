# video-studio

Claude Code skills for Andrew's video pipeline, from idea to finished edit.

| Stage | Skill | What it does |
|---|---|---|
| 1. References | `video-research` | Pulls reference videos (URLs you give it, YouTube search, or trending Chinese platforms), measures what makes them work, and writes a reference pack |
| 2. Script | `video-script` | Turns your idea or voice-note riff and a reference pack into hooks, a script in your voice, a shot list, and a recording checklist |
| 3. Record | you | |
| 4. Edit | `youtube-edit` | Raw footage to finished edit: cuts, zooms, HyperFrames graphics, B-roll, music, SFX, captions, QC, independent review |
| 5. Review | Cut Notes page | You leave notes pinned to exact frames; Claude reads them, applies them and replies on each one |

Each skill's `SKILL.md` has the full workflow. `youtube-edit/STYLE.md` holds the editing rules learned from feedback; `youtube-edit/references/feedback-log.md` records why each rule exists.

## Install

Needs a Mac with Apple Silicon (M1 or later), because transcription runs on MLX.

**1. Get the repo**
```bash
git clone https://github.com/lolzcat/video-studio.git ~/projects/video-studio
```

**2. Install the tools and link the skills**
```bash
~/projects/video-studio/install.sh --deps
```
This installs whatever is missing (Homebrew packages, `uv` tools and the HyperFrames
plugin), links every skill into `~/.claude/skills/`, and prints a checklist at the end.
Without `--deps` it only links the skills and reports what's missing. Safe to re-run.

**3. Restart Claude Code** so it loads the new skills and the plugin. Then check:
```bash
~/projects/video-studio/install.sh --check
```

**4. First run in Claude Code:** say `/youtube-edit` with a video. Step 0 (preflight) runs
`npx hyperframes doctor` and reports anything still missing.

### What gets installed

| Tool | Used for | Installed with |
|---|---|---|
| `ffmpeg`, `ffprobe` | every cut, mix, render and check | `brew install ffmpeg` |
| `yt-dlp` | pulling reference videos | `brew install yt-dlp` (on a YouTube 403, run `brew upgrade yt-dlp`) |
| `uv` | runs the numpy scripts (`timing.py`, `gaps.py`, `sync_sheet.py`, `shots.py`) with their own deps | `brew install uv` |
| Node 18+ | HyperFrames graphics renderer | `brew install node` |
| `parakeet-mlx` | English transcription with word timings | `uv tool install parakeet-mlx --python 3.12` |
| `mlx_whisper` | Chinese and other languages | `uv tool install mlx-whisper --python 3.12` |
| HyperFrames plugin | animated graphics, captions, scoreboard | `claude plugin marketplace add heygen-com/hyperframes` then `claude plugin install hyperframes@hyperframes` |

The other scripts use only the Python standard library (`python3` from macOS or Homebrew).
Whisper and Parakeet download their models (about 1–3 GB) the first time they run.

### Optional

- **Epidemic Sound** and **Tella**: connect them in Claude (Customize → Connectors). Without
  them the editor uses `youtube-edit/assets/` or generates sound with ElevenLabs.
- **ElevenLabs** (generated music and SFX): put `ELEVENLABS_API_KEY=...` in the `.env` file the
  skill reads (see `youtube-edit/SKILL.md` → step 7). Never commit the key.
- **Obsidian vault** at `~/Obsidian/Luxvoni` for reference packs and creator studies. Without it,
  packs stay in `~/Movies/youtube-edit/research/`.

## Cut Notes (timeline comments)

A review page where you scrub the video and leave notes pinned to exact frames
(pause → `N` → type → Enter). When you say "check my notes", Claude reads the open notes,
fixes them, replies on each one and uploads the next version.

- Andrew's page: https://claude.ai/artifact/VTAi9zqoZqYfLpGRuqALtL
- Source: [`skills/youtube-edit/review/cut-notes.html`](skills/youtube-edit/review/cut-notes.html)
- **On another claude.ai account**, ask Claude Code: "publish my own Cut Notes page from the
  video-studio repo". It follows `youtube-edit/SKILL.md` → Revisions → Cut Notes to publish a
  copy with its own database and swaps in the new URL.

Videos are uploaded as 720p proxies to the page itself; they never go in this repo.

## Style profiles

`styles/*.md` are style profiles built from creator studies (`/video-research` creator
study mode). Tell `/video-script` or `/youtube-edit` "use style <name>" to apply one on top
of `youtube-edit/STYLE.md`. `short-form-v1` comes from 30 reels by three talking-head creators.

## Where things land

| What | Where |
|---|---|
| Edits (one folder per video, versions `final_v1.mp4`, `final_v2.mp4`…) | `~/Movies/youtube-edit/<date>-<slug>/` |
| Daily series (three shorts a day + scoreboard) | `~/Movies/youtube-edit/series/<series>/day-NNN/` |
| Reference pulls | `~/Movies/youtube-edit/research/` |

## Updating

```bash
cd ~/projects/video-studio && git pull
```
The skills are symlinks, so a pull updates them in place. Re-run `./install.sh --deps` if a
new tool was added. When Claude changes a rule after your feedback, it commits here so the
history shows how the style evolved.
