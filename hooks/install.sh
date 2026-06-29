#!/bin/sh
# Install Repo Guardian's pre-commit hook into this repo's .git/hooks.
# Usage:  sh hooks/install.sh
set -e

ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$ROOT/.git/hooks"

mkdir -p "$HOOK_DIR"
cp "$ROOT/hooks/pre-commit" "$HOOK_DIR/pre-commit"
chmod +x "$HOOK_DIR/pre-commit"

echo "Installed Repo Guardian pre-commit hook -> $HOOK_DIR/pre-commit"
echo "Test it:  echo 'AWS_SECRET = \"AKIAIOSFODNN7EXAMPLE\"' >> app/config.py && git add -A && git commit -m test"
