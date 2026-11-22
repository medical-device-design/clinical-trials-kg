# Master control

clinical-trials-kg is governed by the BMEdesign master control, `medical-device-design/bmedesign-kg` (private).

Before any build, upload or schema change, read there:
1. `MASTER_CONTROL.md`
2. `docs/instructions/clinical-trials-kg.md` (rulings and open items for this graph)
3. `requests/DECISIONS.md` (what has been decided)

Requests to the master go in `requests/inbox/` (template `requests/TEMPLATE.md`). Gate before any lakeFS upload: `python kgctl check clinical-trials-kg --path <release folder or sample>` must reach L1 for develop and L2 for main.
