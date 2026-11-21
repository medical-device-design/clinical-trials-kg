#!/usr/bin/env python3
"""
iri.py -- the single source of every IRI in clinical-trials-kg.

Same contract as medical-device-kg-pipeline/pipeline/iri.py:
  * every IRI is minted HERE and nowhere else
  * namespace migration = edit the two lines NS and ID
  * deterministic: same input, same IRI, always
  * empty keys raise (no silent 'unknown' orphan nodes)

KEY CHOICES
-----------
  study                NCT ID                          skos:exactMatch clinicaltrials.gov
  arm, intervention,   NCT ID + position in record     never shared across trials (fixes the
  outcome, group, ...                                  legacy "Sham device" merge)
  organization         normalized name                 sponsors and collaborators; linked to FDA
                                                       firms only through the linkage layer
  person               normalized name + affiliation   overall officials (published, Roche 2026-11-20)
  condition            normalized condition text       MeSH links sit on the study (derived section)
  mesh                 MeSH descriptor ID (D012345)    skos:exactMatch id.nlm.nih.gov
  publication          PMID                            skos:exactMatch identifiers.org
  country              normalized name
"""

import hashlib
import re
import unicodedata

# ===========================================================================
#  THE TWO LINES THAT DEFINE THE NAMESPACE.
# ===========================================================================
NS = "https://bmedesign.org/clinical-trials-kg/ns/"   # vocabulary
ID = "https://bmedesign.org/clinical-trials-kg/id/"   # instances

# External bases, used only as skos:exactMatch targets for cross-graph joins.
CTGOV_STUDY = "https://clinicaltrials.gov/study/"
PUBMED = "https://identifiers.org/pubmed:"
MESH = "http://id.nlm.nih.gov/mesh/"
# NIH core project: the canonical IRI set by the master control (bmedesign-kg
# ids/identifiers.yaml, nihProjectNumber.iri_template). research-award-kg links its own
# project nodes to it with skos:exactMatch, so trials join awards through this IRI.
NIH_PROJECT = "https://bmedesign.org/core/id/nih-project/"

NCT = re.compile(r"^NCT\d{8}$")
_SLUG = re.compile(r"[^a-z0-9]+")


def _req(value, what):
    s = "" if value is None else str(value).strip()
    if not s:
        raise ValueError(f"iri: empty key for {what}")
    return s


def norm_name(value):
    """Normalized form used as a key: accents folded, lower case, punctuation to
    single spaces. 'Medtronic, Inc.' and 'MEDTRONIC INC' give the same key."""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(_SLUG.sub(" ", s.lower()).split())


def slug(value, what):
    """URL-safe key from a name. Long names get a short hash suffix so IRIs stay
    under 120 characters while staying deterministic and collision-resistant."""
    n = norm_name(_req(value, what))
    if not n:
        # name made only of punctuation or non-Latin characters
        n = "h-" + hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:16]
        return n
    s = n.replace(" ", "-")
    if len(s) > 80:
        s = s[:64].rstrip("-") + "-" + hashlib.sha1(n.encode()).hexdigest()[:12]
    return s


def _u(path):
    return f"<{ID}{path}>"


def ns(term):
    return f"<{NS}{term}>"


# --- top-level entities ------------------------------------------------------
def study(nct):
    n = _req(nct, "study").upper()
    if not NCT.match(n):
        raise ValueError(f"iri: not an NCT ID: {nct!r}")
    return _u(f"study/{n}")


def ctgov_page(nct):
    return f"<{CTGOV_STUDY}{_req(nct, 'ctgov page').upper()}>"


def organization(name):
    return _u(f"organization/{slug(name, 'organization')}")


def person(name, affiliation=None):
    key = slug(name, "person")
    if affiliation and norm_name(affiliation):
        key += "--" + slug(affiliation, "person affiliation")
    return _u(f"person/{key}")


def condition(text):
    return _u(f"condition/{slug(text, 'condition')}")


def mesh(descriptor_id):
    d = _req(descriptor_id, "mesh")
    if not re.match(r"^[A-Z]\d{6,9}$", d):
        raise ValueError(f"iri: not a MeSH ID: {d!r}")
    return _u(f"mesh/{d}")


def mesh_external(descriptor_id):
    return f"<{MESH}{_req(descriptor_id, 'mesh')}>"


def publication(pmid):
    p = _req(pmid, "publication")
    if not p.isdigit():
        raise ValueError(f"iri: not a PMID: {pmid!r}")
    return _u(f"publication/{p}")


