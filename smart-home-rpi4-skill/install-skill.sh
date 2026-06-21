#!/usr/bin/env bash
# Installs the smart-home-rpi4 skill into Cowork.
# Run once from WSL: bash ~/workspace/smart-home-rpi4/smart-home-rpi4-skill/install-skill.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="smart-home-rpi4"

# Find the Cowork skills folder (skills-plugin path varies per session ID but the structure is stable)
SKILLS_BASE="$APPDATA/Claude/local-agent-mode-sessions/skills-plugin"

# Package as .skill (zip)
OUTFILE="/tmp/${SKILL_NAME}.skill"
echo "→ Packaging ${SKILL_NAME}..."
cd "$(dirname "$SKILL_DIR")"
zip -r "$OUTFILE" "$(basename "$SKILL_DIR")/SKILL.md"
echo "✓ Packaged: $OUTFILE"

echo ""
echo "To install in Cowork:"
echo "  1. Open Cowork → Settings → Skills"
echo "  2. Click 'Install skill from file'"
echo "  3. Select: $OUTFILE"
echo ""
echo "Or drag and drop $OUTFILE onto the Cowork skills panel."
