#!/usr/bin/env python3
"""
device_match.py -- candidate links from device interventions to FDA product codes.

The scorer (weighted word overlap, with "strong" device words counted double and
generic words a quarter) is Adelyn Mathew's, from fda_device_match.py on the
clinicaltrials-harvester branch (August 2026). What changed:

  * runs OFFLINE against the openFDA device classification download, not one live
    API call per intervention (reproducible, no API key, no rate limit)
  * output is a typed candidate link with method, score and confidence, written
    to its own file, never a property asserted on the device itself
  * only the best match at or above the threshold is written, plus how many
    product codes tied with it, so ambiguity is visible

This is a WEAK signal. Precision must be measured on a hand-reviewed sample of
200 before any count from it goes into a paper or proposal.

Usage:
  device_match.py CLASSIFICATION_JSON DOWNLOAD_DIR OUT_DIR [--threshold 0.75]
  (CLASSIFICATION_JSON = openFDA device-classification-0001-of-0001.json)
"""

import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import iri                                                  # noqa: E402
from common import lit, float_lit, write_block, prefixes   # noqa: E402

METHOD = "name-token-overlap-v1 (Mathew 2026)"

STRONG = {"cardiac", "cardioverter", "defibrillator", "pacemaker", "neurostimulator",
          "resynchronization", "crt", "icd", "graft", "catheter", "stent", "cochlear",
          "valve", "electrode", "implant", "dressing", "wound", "laser", "ultrasound",
          "pump", "lens", "prosthesis", "sensor", "monitor"}
GENERIC = {"device", "system", "medical", "stimulator", "generator", "implantable",
           "implanted", "electrical", "therapeutic"}
STOP = {"device", "system", "medical", "the", "and", "with", "inc", "incorporated",
        "company", "corporation", "corp", "llc", "ltd", "of", "for", "a", "an"}
NOT_A_DEVICE = {"sham", "placebo", "control", "standard", "usual", "care", "no", "none"}


def words(name):
    return [w for w in re.findall(r"\b[a-z0-9]+\b", str(name).lower()) if w not in STOP]


def _weight(w):
    return 2.0 if w in STRONG else 0.25 if w in GENERIC else 1.0


def similarity(a, b):
    """Mean of the weighted coverage of each name by the shared words (0 to 1)."""
    wa, wb = set(words(a)), set(words(b))
    if not wa or not wb:
        return 0.0
    shared = wa & wb
    if not shared:
        return 0.0
    cov = lambda ws: sum(_weight(w) for w in ws & shared) / sum(_weight(w) for w in ws)
    return (cov(wa) + cov(wb)) / 2


def confidence(score):
    return "medium" if score >= 0.9 else "low"


class Index:
    """Inverted index of classification names by word, so each intervention is
    compared only with product codes sharing at least one word."""

    def __init__(self, records):
        self.recs = [r for r in records if r.get("product_code") and r.get("device_name")]
        self.by_word = {}
        for i, r in enumerate(self.recs):
            for w in set(words(r["device_name"])):
                self.by_word.setdefault(w, []).append(i)

    def best(self, name, threshold):
        ws = set(words(name))
        if not ws or ws <= NOT_A_DEVICE:
            return None, 0
        cand = {i for w in ws for i in self.by_word.get(w, [])}
        scored = sorted(((similarity(name, self.recs[i]["device_name"]), self.recs[i]["product_code"])
                         for i in cand), key=lambda t: (-t[0], t[1]))
        if not scored or scored[0][0] < threshold:
            return None, 0
        top = scored[0][0]
        ties = sum(1 for s, _ in scored if abs(s - top) < 1e-9)
        return (top, scored[0][1]), ties


def run(classification_json, download_dir, out_dir, threshold=0.75):
    with open(classification_json, encoding="utf-8") as f:
        data = json.load(f)
    idx = Index(data.get("results", data) if isinstance(data, dict) else data)
    os.makedirs(out_dir, exist_ok=True)
    n_iv = n_hit = 0
    pages = sorted(p for p in os.listdir(download_dir) if p.startswith("page_"))
    for p in pages:
        opener = gzip.open if p.endswith(".gz") else open
        with opener(os.path.join(download_dir, p), "rt", encoding="utf-8") as f:
            studies = json.load(f).get("studies", [])
        out_p = os.path.join(out_dir, p.split(".")[0] + ".devicematch.ttl")
        with open(out_p, "w", encoding="utf-8") as out:
            out.write(prefixes({"ex": iri.NS}) + "\n")
            for rec in studies:
                nct = (((rec.get("protocolSection") or {}).get("identificationModule") or {}).get("nctId") or "")
                try:
                    iri.study(nct)
                except ValueError:
                    continue
                ivs = ((rec.get("protocolSection") or {}).get("armsInterventionsModule") or {}).get("interventions") or []
                for i, iv in enumerate(ivs):
                    if iv.get("type") != "DEVICE":
                        continue
                    n_iv += 1
                    names = [iv.get("name")] + list(iv.get("otherNames") or [])
                    best, ties, used = None, 0, None
                    for nm in names:
                        b, t = idx.best(nm or "", threshold)
                        if b and (best is None or b[0] > best[0]):
                            best, ties, used = b, t, nm
                    if not best:
                        continue
                    n_hit += 1
                    write_block(out, iri.device_match(nct, i, 0), [
                        ("a", "ex:ProductCodeCandidate"),
                        ("ex:intervention", iri.intervention(nct, i)),
                        ("ex:productCode", lit(best[1])),
                        ("ex:matchedName", lit(used)),
                        ("ex:matchScore", float_lit(round(best[0], 4))),
                        ("ex:tiedCandidates", f'"{ties}"^^xsd:integer'),
                        ("ex:linkMethod", lit(METHOD)),
                        ("ex:linkConfidence", lit(confidence(best[0]))),
                    ])
    stats = {"device_interventions": n_iv, "candidates": n_hit,
             "rate": round(n_hit / n_iv, 4) if n_iv else None, "threshold": threshold}
    with open(os.path.join(out_dir, "devicematch_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))
    return stats


def _selftest():
    assert similarity("Implantable cardioverter defibrillator",
                      "Implantable cardioverter defibrillator (non-CRT)") > 0.75
    assert similarity("Alpha dressing", "Dressing, wound, drug") > 0
    assert similarity("Sham", "Stent, coronary") == 0.0
    idx = Index([{"device_name": "Stent, Coronary", "product_code": "MAF"},
                 {"device_name": "Dressing, Wound, Hydrogel", "product_code": "NAE"}])
    b, _ = idx.best("Coronary stent", 0.75)
    assert b and b[1] == "MAF", b
    assert idx.best("Sham device", 0.75)[0] is None
    print("device_match.py self-test PASSED.")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _selftest()
    else:
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("classification_json")
        ap.add_argument("download_dir")
        ap.add_argument("out_dir")
        ap.add_argument("--threshold", type=float, default=0.75)
        a = ap.parse_args()
        run(a.classification_json, a.download_dir, a.out_dir, a.threshold)
