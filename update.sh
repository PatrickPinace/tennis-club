#!/usr/bin/env bash
set -euo pipefail

# Update local working directory from remote repository.
# Normal mode: safe pull with rebase and autostash.
# Hard mode: reset to remote/branch (discard local changes).
# Clean mode: only works with --hard; removes untracked files and directories.
#
# Usage:
#   ./update.sh               # safe mode
#   ./update.sh --hard        # forcefully match remote, keeps untracked files
#   ./update.sh --hard --clean  # forcefully match remote and remove untracked files
#
# Env vars:
#   REMOTE (default: origin)
#   BRANCH (default: current branch)
#   SUBMODULES (if set to 1, also update submodules)
# Aby pzrekonwertować plik po edycji w Windows należy skorzystać z poniższego polecenia:
# dos2unix update.sh


MODE="safe"
CLEAN_MODE="false"

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --hard)
      MODE="hard"
      ;;
    --clean)
      CLEAN_MODE="true"
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

REMOTE=tennis-club

# Move to script directory (repo root assumed)
cd "$(dirname "$0")"

if ! command -v git >/dev/null 2>&1; then
  echo "Git is not installed or not on PATH." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This is not a Git repository." >&2
  exit 1
fi

BRANCH=${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}

if ! git remote | grep -q "^${REMOTE}$"; then
  echo "Remote '${REMOTE}' not found. Configure it: git remote add ${REMOTE} <url>" >&2
  exit 1
fi

echo "Fetching from ${REMOTE}..."
git fetch "$REMOTE" --prune

# Ensure upstream exists; if not, try to set it to REMOTE/BRANCH (non-fatal)
if ! git rev-parse --abbrev-ref --symbolic-full-name "${BRANCH}@{upstream}" >/dev/null 2>&1; then
  if git ls-remote --exit-code --heads "${REMOTE}" "${BRANCH}" >/dev/null 2>&1; then
    git branch --set-upstream-to "${REMOTE}/${BRANCH}" "${BRANCH}" || true
  fi
fi

if [[ "$MODE" == "hard" ]]; then
  echo "HARD mode: resetting to ${REMOTE}/${BRANCH}..."
  git reset --hard "${REMOTE}/${BRANCH}"
  
  if [[ "$CLEAN_MODE" == "true" ]]; then
    echo "Performing git clean..."
    git clean -fdx
  fi
else
  echo "SAFE mode: pulling with --rebase --autostash from ${REMOTE}/${BRANCH}..."
  if ! git pull --rebase --autostash "$REMOTE" "$BRANCH"; then
    echo "Rebase encountered issues; trying to continue or abort." >&2
    git rebase --continue 2>/dev/null || git rebase --abort || true
  fi
fi

# if [[ "${SUBMODULES:-0}" == "1" ]]; then
#   echo "Updating submodules..."
#   git submodule update --init --recursive
#   if [[ "$MODE" == "hard" ]]; then
#     git submodule foreach --recursive 'git reset --hard HEAD && git clean -fdx || true'
#   fi
# fi

# Przeładowanie Apache2
echo "Reloading Apache2 service..."
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl reload apache2
else
  echo "Systemd not found. Skipping Apache2 reload." >&2
fi

echo "Update complete."