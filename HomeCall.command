#!/bin/bash
# Double-click to start HomeCall on this Mac.  (Owner: lead)
# The first time it sets everything up by itself (Python packages, cloudflared), then
# asks macOS for every permission HomeCall needs, so nothing pops up during a call.
# Keep this window open while you use HomeCall; close it to stop.
cd "$(dirname "$0")" || exit 1
printf '\033]0;HomeCall\007'

pick_python() {
  for p in python3.13 python3.12 python3.11 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
      echo "$p"; return
    fi
  done
}

if [ ! -x .venv/bin/python ]; then
  PY=$(pick_python)
  if [ -z "$PY" ]; then
    echo "HomeCall needs Python 3.11 or newer: https://www.python.org/downloads/ . Then double-click HomeCall again."
    read -r -p "Press Enter to close." _; exit 1
  fi
  echo "First time here: setting up HomeCall (a minute or two)..."
  "$PY" -m venv .venv || { read -r -p "Setup failed. Press Enter to close." _; exit 1; }
fi

# Python packages: installed again only when requirements.txt changed.
if ! cmp -s requirements.txt .venv/.homecall-requirements; then
  echo "Installing HomeCall's Python packages..."
  .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt \
    && cp requirements.txt .venv/.homecall-requirements
fi

# cloudflared: the tunnel that lets your phone reach this Mac from anywhere.
if ! command -v cloudflared >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/cloudflared ] && [ ! -x /usr/local/bin/cloudflared ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing cloudflared..."; brew install cloudflared
  else
    echo "Tip: install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) so your phone can reach this Mac from anywhere."
  fi
fi

.venv/bin/python start.py "$@"
read -r -p "HomeCall stopped. Press Enter to close this window." _
