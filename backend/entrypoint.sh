#!/bin/sh
set -eu
cd /app/backend
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 9000 --proxy-headers --forwarded-allow-ips="${FILAFLOW_FORWARDED_ALLOW_IPS:-127.0.0.1}"
