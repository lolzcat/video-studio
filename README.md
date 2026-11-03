# video-studio

Claude Code skills for Andrew's video pipeline, from idea to finished edit.

| Stage | Skill | What it does |
|---|---|---|
| 1. References | `video-research` | Pulls reference videos (URLs you give it, YouTube search, or trending Chinese platforms), measures what makes them work, and writes a reference pack |
| 2. Script | `video-script` | Turns your idea or voice-note riff and a reference pack into hooks, a script in your voice, a shot list, and a recording checklist |
| 3. Record | you | |
| 4. Edit | `youtube-edit` | Raw footage to finished edit: cuts, zooms, HyperFrames graphics, B-roll, music, SFX, QC, independent review |

Each skill's `SKILL.md` has the full workflow. `youtube-edit/STYLE.md` holds the editing rules learned from feedback; `youtube-edit/references/feedback-log.md` records why each rule exists.

## Style profiles

`styles/*.md` are style profiles built from creator studies (`/video-research` creator
study mode). Tell `/video-script` or `/youtube-edit` "use style <name>" to apply one on top
of `youtube-edit/STYLE.md`. `short-form-v1` comes from 30 reels by three talking-head creators.

## Install

```bash
./install.sh
```

This links every folder in `skills/` into `~/.claude/skills/`. Edit the skills here, commit after each round of feedback, and the history shows how the style evolved.

## Requirements

ffmpeg, `uv`, `yt-dlp`, `parakeet-mlx` (`uv tool install parakeet-mlx --python 3.12`), `mlx_whisper` (for non-English audio), and the HyperFrames Claude Code plugin. Optional: Epidemic Sound and Tella connectors; an ElevenLabs key for generated music/SFX.
