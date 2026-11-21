#!/usr/bin/env python3
"""
fetch_ct.py -- download ClinicalTrials.gov study records (API v2) to page files.

Full records come straight from the list endpoint (pageSize up to 1000), so there
is NO per-study call (the legacy harvester fetched every study twice).

  Full load, all studies (Roche, 2026-11-20):
      fetch_ct.py --out $CTKG/downloads/2026-11-21
  Device-intervention pilot:
      fetch_ct.py --scope device --out $CTKG/downloads/pilot-device
  Weekly delta:
      fetch_ct.py --updated-since 2026-11-14 --out $CTKG/downloads/delta-2026-11-21

Writes page_00001.json.gz ... plus manifest.json (retrieved_at, query, total_count,
per-page counts and sha256). Exits non-zero if the pages do not add up to the
total the API reported, so a silent truncation can never reach the graph.

Stdlib only. Throttled (default 1.5 s between requests) with backoff on 429/5xx.
"""

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://clinicaltrials.gov/api/v2/studies"
UA = "clinical-trials-kg/0.1 (bmedesign.org; contact roche0619@outlook.com)"


def build_params(scope, updated_since, page_size):
    p = {"format": "json", "pageSize": str(page_size), "countTotal": "true"}
    adv = []
    if scope == "device":
        adv.append("AREA[InterventionType]DEVICE")
    if updated_since:
        adv.append(f"AREA[LastUpdatePostDate]RANGE[{updated_since},MAX]")
    if adv:
        p["filter.advanced"] = " AND ".join(adv)
    return p


def get_json(params, pause, max_tries=6):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(max_tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
            time.sleep(pause)
            return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_tries - 1:
                wait = pause * (2 ** (attempt + 1))
                print(f"[fetch_ct] HTTP {e.code}, retry in {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_tries - 1:
                wait = pause * (2 ** (attempt + 1))
                print(f"[fetch_ct] {e}, retry in {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--scope", choices=["all", "device"], default="all")
    ap.add_argument("--updated-since", help="YYYY-MM-DD, delta by last update post date")
    ap.add_argument("--page-size", type=int, default=1000)
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--max-pages", type=int, help="stop early (smoke test only)")
    a = ap.parse_args(argv)

    os.makedirs(a.out, exist_ok=True)
    params = build_params(a.scope, a.updated_since, a.page_size)
    manifest = {
        "source": "ClinicalTrials.gov API v2",
        "endpoint": BASE,
        "query": dict(params),
        "retrieved_at": dt.date.today().isoformat(),
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "pages": [],
    }
    token, page, total, seen = None, 0, None, 0
    while True:
        q = dict(params)
        if token:
            q["pageToken"] = token
        data = get_json(q, a.pause)
        if total is None:
            total = data.get("totalCount")
            print(f"[fetch_ct] totalCount reported by API: {total}")
        studies = data.get("studies") or []
        page += 1
        name = f"page_{page:05d}.json.gz"
        raw = json.dumps({"studies": studies}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        with gzip.open(os.path.join(a.out, name), "wb", compresslevel=6) as f:
            f.write(raw)
        seen += len(studies)
        manifest["pages"].append({"file": name, "studies": len(studies),
                                  "sha256": hashlib.sha256(raw).hexdigest()})
        print(f"[fetch_ct] {name}: {len(studies)} studies (running {seen}/{total})")
        token = data.get("nextPageToken")
        if not token or (a.max_pages and page >= a.max_pages):
            break

    manifest["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    manifest["api_total_count"] = total
    manifest["total_count"] = seen          # what the converter must account for
    # Studies are added daily, so a long run can see a few more than the first
    # totalCount. Fewer than reported is the failure that matters (truncation).
    manifest["complete"] = bool(total is not None and seen >= total)
    if total is not None and seen > total:
        print(f"[fetch_ct] note: {seen - total} more studies than first reported "
              "(records added during the run)")
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    if a.max_pages:
        print(f"[fetch_ct] smoke test: stopped after {page} pages, {seen} studies")
        return 0
    if not manifest["complete"]:
        print(f"[fetch_ct] ERROR: downloaded {seen} but API reported {total}", file=sys.stderr)
        return 2
    print(f"[fetch_ct] complete: {seen} studies in {page} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
