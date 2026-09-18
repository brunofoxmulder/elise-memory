#!/usr/bin/with-contenv bashio
set -e
cd /app
exec uvicorn elise_memory.app:app --host 0.0.0.0 --port 8100
