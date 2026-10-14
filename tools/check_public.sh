#!/usr/bin/env bash
# Fails if any file that would be published mentions the private booking system, or if the
# committed public snapshot (data/public/) contains availability/capacity fields.
#   tools/check_public.sh         staged files (run by the pre-commit hook)
#   tools/check_public.sh --all   every file git would publish (tracked + untracked, not ignored)
# The pattern is assembled in pieces so this script doesn't match itself.
set -uo pipefail
PATTERN="rock""gympro|r""gp|app\.rock""gympro|portal\.rock""gympro"
cd "$(git rev-parse --show-toplevel)" || exit 1

if [ "${1:-}" = "--all" ]; then
  files=$(git ls-files -co --exclude-standard)
  content() { cat -- "$1"; }
else
  files=$(git diff --cached --name-only --diff-filter=ACMR)
  content() { git show ":$1"; }
fi

hits=0
while IFS= read -r f; do
  [ -z "$f" ] || [ "$f" = ".gitignore" ] && continue
  if printf '%s' "$f" | grep -Eiq "$PATTERN"; then
    echo "PATH  $f"; hits=$((hits + 1))
  fi
  # -I skips binary files. Lockfile "integrity" hashes are random base64 and can contain the
  # letters by chance, so those lines are ignored.
  matches=$(content "$f" | grep -v '"integrity": "sha' | grep -EIin "$PATTERN" | cut -c1-140)
  if [ -n "$matches" ]; then
    echo "$matches" | sed "s|^|FILE  $f:|"; hits=$((hits + 1))
  fi
  # The committed public snapshot must never carry live availability or capacity fields.
  case "$f" in
    data/public/*.json)
      leaks=$(content "$f" | grep -Eon '"(avail|full|bookable|spaces|capacity)"[[:space:]]*:' | head -5)
      if [ -n "$leaks" ]; then
        echo "$leaks" | sed "s|^|FIELD $f:|"; hits=$((hits + 1))
      fi
      ;;
  esac
done <<< "$files"

if [ "$hits" -gt 0 ]; then
  echo "check_public: $hits file(s) mention private code/config. Move it to a gitignored path." >&2
  exit 1
fi
echo "check_public: OK"
