#!/usr/bin/env python3
"""Write ontology/ontology.ttl from a vocab_scan.py result, so every ex: term the
converter emits is declared (master control rule L2-MAPPING). Domains and ranges are
the ones observed in the full build: one class or datatype gives rdfs:domain or
rdfs:range, several are listed in rdfs:comment instead of a union.

    python3 scripts/make_ontology.py vocab_scan_full.json > ontology/ontology.ttl
"""
import json
import re
import sys

NS = "https://bmedesign.org/clinical-trials-kg/ns/"
VERSION = "v0.0.1"

# words kept as written when the camelCase name is split into a label
ACRONYMS = {"nct": "NCT", "fda": "FDA", "ipd": "IPD", "mesh": "MeSH", "nih": "NIH", "pmid": "PMID",
            "qc": "QC", "us": "US", "id": "ID", "ids": "IDs", "url": "URL", "ae": "AE", "ci": "CI",
            "fdaaa801": "FDAAA 801", "wkt": "WKT", "p": "p"}
LABELS = {  # hand-set where the split name reads badly
    "pmid": "PubMed identifier", "nctId": "NCT identifier", "nctIdAlias": "former NCT identifier",
    "meshId": "MeSH descriptor identifier", "pValue": "p-value", "isUsExport": "is US export",
    "fdaaa801Violation": "FDAAA 801 violation", "hasViolationEvent": "has violation event",
    "MeSHConcept": "MeSH concept", "FdaSubmissionLink": "FDA submission link",
    "nihCoreProjectNumber": "NIH core project number", "fundedByNihProject": "funded by NIH project",
}


def label(name):
    if name in LABELS:
        return LABELS[name]
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+|[A-Z]+", name)
    out = [ACRONYMS.get(w.lower(), w.lower()) for w in words]
    return " ".join(out)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main(path):
    scan = json.load(open(path))
    lines = [
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        f"@prefix ex: <{NS}> .",
        "",
        f"<{NS}> a owl:Ontology ;",
        '    dcterms:title "ClinicalTrials.gov Knowledge Graph vocabulary" ;',
        "    dcterms:license <https://creativecommons.org/publicdomain/zero/1.0/> ;",
        f'    owl:versionInfo "{VERSION}" ;',
        '    rdfs:comment "Local terms of clinical-trials-kg. Shared identifiers and provenance map to the BMEdesign core vocabulary (https://bmedesign.org/core/ns/) through bmedesign-kg mappings/clinical-trials-kg.sssom.tsv." .',
        "",
        "# ---------------- classes ----------------",
    ]
    for c in scan["classes"]:
        n = c.split(":", 1)[1]
        lines.append(f'ex:{n} a owl:Class ; rdfs:label "{esc(label(n))}" .')
    lines += ["", "# ---------------- properties ----------------"]
    for p, u in scan["predicates"].items():
        n = p.split(":", 1)[1]
        is_obj = u["iri"] > 0 and not u["lit"]
        kind = "owl:ObjectProperty" if is_obj else ("owl:DatatypeProperty" if not u["iri"] else "rdf:Property")
        parts = [f"ex:{n} a {kind}", f'rdfs:label "{esc(label(n))}"']
        dom = [d for d in u["domain"] if d.startswith("ex:")]
        if len(dom) == 1:
            parts.append(f"rdfs:domain {dom[0]}")
        notes = []
        if len(dom) > 1:
            notes.append("used on " + ", ".join(d.split(":", 1)[1] for d in dom))
        if is_obj:
            tg = [t for t in u["iri_targets"] if t.startswith("ex:")]
            if len(tg) == 1 and len(u["iri_targets"]) == 1:
                parts.append(f"rdfs:range {tg[0]}")
            elif u["iri_targets"]:
                notes.append("points to " + ", ".join(t.split(":", 1)[1] if t.startswith("ex:") else t.strip("<")
                                                     for t in u["iri_targets"][:6]))
        elif u["lit"]:
            if len(u["lit"]) == 1:
                parts.append(f"rdfs:range {u['lit'][0]}")
            else:
                notes.append("values typed " + ", ".join(u["lit"]))
        if notes:
            parts.append(f'rdfs:comment "{esc("; ".join(notes).replace("; ", ". "))}."')
        lines.append(" ;\n    ".join(parts) + " .")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
