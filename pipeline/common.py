#!/usr/bin/env python3
"""
common.py -- shared Turtle literal, provenance, and serialization helpers.

Copied from medical-device-kg-pipeline/pipeline/common.py (same contract), with
three changes that should be ported back to the other graphs:

  1. float_lit uses Decimal, so amounts of 1e6 or more are no longer written in
     exponent form ("2.5e+06" is not a valid xsd:decimal). Same fix as the
     nih-reporter-kg pilot.
  2. date_lit types partial dates: "2019-05" -> xsd:gYearMonth, "2019" -> xsd:gYear.
     ClinicalTrials.gov reports many start and completion dates to the month only.
     Credit: partial-date handling first written by Adelyn Mathew in the
     clinicaltrials-harvester branch (August 2026).
  3. scrub_emails / text_lit: e-mail addresses in free text are replaced with
     "[EMAIL REMOVED]", the same rule used for medical-device-kg v0.0.7.

Division of labour:
    iri.py     mints every IRI
    common.py  formats every literal, the provenance block, and writes blocks
    sources    decide WHICH triples a record has and own no formatting
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_YM = re.compile(r"^(\d{4})-(\d{2})$")
YEAR = re.compile(r"^\d{4}$")
YYYYMMDD = re.compile(r"^\d{8}$")
US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EMAIL_MASK = "[EMAIL REMOVED]"


# ---------------------------------------------------------------------------
# String literals
# ---------------------------------------------------------------------------
def esc(value):
    """Escape a Python string for a Turtle double-quoted literal."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def lit(value):
    """Plain string literal, or None if blank (None objects are skipped later)."""
    if value is None:
        return None
    s = str(value).strip()
    return f'"{esc(s)}"' if s else None


def scrub_emails(value):
    """Replace every e-mail address with [EMAIL REMOVED]. Returns None for None."""
    if value is None:
        return None
    return EMAIL.sub(EMAIL_MASK, str(value))


def text_lit(value):
    """Free-text literal: e-mails scrubbed, never truncated."""
    return lit(scrub_emails(value))


