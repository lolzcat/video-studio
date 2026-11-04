#!/usr/bin/env bash
# Install video-studio for Claude Code.
#
#   ./install.sh           link the skills into ~/.claude/skills and report missing tools
#   ./install.sh --deps    also install missing tools (Homebrew, uv tools, HyperFrames plugin)
#   ./install.sh --check   only report what's installed; change nothing
#
# Safe to re-run. Never overwrites a real (non-symlink) skill folder.
set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"
mode="${1:-link}"
case "$mode" in link|--deps|--check) ;; *) sed -n 2,8p "$0"; exit 1 ;; esac

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✗\033[0m %s  →  %s\n' "$1" "$2"; missing=$((missing + 1)); }
have() { command -v "$1" >/dev/null 2>&1; }
missing=0

# --- platform ---
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "warning: transcription (parakeet-mlx, mlx_whisper) needs a Mac with Apple Silicon."
fi

# --- install missing tools ---
if [ "$mode" = "--deps" ]; then
  echo "Installing missing tools…"
  have brew || { echo "Homebrew is required: https://brew.sh — install it, then re-run."; exit 1; }
  pkgs=()
  have ffmpeg || pkgs+=(ffmpeg)
  have yt-dlp || pkgs+=(yt-dlp)
  have uv     || pkgs+=(uv)
  have node   || pkgs+=(node)
  [ ${#pkgs[@]} -gt 0 ] && brew install "${pkgs[@]}"
  export PATH="$HOME/.local/bin:$PATH"
  have parakeet-mlx || uv tool install parakeet-mlx --python 3.12
  have mlx_whisper  || uv tool install mlx-whisper --python 3.12
  if have claude; then
    if ! claude plugin list 2>/dev/null | grep -q 'hyperframes'; then
      claude plugin marketplace add heygen-com/hyperframes || true
      claude plugin install hyperframes@hyperframes
    fi
  else
    echo "Claude Code CLI not found; install the HyperFrames plugin from inside Claude Code later."
  fi
fi

# --- link skills ---
if [ "$mode" != "--check" ]; then
  dest="$HOME/.claude/skills"
  mkdir -p "$dest"
  echo "Linking skills into $dest"
  for skill in "$repo"/skills/*/; do
    name="$(basename "$skill")"
    target="$dest/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
      echo "  skip $name: $target exists and is not a symlink (move it aside first)"
      continue
    fi
    ln -sfn "${skill%/}" "$target"
    echo "  linked $name"
  done
fi

# --- checklist ---
echo "Checklist"
export PATH="$HOME/.local/bin:$PATH"
for t in ffmpeg ffprobe; do have "$t" && ok "$t" || miss "$t" "brew install ffmpeg"; done
have yt-dlp && ok "yt-dlp $(yt-dlp --version)" || miss yt-dlp "brew install yt-dlp"
have uv && ok "uv" || miss uv "brew install uv"
have python3 && ok "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" || miss python3 "brew install python"
if have node; then
  major="$(node -v | sed 's/^v\([0-9]*\).*/\1/')"
  [ "$major" -ge 18 ] && ok "node $(node -v)" || miss "node $(node -v)" "needs 18+: brew upgrade node"
else miss node "brew install node"; fi
have parakeet-mlx && ok parakeet-mlx || miss parakeet-mlx "uv tool install parakeet-mlx --python 3.12"
have mlx_whisper && ok mlx_whisper || miss mlx_whisper "uv tool install mlx-whisper --python 3.12 (only for non-English)"
if ls "$HOME"/.claude/plugins/cache/hyperframes/hyperframes/*/skills/hyperframes/scripts/plugin-cli.mjs >/dev/null 2>&1; then
  ok "HyperFrames plugin $(basename "$(ls -d "$HOME"/.claude/plugins/cache/hyperframes/hyperframes/*/ | tail -1)")"
else miss "HyperFrames plugin" "claude plugin marketplace add heygen-com/hyperframes && claude plugin install hyperframes@hyperframes"; fi
for skill in "$repo"/skills/*/; do
  name="$(basename "$skill")"
  [ -L "$HOME/.claude/skills/$name" ] && ok "skill /$name" || miss "skill /$name" "./install.sh"
done

if [ "$missing" -eq 0 ]; then
  echo "All set. Restart Claude Code if you just installed anything, then try /youtube-edit."
else
  echo "$missing missing. Run ./install.sh --deps, or install the items above by hand."
  [ "$mode" = "--check" ] && exit 1
fi
exit 0
