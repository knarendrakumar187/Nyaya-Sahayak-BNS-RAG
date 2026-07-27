#!/bin/sh
set -e
PORT="${PORT:-10000}"
echo "Nyaya-Sahayak API starting on 0.0.0.0:${PORT}"
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 --timeout-keep-alive 75
