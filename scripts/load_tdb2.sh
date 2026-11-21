#!/usr/bin/env bash
# Load a build into TDB2 on VM .83 and serve it read-only on localhost with Fuseki.
# Waits while another Jena bulk load (tdbloader/xloader) is running, so two loads
# never compete for the shared RAM and disk. Usage:
#   setsid nohup bash scripts/load_tdb2.sh full-2026-11-21 > $CTKG/logs/tdb2-full.log 2>&1 &
set -euo pipefail
TAG=${1:?usage: load_tdb2.sh TAG}
: "${CTKG:=/srv/clinical-trials-kg}"
JENA=${JENA:-/srv/medical-device-kg/tools/apache-jena-5.2.0}
FUSEKI=${FUSEKI:-/srv/medical-device-kg/tools/apache-jena-fuseki-5.2.0}
PORT=${PORT:-3032}
LOC="$CTKG/tdb2/$TAG"
OUT="$CTKG/out/$TAG"

while pgrep -u "$(id -u)" -f 'tdb2\.(xloader|tdbloader)|tdb2.xloader' >/dev/null; do
  echo "$(date '+%F %T') another Jena bulk load is running; waiting"; sleep 120
done
avail=$(df --output=avail -BG / | tail -1 | tr -dc 0-9)
[ "$avail" -ge 120 ] || { echo "only ${avail} GB free; need 120 GB headroom"; exit 2; }

echo "$(date '+%F %T') loading $OUT into $LOC"
rm -rf "$LOC.loading"
"$JENA/bin/tdb2.xloader" --loc "$LOC.loading" --tmpdir "$CTKG/tmp-xloader" \
  $(ls "$OUT"/page_*.ttl)
rm -rf "$CTKG/tmp-xloader"
mv "$LOC.loading" "$LOC"
du -sh "$LOC"

echo "$(date '+%F %T') switching Fuseki on port $PORT to $TAG"
pkill -u "$(id -u)" -f "fuseki-server.*--port=$PORT" || true
sleep 5
cd "$CTKG"
JVM_ARGS=-Xmx3g setsid nohup "$FUSEKI/fuseki-server" --localhost --port="$PORT" \
  --loc="$LOC" /clinical-trials > "$CTKG/logs/fuseki-ct.log" 2>&1 < /dev/null &
sleep 15
tail -n 1 "$CTKG/logs/fuseki-ct.log"
echo "$(date '+%F %T') done"
