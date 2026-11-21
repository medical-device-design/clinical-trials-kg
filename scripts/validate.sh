#!/usr/bin/env bash
# Validate every Turtle file in OUT_DIR: riot syntax, Jena SHACL per page
# (core + its link file together), then the cross-file check (orphans, e-mails).
# Pages run in parallel (JOBS, default 4): serial SHACL took about 7 to 15 s per
# page in the November 20, 2026 pilot, too slow for the 600-page full load.
# Usage: JOBS=6 scripts/validate.sh OUT_DIR
set -euo pipefail
OUT=${1:?usage: validate.sh OUT_DIR}
HERE=$(cd "$(dirname "$0")/.." && pwd)
export SHAPES="$HERE/ontology/shapes/ct.shacl.ttl"
export JVM_ARGS=${JVM_ARGS:--Xmx2g}

check_page() {
  f=$1; base=${f%.ttl}; name=$(basename "$f")
  if ! riot -q --validate "$f" "$base.links.ttl" >/dev/null 2>&1; then
    echo "SYNTAX FAIL $name"; return 1
  fi
  tmp=$(mktemp --suffix=.ttl)
  riot -q --output=turtle "$f" "$base.links.ttl" > "$tmp"
  report=$(shacl validate --shapes "$SHAPES" --data "$tmp" 2>&1)
  rm -f "$tmp"
  if grep -q "sh:conforms  *true" <<<"$report"; then
    echo "ok $name"
  else
    echo "SHACL FAIL $name"; head -40 <<<"$report"; return 1
  fi
}
export -f check_page

fail=0
ls "$OUT"/page_*[0-9].ttl | xargs -P "${JOBS:-4}" -I{} bash -c 'check_page "$@"' _ {} \
  > "$OUT/validate_pages.log" || fail=1
grep -c '^ok' "$OUT/validate_pages.log" | sed 's/^/pages ok: /'
grep -E 'FAIL' "$OUT/validate_pages.log" || true
python3 "$HERE/scripts/check_graph.py" "$OUT" --json "$OUT/check_stats.json" | tail -1 || fail=1
[ $fail -eq 0 ] && echo "validate.sh: ALL PASSED" || { echo "validate.sh: FAILURES"; exit 1; }
