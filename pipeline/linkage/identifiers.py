#!/usr/bin/env python3
"""
identifiers.py -- pull exact identifiers out of ClinicalTrials.gov secondary IDs.

These are the HIGH-confidence links (an identifier written by the sponsor), as
opposed to name matching. Each hit records the pattern that matched, so the
linkage layer can state its method.

  FDA device submissions   IDE G######, 510(k) K######, PMA P######(/S###),
                           De Novo DEN######, HDE H######
  FDA drug/biologic        IND (5-6 digits, only when the record says FDA/IND),
                           NDA / BLA / ANDA numbers when labelled
  NIH grants               activity code + IC + serial, e.g. 5R01EB012345-03
                           -> core project number R01EB012345 (joins nih-reporter-kg)

Measured context (October 2, 2026 sample): only 0.3% of 600 industry device trials
carried an FDA-style identifier, so expect low recall and high precision.
"""

import re

_SEP = r"[\s\-]?"

FDA_DEVICE = [
    ("DeNovo", re.compile(r"\bDEN" + _SEP + r"(\d{6})\b", re.I), "DEN"),
    ("IDE", re.compile(r"\b(?:IDE[\s#:]*)?G" + _SEP + r"(\d{6})\b", re.I), "G"),
    ("510(k)", re.compile(r"\b(?:510\s?\(?k\)?[\s#:]*)?K" + _SEP + r"(\d{6})\b", re.I), "K"),
    ("PMA", re.compile(r"\b(?:PMA[\s#:]*)?P" + _SEP + r"(\d{6})(?:[\s\-/]?(S\d{3}))?\b", re.I), "P"),
    ("HDE", re.compile(r"\b(?:HDE[\s#:]*)?H" + _SEP + r"(\d{6})\b", re.I), "H"),
]

FDA_DRUG = [
    ("IND", re.compile(r"\bIND[\s#:\-]*(\d{5,6})\b", re.I)),
    ("NDA", re.compile(r"\bNDA[\s#:\-]*(\d{6})\b", re.I)),
    ("ANDA", re.compile(r"\bANDA[\s#:\-]*(\d{6})\b", re.I)),
    ("BLA", re.compile(r"\bBLA[\s#:\-]*(\d{6})\b", re.I)),
]

# NIH grant: optional application type digit, activity code (3 chars, letter
# first), 2-letter IC, 6-digit serial, optional support-year suffix.
NIH_GRANT = re.compile(
    r"\b(?:\d)?\s?([A-Z][A-Z0-9]{2})\s?-?\s?([A-Z]{2})\s?-?\s?(\d{6})(?:-\d{2}[A-Z0-9]*)?\b"
)
# Codes that look like grants but are not (avoid FDA numbers being read as grants)
_NOT_ACTIVITY = {"DEN", "IND", "NDA", "BLA", "IDE", "PMA", "HDE", "NCT"}


def fda_ids(text, id_type=None):
    """Return [(submission_type, normalized_number)] found in one secondary ID.
    Bare G/K/P/H numbers are accepted only when the record type is FDA or the
    text names the submission, because K123456 alone is often a sponsor code."""
    s = str(text or "").strip()
    if not s:
        return []
    labelled = (id_type or "").upper() == "FDA" or re.search(
        r"\b(IDE|510\s?\(?k\)?|PMA|HDE|DEN|De\s?Novo|FDA)\b", s, re.I)
    out = []
    for name, rx, prefix in FDA_DEVICE:
        for m in rx.finditer(s):
            if name != "DeNovo" and not labelled:
                continue
            num = prefix + m.group(1)
            if name == "PMA" and m.lastindex and m.lastindex >= 2 and m.group(2):
                num += "/" + m.group(2).upper()
            if (name, num) not in out:
                out.append((name, num))
    for name, rx in FDA_DRUG:
        for m in rx.finditer(s):
            hit = (name, m.group(1))
            if hit not in out:
                out.append(hit)
    return out


def nih_core_projects(text, id_type=None):
    """Return core project numbers (e.g. R01EB012345) found in one secondary ID.
    Only for records typed NIH, or text that names NIH, to keep precision high."""
    s = str(text or "").upper()
    if not s.strip():
        return []
    if (id_type or "").upper() != "NIH" and "NIH" not in s:
        return []
    out = []
    for m in NIH_GRANT.finditer(s):
        act, ic, serial = m.groups()
        if act in _NOT_ACTIVITY:
            continue
        core = f"{act}{ic}{serial}"
        if core not in out:
            out.append(core)
    return out


def _selftest():
    assert fda_ids("G170123", "FDA") == [("IDE", "G170123")]
    assert fda_ids("IDE G170123", "OTHER") == [("IDE", "G170123")]
    assert fda_ids("K170123", "OTHER") == []                 # bare K: sponsor code risk
    assert fda_ids("510(k) K170123") == [("510(k)", "K170123")]
    assert fda_ids("PMA P100023/S045") == [("PMA", "P100023/S045")]
    assert fda_ids("DEN180044") == [("DeNovo", "DEN180044")]
    assert fda_ids("IND 123456", "FDA") == [("IND", "123456")]
    assert fda_ids("") == []
    assert nih_core_projects("5R01EB012345-03", "NIH") == ["R01EB012345"]
    assert nih_core_projects("R01 HL 123456", "NIH") == ["R01HL123456"]
    assert nih_core_projects("UG3TR002934", "NIH") == ["UG3TR002934"]
    assert nih_core_projects("R01EB012345", "OTHER") == []
    assert nih_core_projects("NIH grant R21NS099999") == ["R21NS099999"]
    print("identifiers.py self-test PASSED.")


if __name__ == "__main__":
    _selftest()
