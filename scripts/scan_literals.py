#!/usr/bin/env python3
"""
scan_literals.py -- find two literal defects in any Turtle output tree:

  1. xsd:decimal written in exponent form ("2.5e+06"^^xsd:decimal). Not a valid
     xsd:decimal lexical form, so strict SPARQL engines reject or mis-compare it.
  2. Partial dates left untyped on date-like predicates ("2019-05" or "2019"
     without ^^xsd:gYearMonth / ^^xsd:gYear), so they drop out of date filters.

Read-only. Usage: scan_literals.py ROOT [ROOT ...] > report.json
Scans *.ttl recursively, line by line (fine for multi-GB files).
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict

EXP = re.compile(r'(\S+)\s+"(-?[0-9.]+[eE][-+]?[0-9]+)"\^\^xsd:decimal')
PARTIAL = re.compile(r'^\s*(\S*[Dd]ate\S*)\s+"(\d{4}(?:-\d{2})?)"\s*[;.,]?\s*$')


def main(roots):
    report = {"roots": roots, "files": {}, "exponent_by_predicate": Counter(),
              "partial_date_by_predicate": Counter(), "examples": defaultdict(list)}
    for root in roots:
        for dirpath, _, names in os.walk(root):
            for n in sorted(names):
                if not n.endswith(".ttl"):
                    continue
                path = os.path.join(dirpath, n)
                exp = part = 0
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if "e" in line and "xsd:decimal" in line:
                                m = EXP.search(line)
                                if m:
                                    exp += 1
                                    report["exponent_by_predicate"][m.group(1)] += 1
                                    if len(report["examples"]["exponent"]) < 10:
                                        report["examples"]["exponent"].append([path, m.group(1), m.group(2)])
                            if "ate" in line and "^^" not in line:
                                m = PARTIAL.match(line)
                                if m:
                                    part += 1
                                    report["partial_date_by_predicate"][m.group(1)] += 1
                                    if len(report["examples"]["partial_date"]) < 10:
                                        report["examples"]["partial_date"].append([path, m.group(1), m.group(2)])
                except OSError as e:
                    report["files"][path] = {"error": str(e)}
                    continue
                if exp or part:
                    report["files"][path] = {"exponent_decimals": exp, "untyped_partial_dates": part}
                print(f"[scan] {path}: exp={exp} partial={part}", file=sys.stderr, flush=True)
    report["total_exponent_decimals"] = sum(report["exponent_by_predicate"].values())
    report["total_untyped_partial_dates"] = sum(report["partial_date_by_predicate"].values())
    json.dump(report, sys.stdout, indent=2, default=dict)


if __name__ == "__main__":
    main(sys.argv[1:])
