# clinical-trials-kg

ClinicalTrials.gov as a knowledge graph for the Open Knowledge Network (okn.us), built to the same standard as `medical-device-kg` and `nih-reporter-kg`.

* Shortname: `clinical-trials-kg` (do not change after publication, it is in every IRI)
* Namespace: `https://bmedesign.org/clinical-trials-kg/ns/` (vocabulary) and `/id/` (instances)
* Scope: all registered studies (about 605,000), with device studies flagged by intervention type and the FDA device flag
* Contact: Roche de Guzman, roche0619@outlook.com

## Layout

| Path | Role |
|---|---|
| `pipeline/iri.py` | Single source of every IRI |
| `pipeline/common.py` | Literals, provenance, block writer (partial dates, plain decimals, e-mail scrub) |
| `pipeline/ct_to_rdf.py` | API v2 records to Turtle, one file per page |
| `pipeline/linkage/identifiers.py` | Exact IDs in secondary IDs: IDE, 510(k), PMA, De Novo, HDE, IND, NDA, BLA, NIH grants |
| `pipeline/linkage/device_match.py` | Baseline device-to-product-code candidates (not published; the shared matcher lives in bmedesign-kg) |
| `scripts/fetch_ct.py` | Paged download of full records, manifest with counts and checksums |
| `scripts/validate.sh` | riot plus Jena SHACL per page, then `check_graph.py` |
| `scripts/check_graph.py` | Orphans, e-mails, forbidden contact fields, class counts |
| `scripts/run_pilot.sh` | Tests, fetch, convert, validate, measure |
| `scripts/weekly_delta.sh` | Update by last-update date, run quarterly per the master-control policy or on demand |
| `ontology/shapes/ct.shacl.ttl` | SHACL shapes |
| `tests/` | Synthetic records and end-to-end tests |

## Run on VM .83

```bash
bash scripts/setup_vm.sh                       # once
cd $CTKG/repo
python3 tests/test_pipeline.py                 # must print ALL TESTS PASSED
SCOPE=device bash scripts/run_pilot.sh         # pilot, about 76,000 studies
SCOPE=all TAG=full-$(date +%F) bash scripts/run_pilot.sh   # full load
```

## Local query endpoint (VM .83)

The full build (612,892 studies, 343,250,455 triples, ClinicalTrials.gov snapshot of November 21, 2026) is loaded in TDB2 at `/srv/clinical-trials-kg/tdb2/full-2026-11-21` (32 GB, xloader, 1 h 38 min) and served read-only by Fuseki on `http://localhost:3032/clinical-trials/sparql` (localhost only, dataset `/clinical-trials`). Reach it from a PC with `ssh -L 3032:localhost:3032 <user>@10.22.12.83` over the Hofstra VPN. A count of `ClinicalStudy` returns 612,892 in under 1 s. `scripts/load_tdb2.sh` rebuilds the store and switches Fuseki after each quarterly refresh.

## Output

Per page of up to 1,000 studies:
* `page_NNNNN.ttl` is the core graph (studies, arms, interventions, outcomes, results, adverse events, sites, officials, references)
* `page_NNNNN.links.ttl` is the exact-identifier linkage (FDA submission numbers, NIH core project numbers)
* `devicematch/page_NNNNN.devicematch.ttl` is the baseline product-code candidates, kept out of the published graph

Every cross-graph link states its method and confidence. None is asserted as identity.

## Rules carried over from the device KG

* Full data kept. Free text is never truncated.
* Overall officials (name, affiliation, role) are published. Central contacts, site contacts and the results point of contact are never written. E-mail addresses in free text become `[EMAIL REMOVED]`.
* Nothing goes to lakeFS until the full load is complete and validated. One upload, then merge and tag only with the PI's approval.

## Credits

The results data model (outcome measures, groups, denominators, measurements, statistical analyses, adverse-event groups and per-group statistics), the field map, partial-date typing and the device-name scorer were first built by **Adelyn Mathew** (HUSSRP 2026, mentor Roche de Guzman) on the `clinicaltrials-harvester` branch of `medical-device-design/medical-device-kg`, last commit `d3be34e`. This repository ports that work to the rebuild standard.

## License

CC0 1.0 for the code, ontology and compiled graph (see `LICENSE`), the same as medical-device-kg and the FDA graphs. Source data are from ClinicalTrials.gov (U.S. National Library of Medicine). Every study records its source, ClinicalTrials.gov page, retrieval date and NLM processing date, and `LICENSE` states the modifications. MedDRA adverse-event term text is third-party content excluded from the dedication.

## Alignment with the KG family

Shared conventions (namespaces, identifier formats, cross-graph join keys, licence) are being standardized by a central control layer across all of the PI's graphs. Where it differs from this repo, the central standard wins; see `docs/OPEN_ITEMS.md` item 11.
