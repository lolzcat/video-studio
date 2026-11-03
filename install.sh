#!/usr/bin/env bash
# Link every skill in this repo into ~/.claude/skills so Claude Code loads it.
# Safe to re-run. Refuses to overwrite a real (non-symlink) skill folder.
set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.claude/skills"
mkdir -p "$dest"
for skill in "$repo"/skills/*/; do
  name="$(basename "$skill")"
  target="$dest/$name"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "skip $name: $target exists and is not a symlink (move it aside first)"
    continue
  fi
  ln -sfn "${skill%/}" "$target"
  echo "linked $name -> ${skill%/}"
done
