# Open items before publication

| # | Item | Owner | Why it matters |
|---|---|---|---|
| 1 | First real run on VM .83. The code has only run on synthetic records so far. | RD | Real records will show fields and shapes the fixtures do not |
| 2 | Confirm the `filter.advanced` syntax (`AREA[InterventionType]DEVICE`, `AREA[LastUpdatePostDate]RANGE[...]`) returns the expected counts (about 76,000 device studies on October 2, 2026) | RD | Wrong filter means a wrong pilot scope |
| 3 | Licence. Current NLM terms ask for attribution, a processing date and a statement of modifications. Older terms also mention international copyright outside the United States. Decide whether CC0 is right or whether the registry entry should state "U.S. Government work, attribute ClinicalTrials.gov". | RD | Must be settled before the registry PR |
| 4 | Confirm the `research-award-kg` (formerly nih-reporter-kg) project IRI pattern in `iri.NIH_REPORTER_PROJECT` | RD | Otherwise the NIH grant links point to IRIs that do not exist |
| 5 | Decide how FDA submission numbers join the device KG (literal match on the device KG's own submission-number property, or IRIs after the namespace migration) | RD | The exact-ID links are only useful once they join |
| 6 | Hand-review 200 device-to-product-code candidates and publish precision before using them in Paper 1 or a proposal | RD | The scorer is a weak signal |
| 7 | Write `ontology/ontology.ttl` (class and property declarations with labels) from the classes in use. Run a vocabulary check like the device KG's `vocab_check.py` | RD | Registry Schema tab and MCP tools read it |
| 8 | Size estimate for the okn-registry PR, from the pilot's triples per study times the full count | RD | RENCI asks for it before creating the lakeFS repo |
| 9 | Port the `common.py` fixes back to the device and FDA graphs: `float_lit` exponent bug, partial-date typing | RD | Same helper exists in those pipelines |
| 10 | Align publication joins with the PubMed KG (`medical-device-design/pubmed-scraper`, Raham Butt). Its `papers.csv` keeps `nct_ids` (links NLM recorded on the paper) apart from `nct_ids_in_text`. When it becomes RDF, both graphs should mark each paper `skos:exactMatch <https://identifiers.org/pubmed:PMID>` and link NLM-recorded NCT IDs to `https://bmedesign.org/clinical-trials-kg/id/study/NCT...`. Its README also keeps abstracts out of the public graph for copyright, the same rule applies here (this graph stores no abstracts). | RD | Paper-to-trial links in both directions |

Owner: RD Roche de Guzman (November 20, 2026). Raham Butt is on the PubMed KG (`pubmed-scraper`). Adelyn Mathew uses the graph for her report and does not build it.
