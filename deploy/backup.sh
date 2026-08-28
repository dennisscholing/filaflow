#!/bin/sh
set -eu

daily_keep="${BACKUP_DAILY_KEEP:-7}"
weekly_keep="${BACKUP_WEEKLY_KEEP:-4}"
backup_hour="${BACKUP_HOUR:-2}"
case "$daily_keep:$weekly_keep:$backup_hour" in *[!0-9:]*|::*|:*) echo "Invalid backup retention setting" >&2; exit 1;; esac
mkdir -p /backups/daily /backups/weekly

trim_backups() {
  folder="$1"; keep="$2"
  find "$folder" -maxdepth 1 -type f -name 'filaflow-*.dump' -print \
    | sort -r | awk -v keep="$keep" 'NR > keep { print }' \
    | while IFS= read -r old; do [ -n "$old" ] && rm -f "$old"; done
}

while true; do
  current_hour="$(date +%H)"
  if [ "$current_hour" = "$(printf '%02d' "$backup_hour")" ]; then
    stamp="$(date +%Y%m%d-%H%M%S)"
    daily="/backups/daily/filaflow-${stamp}.dump"
    pg_dump --format=custom --compress=9 --file="$daily"
    if [ "$(date +%u)" = "7" ]; then cp "$daily" "/backups/weekly/filaflow-${stamp}.dump"; fi
    trim_backups /backups/daily "$daily_keep"
    trim_backups /backups/weekly "$weekly_keep"
    sleep 3700
  else
    sleep 900
  fi
done
