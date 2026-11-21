# Open items before publication

| # | Item | Owner | Why it matters |
|---|---|---|---|
| 1 | DONE November 21, 2026: device pilot and full build on VM .83 (see PILOT_RESULTS.md, FULL_BUILD_RESULTS.md). | RD | Real records will show fields and shapes the fixtures do not |
| 2 | DONE November 21, 2026: `AREA[InterventionType]DEVICE` returned 77,301 device studies, in line with the 76,273 counted on October 2. | RD | Pilot scope confirmed |
| 3 | DONE November 21, 2026: CC0 1.0 (Roche decision), matching medical-device-kg and the FDA graphs. `LICENSE` meets NLM's attribution, processing-date and modifications requests and excludes MedDRA term text. | RD | Registry entry can state CC0 |
| 4 | Confirm the `research-award-kg` (formerly nih-reporter-kg) project IRI pattern in `iri.NIH_REPORTER_PROJECT` | RD | Otherwise the NIH grant links point to IRIs that do not exist |
| 5 | Decide how FDA submission numbers join the device KG (literal match on the device KG's own submission-number property, or IRIs after the namespace migration) | RD | The exact-ID links are only useful once they join |
| 6 | Hand-review 200 device-to-product-code candidates (50 per score band) in the Sheet "clinical-trials-kg device match review (200)", then publish precision before using them in Paper 1 or a proposal. Sheet built November 21, 2026, review pending. | RD | The scorer is a weak signal |
| 7 | Write `ontology/ontology.ttl` (class and property declarations with labels) from the classes in use. Run a vocabulary check like the device KG's `vocab_check.py` | RD | Registry Schema tab and MCP tools read it |
| 8 | Size for the okn-registry PR: measured 343,250,455 triples, 30 GB Turtle (full build, November 21, 2026) | RD | RENCI asks for it before creating the lakeFS repo |
| 9 | `common.py` fixes ported as PRs: medical-device-kg-pipeline #21, FDA-kg #1 (November 21, 2026). Scan: 0 exponent decimals in either; 5,520 untyped partial dates in the FDA graphs (cosmetic events, warning letters) to regenerate after merge. | RD | Same helper exists in those pipelines |
| 10 | Align publication joins with the PubMed KG (`medical-device-design/pubmed-scraper`, Raham Butt). Its `papers.csv` keeps `nct_ids` (links NLM recorded on the paper) apart from `nct_ids_in_text`. When it becomes RDF, both graphs should mark each paper `skos:exactMatch <https://identifiers.org/pubmed:PMID>` and link NLM-recorded NCT IDs to `https://bmedesign.org/clinical-trials-kg/id/study/NCT...`. Its README also keeps abstracts out of the public graph for copyright, the same rule applies here (this graph stores no abstracts). | RD | Paper-to-trial links in both directions |
| 11 | Align with the central control layer that standardizes all of the PI's KGs (developed in a separate session): namespace and IRI patterns, shared join keys (NCT, PMID, NIH core project number, FDA submission number, organization identity), class and property names, licence and provenance fields. Adjust `iri.py` and the ontology to its standard before the lakeFS upload. | RD | The graphs must cross-talk |

Owner: RD Roche de Guzman (November 20, 2026). Raham Butt is on the PubMed KG (`pubmed-scraper`). Adelyn Mathew uses the graph for her report and does not build it.
