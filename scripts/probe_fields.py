#!/usr/bin/env python3
"""
probe_fields.py -- which JSON paths occur in downloaded ClinicalTrials.gov records,
how often, and which the converter does not read. Used to audit field coverage
after a fetch (the "no fields dropped" rule).

Usage: probe_fields.py DOWNLOAD_DIR [--out paths.tsv]
Lists are collapsed to [] so the output is one row per path.
"""

import gzip
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERTER = os.path.join(os.path.dirname(HERE), "pipeline", "ct_to_rdf.py")


def walk(node, path, seen):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, f"{path}.{k}" if path else k, seen)
    elif isinstance(node, list):
        for v in node:
            walk(v, path + "[]", seen)
    else:
        seen.add(path)


def main(argv):
    d = argv[0]
    out = argv[2] if len(argv) > 2 and argv[1] == "--out" else None
    counts, n = Counter(), 0
    for p in sorted(os.listdir(d)):
        if not p.startswith("page_"):
            continue
        with gzip.open(os.path.join(d, p), "rt", encoding="utf-8") as f:
            for rec in json.load(f)["studies"]:
                n += 1
                seen = set()
                walk(rec, "", seen)
                counts.update(seen)
    src = open(CONVERTER, encoding="utf-8").read()
    keys_used = set(re.findall(r'"([A-Za-z][A-Za-z0-9]+)"', src))
    rows = []
    for path, c in counts.most_common():
        leaf = re.sub(r"\[\]", "", path.split(".")[-1])
        rows.append((path, c, round(100 * c / n, 2), "mapped" if leaf in keys_used else "NOT-READ"))
    if out:
        with open(out, "w") as f:
            f.write("path\tstudies\tpercent\tstatus\n")
            for r in rows:
                f.write("\t".join(map(str, r)) + "\n")
    print(f"studies: {n}, distinct leaf paths: {len(rows)}, "
          f"not read: {sum(1 for r in rows if r[3] == 'NOT-READ')}")
    for r in rows:
        if r[3] == "NOT-READ":
            print(f"{r[2]:>7}%  {r[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
