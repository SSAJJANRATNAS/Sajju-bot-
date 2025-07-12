#!/usr/bin/env bash
set -e

# Optional: Load .env if present (for local development)
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

exec python bot.py