# ---------------------------------------------------------------------------
# Typed literals
# ---------------------------------------------------------------------------
def bool_lit(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return '"true"^^xsd:boolean' if value else '"false"^^xsd:boolean'
    s = str(value).strip().lower()
    if s in ("true", "yes", "y", "1"):
        return '"true"^^xsd:boolean'
    if s in ("false", "no", "n", "0"):
        return '"false"^^xsd:boolean'
    return None


def int_lit(value):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        return f'"{int(str(value).strip())}"^^xsd:integer'
    except (ValueError, TypeError):
        return None


def float_lit(value):
    """xsd:decimal in plain notation (never exponent form), or None.
    Values that are not numbers ("NA", "<0.001") return None, so callers that
    must keep such text write it with lit() alongside."""
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return f'"{s}"^^xsd:decimal'


def _valid_date(y, m, d):
    try:
        datetime(int(y), int(m), int(d))
        return True
    except ValueError:
        return False


def date_lit(value):
    """
    xsd:date for a real calendar date (ISO, 8-digit, or MM/DD/YYYY),
    xsd:gYearMonth for YYYY-MM, xsd:gYear for YYYY. Anything else is kept as an
    untyped string, never emitted as an invalid typed literal. None if blank.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if ISO_DATE.match(s):
        y, m, d = s[0:4], s[5:7], s[8:10]
        return f'"{s}"^^xsd:date' if _valid_date(y, m, d) else f'"{esc(s)}"'
    m = ISO_YM.match(s)
    if m:
        return f'"{s}"^^xsd:gYearMonth' if 1 <= int(m.group(2)) <= 12 else f'"{esc(s)}"'
    if YEAR.match(s):
        return f'"{s}"^^xsd:gYear'
    if YYYYMMDD.match(s):
        y, mo, d = s[0:4], s[4:6], s[6:8]
        return f'"{y}-{mo}-{d}"^^xsd:date' if _valid_date(y, mo, d) else f'"{esc(s)}"'
    m = US_DATE.match(s)
    if m:
        mo, d, y = m.groups()
        if _valid_date(y, mo, d):
            return f'"{y}-{int(mo):02d}-{int(d):02d}"^^xsd:date'
        return f'"{esc(s)}"'
    return f'"{esc(s)}"'


def as_list(value):
    """Normalise a repeatable field to a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return [p.strip() for p in str(value).split(";") if p.strip()]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
def provenance(dataset, record_id, source_url=None, retrieved_at=None):
    """Standard provenance pairs in a fixed order. retrieved_at MUST come from the
    fetch manifest, never datetime.now(), so output stays reproducible."""
    pairs = [
        ("ex:sourceDataset", lit(dataset)),
        ("ex:sourceRecordId", lit(record_id)),
    ]
    if source_url is not None:
        pairs.append(("ex:sourceUrl", lit(source_url)))
    if retrieved_at is not None:
        pairs.append(("ex:retrievedAt", date_lit(retrieved_at)))
    return pairs


# ---------------------------------------------------------------------------
# Turtle serialization
# ---------------------------------------------------------------------------
def write_block(out, subject, pairs):
    """Write one Turtle subject block, skipping pairs whose object is None.
    Returns the number of triples written."""
    valid = [(p, o) for p, o in pairs if o is not None]
    if not valid:
        return 0
    out.write(f"{subject}\n")
    for i, (pred, obj) in enumerate(valid):
        sep = " ;" if i < len(valid) - 1 else " ."
        out.write(f"    {pred} {obj}{sep}\n")
    out.write("\n")
    return len(valid)


def prefixes(extra=None):
    base = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
    }
    if extra:
        base.update(extra)
    return "".join(f"@prefix {p}: <{u}> .\n" for p, u in base.items())


def _selftest():
    assert date_lit("2016-09-12") == '"2016-09-12"^^xsd:date'
    assert date_lit("20160912") == '"2016-09-12"^^xsd:date'
    assert date_lit("2019-05") == '"2019-05"^^xsd:gYearMonth'
    assert date_lit("2019-13") == '"2019-13"'
    assert date_lit("2019") == '"2019"^^xsd:gYear'
    assert date_lit("2016-13-45") == '"2016-13-45"'
    assert date_lit("02/17/2017") == '"2017-02-17"^^xsd:date'
    assert date_lit("") is None and date_lit(None) is None
    assert bool_lit(True) == '"true"^^xsd:boolean'
    assert bool_lit("false") == '"false"^^xsd:boolean'
    assert bool_lit("maybe") is None
    assert int_lit("42") == '"42"^^xsd:integer' and int_lit(True) is None
    assert float_lit("2.0") == '"2"^^xsd:decimal'
    assert float_lit("2500000") == '"2500000"^^xsd:decimal'       # was "2.5e+06"
    assert float_lit("0.00012") == '"0.00012"^^xsd:decimal'
    assert float_lit("-0") == '"0"^^xsd:decimal'
    assert float_lit("NA") is None and float_lit("<0.001") is None
    assert lit('a"b') == '"a\\"b"' and lit("") is None
    assert text_lit("Contact jane.doe@site.org now") == '"Contact [EMAIL REMOVED] now"'
    assert as_list(["a", " b ", "", None]) == ["a", "b"]
    p = provenance("ClinicalTrials.gov", "NCT1", retrieved_at="2026-11-20")
    assert ("ex:retrievedAt", '"2026-11-20"^^xsd:date') in p
    import io
    buf = io.StringIO()
    assert write_block(buf, "<s>", [("ex:a", '"1"'), ("ex:b", None)]) == 1
    print("common.py self-test PASSED.")


if __name__ == "__main__":
    _selftest()
