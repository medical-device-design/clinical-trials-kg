#!/usr/bin/env python3
"""
check_graph.py -- cross-file checks Jena SHACL cannot do on one file at a time.

  1. orphans     every object IRI in our /id/ namespace is typed somewhere
  2. e-mails     no literal contains an e-mail address
  3. contacts    no central/site contact predicates ever appear
  4. counts      typed instances per class, total triples

Streams N-Triples via Jena `riot` when available (VM), else parses with rdflib
(tests). Usage: check_graph.py OUT_DIR [--json stats.json]
"""

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

ID = "https://bmedesign.org/clinical-trials-kg/id/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
FORBIDDEN = ("centralContact", "contactEmail", "contactPhone", "pointOfContactEmail")
NT = re.compile(r'^(<[^>]*>|_:\S+)\s+<([^>]*)>\s+(.*)\s+\.\s*$')


def triples(path):
    riot = shutil.which("riot")
    if riot:
        p = subprocess.Popen([riot, "--output=nt", path], stdout=subprocess.PIPE, text=True)
        for line in p.stdout:
            m = NT.match(line)
            if m:
                yield m.group(1).strip("<>"), m.group(2), m.group(3)
        if p.wait() != 0:
            raise SystemExit(f"riot failed on {path}")
    else:
        import rdflib
        g = rdflib.Graph()
        g.parse(path, format="turtle")
        for s, p, o in g:
            ob = f"<{o}>" if isinstance(o, rdflib.URIRef) else '"' + str(o) + '"'
            yield str(s), str(p), ob


def main(argv):
    """Orphans are checked per page group (page_N.ttl plus page_N.*.ttl), which is
    exact because every page file describes its own shared nodes. This keeps
    memory at one page instead of the whole graph."""
    out_dir = argv[0]
    stats_path = argv[2] if len(argv) > 2 and argv[1] == "--json" else None
    classes, n, emails, forbidden, orphans = Counter(), 0, [], [], []
    files = sorted(f for f in os.listdir(out_dir) if f.endswith(".ttl"))
    groups = {}
    for f in files:
        groups.setdefault(f.split(".")[0], []).append(f)
    typed_total = 0
    for key in sorted(groups):
        typed, referenced = set(), set()
        for f in groups[key]:
            for s, p, o in triples(os.path.join(out_dir, f)):
                n += 1
                if p == RDF_TYPE:
                    typed.add(s)
                    classes[o.strip("<>")] += 1
                elif o.startswith("<") and o[1:].startswith(ID):
                    referenced.add(o.strip("<>"))
                if o.startswith('"') and EMAIL.search(o):
                    emails.append((s, p))
                if any(k in p for k in FORBIDDEN):
                    forbidden.append((s, p))
        typed_total += len(typed)
        orphans.extend(sorted(referenced - typed))
    report = {
        "files": len(files), "triples": n, "typed_instances": typed_total,
        "orphans": len(orphans), "orphan_examples": orphans[:10],
        "email_literals": len(emails), "email_examples": emails[:5],
        "forbidden_predicates": len(forbidden),
        "classes": {k.rsplit("/", 1)[-1]: v for k, v in sorted(classes.items())},
    }
    print(json.dumps(report, indent=2))
    if stats_path:
        with open(stats_path, "w") as fh:
            json.dump(report, fh, indent=2)
    ok = not orphans and not emails and not forbidden
    print("check_graph:", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
