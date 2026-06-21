#!/usr/bin/env bash
# setup-github-ssh.sh — sets up SSH key auth for GitHub in WSL
set -e

EMAIL="jackgukf@gmail.com"
KEY="$HOME/.ssh/id_ed25519"

echo "=== GitHub SSH Setup ==="

# 1. Generate key if missing
if [ -f "$KEY" ]; then
  echo "✓ SSH key already exists: $KEY"
else
  echo "→ Generating SSH key..."
  ssh-keygen -t ed25519 -C "$EMAIL" -f "$KEY" -N ""
  echo "✓ Key generated."
fi

# 2. Start ssh-agent and add key
eval "$(ssh-agent -s)" > /dev/null
ssh-add "$KEY" 2>/dev/null
echo "✓ Key loaded into ssh-agent."

# 3. Print public key for GitHub
echo ""
echo "=============================="
echo "Add this public key to GitHub:"
echo "  https://github.com/settings/ssh/new"
echo "=============================="
cat "$KEY.pub"
echo "=============================="
echo ""
read -p "Press Enter once you've added the key to GitHub..."

# 4. Test connection
echo "→ Testing connection to GitHub..."
if ssh -T git@github.com -o StrictHostKeyChecking=accept-new 2>&1 | grep -q "successfully authenticated"; then
  echo "✓ GitHub SSH authentication successful!"
else
  ssh -T git@github.com -o StrictHostKeyChecking=accept-new 2>&1 || true
fi

# 5. Verify remote
echo ""
REMOTE=$(git -C "$(dirname "$0")/.." remote get-url origin 2>/dev/null || echo "not in a git repo")
echo "→ Remote URL: $REMOTE"

echo ""
echo "Done! You can now use git push/pull without a password."
