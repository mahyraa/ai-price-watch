#!/bin/bash
# Double-click this file to set up and run AI Price Watch.
cd "$(dirname "$0")" || exit 1

echo ""
echo "======================================"
echo "   AI Price Watch"
echo "======================================"
echo ""

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$candidate"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "Could not find Python 3.10 or newer."
  echo "Install it from https://www.python.org/downloads/ then run this again."
  echo ""
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

echo "Using $($PY --version)"
echo ""

# --- API key ---------------------------------------------------------------
if [ ! -f .env ]; then
  echo "You need an Anthropic API key (this is what reads the pricing pages)."
  echo ""
  echo "  1. Go to  console.anthropic.com"
  echo "  2. API Keys  ->  Create Key"
  echo "  3. Add about \$5 of credit under Billing"
  echo ""
  echo "Then come back here and paste it with  Cmd+V  and press Enter."
  echo "(You WILL see the key appear as you paste - that is normal. Paste once.)"
  echo ""

  while true; do
    printf "Key: "
    read -r KEY
    # strip spaces/newlines, and keep only the first key if it got pasted twice
    KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
    KEY="sk-ant-$(printf '%s' "$KEY" | awk -F'sk-ant-' '{print $2}')"

    if [ "$KEY" = "sk-ant-" ]; then
      echo "That did not look like a key (it should start with sk-ant-). Try again."
      echo ""
      continue
    fi
    if [ ${#KEY} -lt 40 ]; then
      echo "That looks too short to be a full key. Try pasting again."
      echo ""
      continue
    fi
    break
  done

  printf 'ANTHROPIC_API_KEY=%s\n' "$KEY" > .env
  chmod 600 .env
  echo ""
  echo "Key saved (${#KEY} characters). This file never goes to GitHub."
  echo ""
fi

# --- dependencies ----------------------------------------------------------
# A dedicated virtual environment. Anaconda's base environment ships its own
# versions of some of these libraries, and mixing them breaks the HTTP client.
if [ ! -d .venv ]; then
  echo "Creating an isolated environment for this project (first time only)..."
  "$PY" -m venv .venv || { echo "Could not create the environment."; read -n 1 -s -r -p "Press any key..."; exit 1; }
fi

VENV_PY=".venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "The environment looks broken. Delete the .venv folder and run this again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

echo "Installing what it needs (first time only, ~1 minute)..."
"$VENV_PY" -m pip install -q --upgrade pip 2>&1 | tail -2
"$VENV_PY" -m pip install -q -r requirements.txt 2>&1 | grep -vi "already satisfied" | tail -5
echo "Done."
echo ""

# --- tests -----------------------------------------------------------------
echo "Running tests..."
"$VENV_PY" -m pytest tests/ -q 2>&1 | tail -3
echo ""

# --- the actual run --------------------------------------------------------
echo "Checking pricing pages. This takes a couple of minutes..."
echo ""
set -a; . ./.env; set +a
"$VENV_PY" -m src.run
STATUS=$?

echo ""
if [ $STATUS -eq 0 ] && [ -f site/index.html ]; then
  echo "Opening your site..."
  open site/index.html
else
  echo "Something went wrong above. Copy the error and send it to Claude."
fi

echo ""
read -n 1 -s -r -p "Press any key to close this window..."
echo ""
