#!/usr/bin/env bash
# Pilot: device-intervention studies (about 76,000), measured end to end.
# Then the full load (all studies, Roche 2026-11-20) with SCOPE=all.
# Usage: SCOPE=device scripts/run_pilot.sh      (default)
#        SCOPE=all    scripts/run_pilot.sh
#        SKIP_FETCH=1 SCOPE=device scripts/run_pilot.sh   (reuse downloads)
set -euo pipefail
: "${CTKG:=/srv/clinical-trials-kg}"
SCOPE=${SCOPE:-device}
TAG=${TAG:-pilot-$SCOPE}
HERE=$(cd "$(dirname "$0")/.." && pwd)
DL="$CTKG/downloads/$TAG"; OUT="$CTKG/out/$TAG"; LOG="$CTKG/logs/$TAG-$(date +%Y%m%d-%H%M).log"
mkdir -p "$DL" "$OUT" "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1
echo "== tests"; python3 "$HERE/tests/test_pipeline.py" | tail -1
if [ -z "${SKIP_FETCH:-}" ]; then
  echo "== fetch ($SCOPE)"; /usr/bin/time -v python3 "$HERE/scripts/fetch_ct.py" --scope "$SCOPE" --out "$DL" 2> "$OUT/time_fetch.txt"
fi
echo "== convert"; /usr/bin/time -v python3 "$HERE/pipeline/ct_to_rdf.py" "$DL" "$OUT" 2> "$OUT/time_convert.txt"
grep -E "Maximum resident|Elapsed" "$OUT/time_convert.txt" || true
echo "== validate"; bash "$HERE/scripts/validate.sh" "$OUT"
if [ -n "${CLASSIFICATION_JSON:-}" ]; then
  echo "== device to product-code candidates"
  python3 "$HERE/pipeline/linkage/device_match.py" "$CLASSIFICATION_JSON" "$DL" "$OUT/devicematch"
fi
echo "== size"; du -sh "$DL" "$OUT"
echo "Done. Record convert_stats.json, check_stats.json, time_*.txt in docs/PILOT_RESULTS.md"
