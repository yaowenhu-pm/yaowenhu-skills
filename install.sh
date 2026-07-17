#!/usr/bin/env bash
# infiDive-skills 安装器:软链本仓库所有 skill 到 Codex / Claude。
# 新人首次 + 每次 git pull 后都可重复跑,幂等。
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DESTS=("$HOME/.codex/skills" "$HOME/.claude/skills")
for DEST in "${DESTS[@]}"; do
  mkdir -p "$DEST"
  echo "软链 skill → $DEST"
  for s in "$SRC"/*/; do
    [ -f "${s}SKILL.md" ] || continue
    name="$(basename "$s")"
    ln -sfn "$s" "$DEST/$name"
    echo "  ✓ $name"
  done
  echo
done
for s in "$SRC"/*/; do
  if [ -f "${s}package.json" ] && [ ! -d "${s}node_modules" ]; then
    echo "⚠ $(basename "$s") 还需安装 Node 依赖: cd ${s} && npm install"
  fi
done
echo "完成。需授权的 skill 见各自 SKILL.md 跑一次首次授权(如 feishu: python3 setup.py)。"
