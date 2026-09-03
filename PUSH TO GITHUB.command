#!/bin/bash
cd "$(dirname "$0")" || exit 1

USER="mahyraa"
REPO="ai-price-watch"

echo ""
echo "=========================================="
echo "   Push AI Price Watch to GitHub"
echo "=========================================="
echo ""

# --- safety: never publish the API key ------------------------------------
if [ ! -f .gitignore ] || ! grep -q "^\.env$" .gitignore; then
  echo "STOPPING: .gitignore is missing or doesn't exclude .env."
  echo "Your API key could be published. Nothing was pushed."
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi

git config --global --get user.name  >/dev/null 2>&1 || git config --global user.name  "Mahyra Afif"
git config --global --get user.email >/dev/null 2>&1 || git config --global user.email "mra012@bucknell.edu"
git config --global credential.helper osxkeychain

if [ ! -d .git ]; then
  git init -q
  git branch -M main
fi

git add -A

# Hard stop if the key or the virtualenv somehow got staged.
if git diff --staged --name-only | grep -qE "^\.env$|^\.venv/"; then
  echo "STOPPING: .env or .venv is staged. Nothing was pushed."
  git reset -q
  read -n 1 -s -r -p "Press any key to close..."; exit 1
fi

echo "Files that will be published:"
git diff --staged --name-only | sed 's/^/   /'
echo ""
echo "Confirmed NOT published: .env (your API key), .venv"
echo ""

git commit -q -m "AI pricing watcher: fetch, extract, diff, publish" 2>/dev/null \
  || git commit -q -m "Update" 2>/dev/null \
  || echo "(nothing new to commit)"

git remote remove origin 2>/dev/null
git remote add origin "https://github.com/$USER/$REPO.git"

echo "------------------------------------------------------------"
echo "GitHub will now ask you to sign in."
echo ""
echo "  Username: $USER"
echo "  Password: paste your PERSONAL ACCESS TOKEN (not your password)"
echo ""
echo "The token will look like  ghp_xxxxxxxx  and will not appear"
echo "as you paste it. Paste ONCE with Cmd+V, then press Enter."
echo "------------------------------------------------------------"
echo ""

git push -u origin main
STATUS=$?

echo ""
if [ $STATUS -eq 0 ]; then
  echo "=========================================="
  echo "  Pushed."
  echo "  Repo: https://github.com/$USER/$REPO"
  echo "=========================================="
  open "https://github.com/$USER/$REPO"
else
  echo "Push failed. Common causes:"
  echo "  - the repository doesn't exist yet on github.com"
  echo "  - the token was wrong, expired, or lacks the 'repo' scope"
  echo "Copy the error above and send it to Claude."
fi

echo ""
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
