#!/usr/bin/env bash
# Point .git/hooks/post-commit at the tracked hook in scripts/git-hooks/.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
chmod +x "${REPO_ROOT}/scripts/git-hooks/post-commit"
ln -sfn ../../scripts/git-hooks/post-commit "${REPO_ROOT}/.git/hooks/post-commit"
echo "post-commit -> scripts/git-hooks/post-commit"
