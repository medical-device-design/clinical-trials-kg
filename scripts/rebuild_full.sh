#!/usr/bin/env bash
# Rebuild the full graph from an existing download snapshot (no fetch), validate it,
# check it, then load it into TDB2 and switch Fuseki (scripts/load_tdb2.sh).
# Announce first (bmedesign-kg 2a) and run only after the master approved the conventions it applies.
# Nothing is deleted. Superseded stores are listed for the master control to handle.
#
# Usage: SNAP=full-2026-11-21 TAG=full-2026-11-22 scripts/rebuild_full.sh
set -euo pipefail
: "${CTKG:=/srv/clinical-trials-kg}"
SNAP=${SNAP:?download snapshot under downloads/}
TAG=${TAG:?output tag under out/ and tdb2/}
JOBS=${JOBS:-4}                   # 4 SHACL JVMs x 2 GB = 8 GB, the VM JVM limit
HERE=$(cd "$(dirname "$0")/.." && pwd)
DL="$CTKG/downloads/$SNAP"; OUT="$CTKG/out/$TAG"; LOG="$CTKG/logs/rebuild-$TAG.log"
[ -e "$OUT" ] && { echo "refusing: $OUT exists"; exit 1; }
mkdir -p "$OUT"
exec > >(tee -a "$LOG") 2>&1
free_gb=$(df -BG --output=avail "$CTKG" | tail -1 | tr -dc 0-9)
echo "$(date '+%F %T') start rebuild $TAG from $SNAP, ${free_gb} GB free"
[ "$free_gb" -ge 170 ] || { echo "need 170 GB free (output + TDB2 + 100 GB reserve)"; exit 1; }
echo "== tests"; python3 "$HERE/tests/test_pipeline.py" | tail -1
echo "== convert"; /usr/bin/time -v python3 "$HERE/pipeline/ct_to_rdf.py" "$DL" "$OUT" 2> "$OUT/time_convert.txt"
grep -E "Maximum resident|Elapsed" "$OUT/time_convert.txt" || true
echo "== validate"; JOBS=$JOBS bash "$HERE/scripts/validate.sh" "$OUT"
echo "== check"; python3 "$HERE/scripts/check_graph.py" "$OUT" --json "$OUT/check_stats.json" | tail -5
echo "== literal scan (exponent decimals, untyped partial dates)"; python3 "$HERE/scripts/scan_literals.py" "$OUT" > "$OUT/literal_scan.json" 2>/dev/null; grep -E "total_" "$OUT/literal_scan.json"
du -sh "$OUT"
echo "$(date '+%F %T') converted and validated; loading"
bash "$HERE/scripts/load_tdb2.sh" "$TAG"
echo "$(date '+%F %T') rebuild $TAG done"
