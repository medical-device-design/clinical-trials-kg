# Full build results (November 21, 2026)

Run on VM .83 (`/srv/clinical-trials-kg`, TAG `full-2026-11-21`), owner Roche de Guzman. Code at commit `33ce02f`, after the pilot fixes (see `PILOT_RESULTS.md`). Not uploaded to lakeFS.

## Size and run

| Measure | Value |
|---|---|
| Studies fetched (all of ClinicalTrials.gov) | 612,892 in 613 pages, manifest complete (API total 612,892) |
| Retrieved | November 20 to 21, 2026 (`retrievedAt` 2026-11-20) |
| Studies converted / skipped | 612,892 / 0 |
| Triples (core + links) | 343,250,455 (about 560 per study) |
| Typed instances | 47,610,423 (shared nodes counted once per page) |
| Turtle on disk | 30 GB (downloads 2.1 GB gzipped) |
| Convert time / peak RAM | 23 min / 259 MB |
| Validation | 613 of 613 pages pass riot and Jena SHACL (6 parallel jobs, about 35 min) |
| Cross-file check | 0 orphans, 0 e-mail literals, 0 contact fields (about 60 min) |

## Content (selected classes)

| Class | Count |
|---|---|
| ClinicalStudy | 612,892 |
| Intervention | 1,037,062 |
| PlannedOutcome | 3,844,725 |
| OutcomeMeasure (posted results) | 676,629 |
| AdverseEvent (serious and other) | 3,448,399 |
| AdverseEventStatistic | 12,270,264 |
| BaselineMeasurement | 3,012,625 |
| FlowMilestone | 912,461 |
| StudySite | 3,566,927 |
| StudyReference | 1,160,606 |
| StudyDocument (protocol, SAP, consent) | 88,476 |
| SecondaryIdentifier | 179,124 |
| UnpostedResultsEvent | 34,158 |
| ViolationEvent (FDAAA 801) | 18 |

## Exact-identifier links

| Link | Count |
|---|---|
| Study to NIH core project number (joins research-award-kg) | 36,394 |
| Study to FDA submission | 168 in total: IND 136, IDE 26, ANDA 3, 510(k) 1, PMA 1, NDA 1 |

FDA submission numbers remain rare (168 in 612,892 studies), so device-side joins will rely on sponsor identity and on NCT numbers held in FDA and PubMed data.

## Device-to-product-code candidates (weak signal, not for publication yet)

106,458 device interventions, 7,800 candidates at threshold 0.75 (7.3%), the same as the pilot because device-type interventions occur only in device studies. About half of a 25-record sample was plausible. Keep `devicematch/` out of the published graph until the 200-record precision check (open item 6).

## Before publication

Open items 2 to 10 in `docs/OPEN_ITEMS.md` still apply, above all the licence (item 3), the research-award-kg IRI pattern for the NIH links (item 4), the ontology file (item 7) and the registry size estimate (item 8: about 343 M triples, 30 GB Turtle).
