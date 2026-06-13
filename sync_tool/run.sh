#!/usr/bin/env bash
# FlashCards CSV Sync - macOS/Linux launcher
cd "$(dirname "$0")"
PY=python3
$PY -m pip install -q -r requirements.txt
$PY sync_app.py
