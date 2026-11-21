#!/usr/bin/env bash
# Validate every Turtle file in OUT_DIR: riot syntax, Jena SHACL per page
# (core + its link file together), then the cross-file check (orphans, e-mails).
# Usage: scripts/validate.sh OUT_DIR
set -euo pipefail
OUT=${1:?usage: validate.sh OUT_DIR}
HERE=$(cd "$(dirname "$0")/.." && pwd)
SHAPES="$HERE/ontology/shapes/ct.shacl.ttl"
fail=0
for f in "$OUT"/page_*[0-9].ttl; do
  base=${f%.ttl}
  riot --validate "$f" "$base.links.ttl" >/dev/null || { echo "SYNTAX FAIL $f"; fail=1; continue; }
  tmp=$(mktemp --suffix=.ttl)
  riot --output=turtle "$f" "$base.links.ttl" > "$tmp"
  if shacl validate --shapes "$SHAPES" --data "$tmp" | grep -q "sh:conforms  *true"; then
    echo "ok $(basename "$f")"
  else
    echo "SHACL FAIL $(basename "$f")"; shacl validate --shapes "$SHAPES" --data "$tmp" | head -40; fail=1
  fi
  rm -f "$tmp"
done
python3 "$HERE/scripts/check_graph.py" "$OUT" --json "$OUT/check_stats.json" || fail=1
[ $fail -eq 0 ] && echo "validate.sh: ALL PASSED" || { echo "validate.sh: FAILURES"; exit 1; }
