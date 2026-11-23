#!/usr/bin/env python3
"""End-to-end tests on synthetic records: python3 tests/test_pipeline.py"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import rdflib                                    # noqa: E402
from rdflib.namespace import RDF, RDFS, XSD      # noqa: E402
import make_fixtures                             # noqa: E402
import ct_to_rdf                                 # noqa: E402

EX = rdflib.Namespace("https://bmedesign.org/clinical-trials-kg/ns/")
ID = "https://bmedesign.org/clinical-trials-kg/id/"
S1 = rdflib.URIRef(ID + "study/NCT09000001")
S2 = rdflib.URIRef(ID + "study/NCT09000002")
FAILS = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def run(dl, out):
    rc = ct_to_rdf.main([dl, out])
    g = rdflib.Graph()
    for f in sorted(os.listdir(out)):
        if f.endswith(".ttl"):
            g.parse(os.path.join(out, f), format="turtle")
    return rc, g


def digest(out):
    h = hashlib.sha256()
    for f in sorted(os.listdir(out)):
        if f.endswith(".ttl"):
            h.update(open(os.path.join(out, f), "rb").read())
    return h.hexdigest()


def main():
    tmp = tempfile.mkdtemp()
    dl, out, out2 = (os.path.join(tmp, x) for x in ("dl", "out", "out2"))
    make_fixtures.write(dl)

    print("conversion")
    rc, g = run(dl, out)
    stats = json.load(open(os.path.join(out, "convert_stats.json")))
    check("exit code 0 (converted + skipped = manifest total)", rc == 0, rc)
    check("3 studies converted, 1 bad record skipped",
          stats["studies"] == 3 and stats["skipped"] == 1, stats)

    print("determinism")
    run(dl, out2)
    check("rerun is byte-identical", digest(out) == digest(out2))

    print("legacy bugs fixed")
    dfu = rdflib.URIRef(ID + "condition/diabetic_foot_ulcer")
    check("both studies link to the shared condition (legacy linked only the first)",
          (S1, EX.hasCondition, dfu) in g and (S2, EX.hasCondition, dfu) in g)
    serious = list(g.subjects(EX.seriousness, rdflib.Literal("SERIOUS")))
    check("serious adverse events converted (legacy read only 'other')", len(serious) == 1)
    shams = [s for s in g.subjects(EX.interventionName, rdflib.Literal("Sham device"))]
    check("'Sham device' stays one node per study (no cross-trial merge)", len(shams) == 2, shams)
    lead = g.value(S1, EX.leadSponsor)
    check("sponsor typed Organization, not Manufacturer",
          (lead, RDF.type, EX.Organization) in g and not list(g.subjects(RDF.type, EX.Manufacturer)))
    check("'Medtronic, Inc.' and 'MEDTRONIC INC' are one organization",
          len({o for o in g.objects(None, EX.leadSponsor) if "medtronic" in str(o)}) == 1)

    print("master control rules (bmedesign-kg)")
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    med = next(o for o in g.objects(None, EX.leadSponsor) if "medtronic" in str(o))
    labels = set(g.objects(med, RDFS.label))
    check("one rdfs:label per organization across pages (L1-LABEL), mixed case preferred on a tie",
          labels == {rdflib.Literal("Medtronic, Inc.")}, labels)
    check("other spelling kept as skos:altLabel",
          set(g.objects(med, SKOS.altLabel)) == {rdflib.Literal("MEDTRONIC INC")})
    multi = [s for s in set(g.subjects(RDFS.label, None)) if len(set(g.objects(s, RDFS.label))) > 1]
    check("no node has two rdfs:label values", not multi, multi[:3])
    pubs = list(g.subjects(RDF.type, EX.Publication))
    check("publications carry one label 'PMID N'",
          pubs and all(str(g.value(p, RDFS.label)) == "PMID " + str(g.value(p, EX.pmid)) for p in pubs))
    hubs = [s for c in ("Organization", "Person", "Condition", "MeSHConcept", "Publication", "Country")
            for s in g.subjects(RDF.type, EX[c])]
    check("every shared hub carries sourceDataset and retrievedAt (master option C)",
          hubs and all(g.value(h, EX.sourceDataset) and g.value(h, EX.retrievedAt) for h in hubs))
    nih = rdflib.URIRef("https://bmedesign.org/core/id/nih-project/R01EB012345")
    check("NIH link uses the canonical core IRI (ids/identifiers.yaml)", (S1, EX.fundedByNihProject, nih) in g)
    onto = rdflib.Graph().parse(os.path.join(ROOT, "ontology", "ontology.ttl"))
    declared = set(onto.subjects(RDF.type, None))
    used = {t for t in set(g.predicates()) | set(g.objects(None, RDF.type)) if str(t).startswith(str(EX))}
    check("every ex: term the converter emits is declared in ontology.ttl (L2-MAPPING)",
          used <= declared, sorted(str(t) for t in used - declared)[:5])
    vg = rdflib.Graph().parse(os.path.join(out, "void.ttl"))
    DCT = rdflib.Namespace("http://purl.org/dc/terms/")
    ds = rdflib.URIRef("https://bmedesign.org/clinical-trials-kg/")
    check("void.ttl: CC0, version, snapshot date (L2-METADATA)",
          (ds, DCT.license, rdflib.URIRef("https://creativecommons.org/publicdomain/zero/1.0/")) in vg
          and str(vg.value(ds, rdflib.OWL.versionInfo)) == "v0.0.1" and vg.value(ds, DCT.issued) is not None)

    print("full data kept")
    dd = str(g.value(S1, EX.detailedDescription))
    check("50,000-character description kept whole", len(dd) == 50000, len(dd))
    check("partial start date typed gYearMonth",
          g.value(S1, EX.startDate) == rdflib.Literal("2019-05", datatype=XSD.gYearMonth))
    check("year-only date typed gYear",
          g.value(S2, EX.startDate) == rdflib.Literal("2025", datatype=XSD.gYear))
    check("phases kept (multi-valued)", len(list(g.objects(S2, EX.phase))) == 2)
    pv = list(g.subjects(EX.pValueText, rdflib.Literal("<0.001")))
    check("p-value text '<0.001' kept even though not a number", len(pv) == 1)
    big = list(g.subjects(EX.paramValue, rdflib.Literal("2500000", datatype=XSD.decimal)))
    check("2,500,000 written as plain xsd:decimal (no exponent)", len(big) == 1)
    na = [m for m in g.subjects(EX.valueText, rdflib.Literal("NA"))]
    check("'NA' measurement kept as text without a numeric value",
          len(na) == 1 and g.value(na[0], EX.value) is None)
    check("measurement points to its group node",
          all((g.value(m, EX.group), RDF.type, EX.OutcomeGroup) in g
              for m in g.subjects(RDF.type, EX.OutcomeMeasurement)))
    check("site has GeoSPARQL point and ZIP",
          any("POINT(-73.618700 40.706200)" in str(o) for o in g.objects(None, None))
          and (None, EX.postalCode, rdflib.Literal("11549")) in g)
    check("PMID linked with identifiers.org exactMatch",
          (rdflib.URIRef(ID + "publication/31234567"), rdflib.URIRef("http://www.w3.org/2004/02/skos/core#exactMatch"),
           rdflib.URIRef("https://identifiers.org/pubmed:31234567")) in g)

    print("sections added after the pilot field audit")
    started = [m for m in g.subjects(EX.milestoneType, rdflib.Literal("STARTED"))]
    check("participant flow: STARTED milestone per group", len(started) == 2, len(started))
    check("participant flow: withdrawal reason kept",
          len(list(g.subjects(EX.withdrawalReason, rdflib.Literal("Lost to Follow-up")))) == 2)
    check("baseline: age measurements typed with group links",
          len(list(g.subjects(RDF.type, EX.BaselineMeasurement))) == 2
          and all((g.value(m, EX.group), RDF.type, EX.BaselineGroup) in g
                  for m in g.subjects(RDF.type, EX.BaselineMeasurement)))
    doc = next(iter(g.subjects(RDF.type, EX.StudyDocument)), None)
    check("protocol document with derived URL",
          doc is not None and str(g.value(doc, EX.derivedUrl)).endswith("/01/NCT09000001/Prot_SAP_000.pdf"))
    check("reference retraction flagged and linked",
          (None, EX.isRetracted, rdflib.Literal(True)) in g
          and (None, EX.retractionNotice, rdflib.URIRef(ID + "publication/39999999")) in g)
    check("NCT alias kept", g.value(S1, EX.nctIdAlias) == rdflib.Literal("NCT08999999"))
    check("source version date typed",
          g.value(S1, EX.sourceVersionDate) == rdflib.Literal("2026-11-20", datatype=XSD.date))
    check("unposted-results event and submission cycle kept",
          len(list(g.subjects(RDF.type, EX.UnpostedResultsEvent))) == 1
          and len(list(g.subjects(RDF.type, EX.ResultsSubmissionCycle))) == 1)
    check("arm linked to intervention via armGroups.interventionNames",
          (rdflib.URIRef(ID + "study/NCT09000001/intervention/1"), EX.inArm,
           rdflib.URIRef(ID + "study/NCT09000001/arm/1")) in g)

    print("privacy")
    ttl = "".join(open(os.path.join(out, f)).read() for f in os.listdir(out) if f.endswith(".ttl"))
    check("no e-mail addresses anywhere (incl. official names, affiliations, URLs)",
          "@testco" not in ttl and "@clinic" not in ttl and "@uni" not in ttl)
    check("no e-mail fragments inside IRIs", "uni-example-edu" not in ttl, "")
    check("e-mail in summary replaced with [EMAIL REMOVED]", "[EMAIL REMOVED]" in ttl)
    check("central and site contact names not written", "Pat Contact" not in ttl and "Site Person" not in ttl)
    check("contact phones not written", "555-01" not in ttl)
    check("overall official published (Roche decision)", "Jane Doe, MD" in ttl)

    print("linkage layer (exact identifiers)")
    subs = {str(o) for o in g.objects(None, EX.submissionNumber)}
    check("IDE G170123 linked", "G170123" in subs)
    check("PMA P100023/S045 linked", "P100023/S045" in subs)
    check("bare K170999 typed OTHER not linked (precision)", "K170999" not in subs)
    check("IND 123456 linked", "123456" in subs)
    check("NIH grant -> core project R01EB012345",
          g.value(S1, EX.nihCoreProjectNumber) == rdflib.Literal("R01EB012345"))
    check("every FDA link states method and confidence",
          all(g.value(l, EX.linkMethod) and g.value(l, EX.linkConfidence)
              for l in g.subjects(RDF.type, EX.FdaSubmissionLink)))

    print("SHACL")
    import pyshacl
    shapes = rdflib.Graph().parse(os.path.join(ROOT, "ontology/shapes/ct.shacl.ttl"), format="turtle")
    conforms, _, text = pyshacl.validate(g, shacl_graph=shapes, inference="none")
    check("SHACL conforms", conforms, text[:600])
    bad = rdflib.Graph() + g
    bad.add((S1, EX.enrollment, rdflib.Literal("lots")))
    bad.add((rdflib.URIRef(ID + "x"), RDF.type, EX.AdverseEvent))   # no seriousness
    conforms_bad, _, _ = pyshacl.validate(bad, shacl_graph=shapes, inference="none")
    check("SHACL rejects a broken graph (shapes are live)", not conforms_bad)

    print("cross-file checks")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts/check_graph.py"), out],
                       capture_output=True, text=True)
    check("check_graph.py passes (0 orphans, 0 e-mails)", r.returncode == 0, r.stdout[-800:])

    print("device to product-code candidates (weak signal)")
    import linkage.device_match as dm
    cls = os.path.join(tmp, "classification.json")
    json.dump({"results": [{"device_name": "Dressing, Wound, Alpha Hydrogel", "product_code": "NAE"},
                           {"device_name": "Stent, Coronary", "product_code": "MAF"}]}, open(cls, "w"))
    dm_out = os.path.join(tmp, "dm")
    st = dm.run(cls, dl, dm_out, threshold=0.5)
    gm = rdflib.Graph()
    for f in os.listdir(dm_out):
        if f.endswith(".ttl"):
            gm.parse(os.path.join(dm_out, f), format="turtle")
    codes = {str(o) for o in gm.objects(None, EX.productCode)}
    check("'Alpha dressing' gets candidate NAE", codes == {"NAE"}, codes)
    check("'Sham device' gets no candidate", st["candidates"] == 1, st)
    iv_targets = set(gm.objects(None, EX.intervention))
    check("candidate points to a typed intervention in the core graph",
          all((t, RDF.type, EX.Intervention) in g for t in iv_targets) and iv_targets)

    shutil.rmtree(tmp)
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
