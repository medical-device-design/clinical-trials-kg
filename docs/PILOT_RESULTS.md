# Pilot results: device-intervention studies (November 20, 2026)

Run on VM .83 (`/srv/clinical-trials-kg`, TAG `pilot-device`), owner Roche de Guzman.

## Scope and size

| Measure | Value |
|---|---|
| Studies fetched (`AREA[InterventionType]DEVICE`) | 77,301 in 78 pages, all accounted for |
| Studies converted / skipped | 77,301 / 0 |
| Triples (core + links) | 28,301,568 (about 366 per study) |
| Exact-identifier link triples | 5,543 |
| Turtle on disk | 2.6 GB (downloads 241 MB gzipped) |
| Convert time / peak RAM | 1 min 34 s / 199 MB (one page at a time) |
| Validation | 78 of 78 pages pass riot and Jena SHACL (6 parallel jobs, about 5 min) |
| Cross-file check | 0 orphans, 0 e-mail literals, 0 contact fields |

## Issues found and fixed

| # | Issue found in the first pilot | Fix | Result after rerun |
|---|---|---|---|
| 1 | Field audit (`scripts/probe_fields.py`): 82 of 325 JSON paths not read, including participant flow, baseline characteristics, protocol and SAP documents, retractions, NCT aliases, submission and QC dates, unposted-results and violation annotations, expanded access, IPD details, see-also links | Mapped all of them (new classes FlowGroup, FlowPeriod, FlowMilestone, FlowWithdrawal, BaselineGroup, BaselineMeasure, BaselineMeasurement, BaselineDenominator, StudyDocument, SeeAlsoLink, AvailableIpd, UnpostedResultsEvent, ViolationEvent, ResultsSubmissionCycle) | 13 paths not read: 9 are contact e-mails and phones (excluded by decision), 4 are rare expanded-access flags read by a loop the probe cannot see |
| 2 | 195 e-mail addresses in official names, affiliations and see-also URLs, some also inside person IRIs | Every literal is scrubbed at write time, names are scrubbed before IRIs are minted | 0 e-mails |
| 3 | Arm-to-intervention links only from `armGroupLabels` | Also linked from `armGroups.interventionNames` | Tested |
| 4 | Serial SHACL took 7 to 15 s per page, about 2.5 h for the full load | `validate.sh` runs pages in parallel (`JOBS`) | About 22 pages per minute with 6 jobs |
| 5 | Orphan check held every IRI of the graph in memory | Checked per page group (exact, because each page describes its own shared nodes) | Memory bounded by one page |

Triples rose from 23.4 M to 28.3 M (+21%) with the added sections.

## Findings to keep in mind

* **FDA submission numbers are rare.** Only 25 FDA submission links (IDE, 510(k), PMA, De Novo, HDE, IND, NDA, BLA) were found in 77,301 device studies (0.03%), from 10,768 secondary IDs. Exact FDA joins will come mostly from other routes (sponsor identity, NCT numbers recorded in FDA or PubMed data).
* **Device-to-product-code candidates are weak.** At threshold 0.75, 7,800 of 106,458 device interventions (7.3%) got a candidate, and 2,033 of those tied with other product codes. In a random sample of 25, about half were plausible and several were clearly wrong ("Doppler" to Weather Doppler, "TAVR" to a generic valve prosthesis, "Catheter ablation" to renal denervation). **Do not publish `devicematch/` until the 200-record precision check is done** (open item 6).
* Class counts in `check_stats.json` count shared nodes (organizations, persons, conditions, MeSH, publications, countries) once per page, so they overstate unique totals.