def pubmed_external(pmid):
    return f"<{PUBMED}{_req(pmid, 'pmid')}>"


def country(name):
    return _u(f"country/{slug(name, 'country')}")


def nih_project(core_project_num):
    return f"<{NIH_PROJECT}{_req(core_project_num, 'nih project').upper()}>"


# --- per-study children (never shared across studies) -------------------------
def _child(nct, kind, *parts):
    base = study(nct)[1:-1]
    tail = "/".join(str(_req(p, kind)) for p in parts)
    return f"<{base}/{kind}/{tail}>"


def arm(nct, i):                       return _child(nct, "arm", i)
def intervention(nct, i):              return _child(nct, "intervention", i)
def planned_outcome(nct, kind, i):     return _child(nct, "planned-outcome", kind.lower(), i)
def location(nct, i):                  return _child(nct, "location", i)
def official(nct, i):                  return _child(nct, "official", i)
def secondary_id(nct, i):              return _child(nct, "secondary-id", i)
def reference(nct, i):                 return _child(nct, "reference", i)
def outcome_measure(nct, i):           return _child(nct, "outcome-measure", i)
def outcome_group(nct, om, gid):       return _child(nct, "outcome-measure", om, "group", gid)
def denom_count(nct, om, d, gid):      return _child(nct, "outcome-measure", om, "denom", d, gid)
def measurement(nct, om, i):           return _child(nct, "outcome-measure", om, "measurement", i)
def analysis(nct, om, i):              return _child(nct, "outcome-measure", om, "analysis", i)
def ae_module(nct):                    return _child(nct, "adverse-events", "all")
def ae_group(nct, gid):                return _child(nct, "adverse-events", "group", gid)
def ae_term(nct, kind, i):             return _child(nct, "adverse-events", kind.lower(), i)
def ae_stat(nct, kind, i, gid):        return _child(nct, "adverse-events", kind.lower(), i, "group", gid)
def pf_group(nct, gid):               return _child(nct, "participant-flow", "group", gid)
def pf_period(nct, i):                 return _child(nct, "participant-flow", "period", i)
def pf_milestone(nct, p, i, gid):      return _child(nct, "participant-flow", "period", p, "milestone", i, gid)
def pf_withdrawal(nct, p, i, j):       return _child(nct, "participant-flow", "period", p, "withdrawal", i, j)
def bl_group(nct, gid):                return _child(nct, "baseline", "group", gid)
def bl_measure(nct, i):                return _child(nct, "baseline", "measure", i)
def bl_measurement(nct, m, k):         return _child(nct, "baseline", "measure", m, "measurement", k)
def bl_denom(nct, d, gid):             return _child(nct, "baseline", "denom", d, gid)
def document(nct, i):                  return _child(nct, "document", i)
def annotation(nct, kind, i):          return _child(nct, "annotation", kind.lower(), i)
def see_also(nct, i):                  return _child(nct, "see-also", i)
def ipd(nct, i):                       return _child(nct, "available-ipd", i)
def fda_link(nct, i):                  return _child(nct, "fda-link", i)
def device_match(nct, i, k):           return _child(nct, "device-match", i, k)


def _selftest():
    assert study("NCT01234567") == f"<{ID}study/NCT01234567>"
    assert study("nct01234567") == f"<{ID}study/NCT01234567>"
    for bad in ("", None, "NCT123", "12345678"):
        try:
            study(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert organization("Medtronic, Inc.") == organization("MEDTRONIC INC")
    assert organization("Medtronic, Inc.").endswith("organization/medtronic-inc>")
    assert organization("Hôpital Necker") == organization("Hopital Necker")
    long_name = "A" * 50 + " " + "B" * 60
    assert len(organization(long_name)) < 200
    assert person("Jane Doe, MD", "Hofstra") != person("Jane Doe, MD", "Yale")
    assert arm("NCT01234567", 0) == f"<{ID}study/NCT01234567/arm/0>"
    assert arm("NCT01234567", 0) != arm("NCT07654321", 0)
    assert outcome_group("NCT01234567", 2, "OG000").endswith("/outcome-measure/2/group/OG000>")
    assert mesh("D003920").endswith("mesh/D003920>")
    try:
        mesh("diabetes")
        raise AssertionError
    except ValueError:
        pass
    assert publication("12345") == f"<{ID}publication/12345>"
    print("iri.py self-test PASSED.")


if __name__ == "__main__":
    _selftest()
