# Open items before publication

| # | Item | Owner | Why it matters |
|---|---|---|---|
| 1 | First real run on VM .83. The code has only run on synthetic records. My workspace cannot reach clinicaltrials.gov. | RB | Real records will show fields and shapes the fixtures do not |
| 2 | Confirm the `filter.advanced` syntax (`AREA[InterventionType]DEVICE`, `AREA[LastUpdatePostDate]RANGE[...]`) returns the expected counts (about 76,000 device studies on October 2, 2026) | RB | Wrong filter means a wrong pilot scope |
| 3 | Licence. Current NLM terms ask for attribution, a processing date and a statement of modifications. Older terms also mention international copyright outside the United States. Decide whether CC0 is right or whether the registry entry should state "U.S. Government work, attribute ClinicalTrials.gov". | RD | Must be settled before the registry PR |
| 4 | Confirm the `research-award-kg` (formerly nih-reporter-kg) project IRI pattern in `iri.NIH_REPORTER_PROJECT` | RB | Otherwise the NIH grant links point to IRIs that do not exist |
| 5 | Decide how FDA submission numbers join the device KG (literal match on the device KG's own submission-number property, or IRIs after the namespace migration) | MB, PS | The exact-ID links are only useful once they join |
| 6 | Hand-review 200 device-to-product-code candidates and publish precision before using them in Paper 1 or a proposal | MB | The scorer is a weak signal |
| 7 | Write `ontology/ontology.ttl` (class and property declarations with labels) from the classes in use. Run a vocabulary check like the device KG's `vocab_check.py` | AM, PS | Registry Schema tab and MCP tools read it |
| 8 | Size estimate for the okn-registry PR, from the pilot's triples per study times the full count | RB | RENCI asks for it before creating the lakeFS repo |
| 9 | Port the `common.py` fixes back to the device and FDA graphs: `float_lit` exponent bug, partial-date typing | RB | Same helper exists in those pipelines |

Owners: RD Roche de Guzman, RB Raham Butt, PS Prabhjot Singh, MB Mustafa Bukhari, AM Adelyn Mathew.
