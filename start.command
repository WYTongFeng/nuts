#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo 'Please create .venv first. See LOCAL_SETUP.md.'
  exit 1
fi
exec .venv/bin/python server.py
