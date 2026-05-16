#!/usr/bin/env bash
# Run this once after cloning to install git hooks
cp .githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "✅ Git hooks installed! Your commits will now be scanned for secrets."
