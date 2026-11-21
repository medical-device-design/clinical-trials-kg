#!/usr/bin/env bash
# Weekly delta (cron on .83, like the recall monitor): studies whose last update
# post date is on or after the previous run. Output goes to out/delta/<date>;
# the next full rebuild supersedes it. Nothing is uploaded to lakeFS from here.
set -euo pipefail
: "${CTKG:=/srv/clinical-trials-kg}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
STAMP="$CTKG/logs/last_delta_date"
SINCE=$(cat "$STAMP" 2>/dev/null || date -d '7 days ago' +%F)
TODAY=$(date +%F)
DL="$CTKG/downloads/delta-$TODAY"; OUT="$CTKG/out/delta/$TODAY"
python3 "$HERE/scripts/fetch_ct.py" --updated-since "$SINCE" --out "$DL"
python3 "$HERE/pipeline/ct_to_rdf.py" "$DL" "$OUT"
bash "$HERE/scripts/validate.sh" "$OUT"
echo "$TODAY" > "$STAMP"
