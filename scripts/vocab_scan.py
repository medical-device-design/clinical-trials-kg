#!/usr/bin/env python3
"""Scan converter output (page_*.ttl, *.links.ttl) and record, for every ex: term,
how it is used: classes, and for each predicate the subject classes and object kinds
(IRI target class or literal datatype). The result feeds make_ontology.py.

Reads the line-per-pair layout written by common.write_block. Usage:
    python3 scripts/vocab_scan.py OUT_DIR [OUT_DIR ...] > vocab_scan.json
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict
from multiprocessing import Pool

EX = "ex:"
EXNS = "https://bmedesign.org/clinical-trials-kg/ns/"
DT = re.compile(r'"\^\^(xsd:[A-Za-z]+)\s*[;.]\s*$')
PAIR = re.compile(r"^    (\S+) (.*?)\s*[;.]\s*$")


def scan(path):
    classes, pred = set(), defaultdict(lambda: {"domain": set(), "iri": 0, "lit": set(), "iri_prefix": set()})
    types = {}
    blocks = []
    subj, pairs = None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("<"):
                subj, pairs = line.strip(), []
                blocks.append((subj, pairs))
            elif line.startswith("    ") and subj:
                m = PAIR.match(line.rstrip("\n"))
                if not m:
                    continue
                p, o = m.groups()
                pairs.append((p, o))
                if p == "a" and o.startswith(EX):
                    classes.add(o)
                    types.setdefault(subj, o)
    study = re.compile(r"/id/study/NCT[0-9]{8}>$")

    def typ(node):
        # link files describe studies without repeating their type
        return types.get(node) or ("ex:ClinicalStudy" if study.search(node) else None)

    for subj, pairs in blocks:
        cls = typ(subj)
        for p, o in pairs:
            if not p.startswith(EX):
                continue
            d = pred[p]
            if cls:
                d["domain"].add(cls)
            if o.startswith("<"):
                d["iri"] += 1
                tgt = typ(o)
                d["iri_prefix"].add(tgt if tgt else re.sub(r"[^/]*>$", "", o)[:90])
            else:
                m = DT.search(o + " .")
                d["lit"].add(m.group(1) if m else ("xsd:boolean" if o in ("true", "false") else "xsd:string"))
    return classes, {k: {"domain": v["domain"], "iri": v["iri"], "lit": v["lit"], "iri_prefix": v["iri_prefix"]}
                     for k, v in pred.items()}


def main(dirs):
    files = sorted(f for d in dirs for f in glob.glob(os.path.join(d, "**", "*.ttl"), recursive=True))
    classes, pred = set(), {}
    with Pool(2) as pool:          # VM rule: at most 2 transform jobs
        for c, p in pool.imap_unordered(scan, files, chunksize=4):
            classes |= c
            for k, v in p.items():
                d = pred.setdefault(k, {"domain": set(), "iri": 0, "lit": set(), "iri_prefix": set()})
                d["domain"] |= v["domain"]
                d["iri"] += v["iri"]
                d["lit"] |= v["lit"]
                d["iri_prefix"] |= v["iri_prefix"]
    out = {"files": len(files), "classes": sorted(classes),
           "predicates": {k: {"domain": sorted(v["domain"]), "iri": v["iri"], "lit": sorted(v["lit"]),
                              "iri_targets": sorted(v["iri_prefix"])[:20]} for k, v in sorted(pred.items())}}
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
