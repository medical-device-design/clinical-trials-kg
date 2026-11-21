#!/usr/bin/env python3
"""
ct_to_rdf.py -- ClinicalTrials.gov API v2 study records -> Turtle.

Input : page files written by scripts/fetch_ct.py (JSON or JSON.gz, each
        {"studies": [...]}), plus the fetch manifest for retrieved_at.
Output: one .ttl per input page (core graph) and one *.links.ttl per page
        (linkage layer: exact identifiers found in secondary IDs).

Streams one page at a time, so peak RAM is one page (<= 1,000 studies).

Data model
----------
The results model (outcome measure -> groups, denominators, measurements,
statistical analyses; adverse-event groups -> terms -> per-group statistics) is
ported from Adelyn Mathew's clinicaltrials-harvester branch (August 2026), with
these fixes:
  * serious adverse events are converted (the branch read only "other" events)
  * every study links to its conditions (the branch linked only the first
    study that mentioned each condition)
  * sponsors and collaborators are ex:Organization, not ex:Manufacturer
  * interventions are per study, so "Sham device" in two trials stays two nodes
  * measurements and statistics point to their group node, not just a group ID
  * no fields dropped, free text never truncated, e-mails scrubbed

Privacy (Roche, 2026-11-20): overall officials (investigator name, affiliation,
role) are published. Central contacts, site contacts, and the results point of
contact (names, phones, e-mails) are never written.
"""

import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import iri                                   # noqa: E402
from common import (                         # noqa: E402
    lit, text_lit, bool_lit, int_lit, float_lit, date_lit, as_list,
    provenance, write_block, prefixes,
)
from linkage import identifiers              # noqa: E402

DATASET = "ClinicalTrials.gov"
PREFIX = prefixes({
    "ex": iri.NS,
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "geo": "http://www.opengis.net/ont/geosparql#",
})


def _g(d, *path):
    """Safe nested get: _g(study, 'protocolSection', 'statusModule', 'overallStatus')."""
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _wkt(lat, lon):
    """GeoSPARQL point (longitude first), or None if either coordinate is bad.
    Lat/long, not S2 cells, per Peter Rose (SDSC)."""
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return f'"POINT({lo:.6f} {la:.6f})"^^geo:wktLiteral'


def _date_pairs(pred, struct):
    """A ClinicalTrials.gov date struct {date, type} -> value plus ACTUAL/ESTIMATED."""
    if not isinstance(struct, dict):
        return []
    return [(pred, date_lit(struct.get("date"))),
            (pred + "Type", lit(struct.get("type")))]


class Writer:
    """Holds the output streams and the per-file 'already written' sets for
    shared nodes, so each shared node is described once per file."""

    def __init__(self, out, links):
        self.out, self.links = out, links
        self.seen = {k: set() for k in ("org", "person", "cond", "mesh", "pub", "country")}
        self.triples = 0
        self.link_triples = 0

    def block(self, s, pairs):
        self.triples += write_block(self.out, s, pairs)

    def link_block(self, s, pairs):
        self.link_triples += write_block(self.links, s, pairs)

    def _once(self, kind, key, s, pairs):
        if key not in self.seen[kind]:
            self.seen[kind].add(key)
            self.block(s, pairs)

    # --- shared nodes ------------------------------------------------------
    def organization(self, name, org_class=None):
        s = iri.organization(name)
        self._once("org", s, s, [("a", "ex:Organization"), ("rdfs:label", lit(name)),
                                 ("ex:normalizedName", lit(iri.norm_name(name)))])
        if org_class:
            # class can differ by role (rare); write per occurrence, RDF dedups
            self.block(s, [("ex:organizationClass", lit(org_class))])
        return s

    def person(self, name, affiliation):
        s = iri.person(name, affiliation)
        self._once("person", s, s, [("a", "ex:Person"), ("rdfs:label", lit(name)),
                                    ("ex:affiliation", lit(affiliation))])
        return s

    def condition(self, text):
        s = iri.condition(text)
        self._once("cond", s, s, [("a", "ex:Condition"), ("rdfs:label", lit(text))])
        return s

    def mesh(self, mid, term):
        s = iri.mesh(mid)
        self._once("mesh", s, s, [("a", "ex:MeSHConcept"), ("rdfs:label", lit(term)),
                                  ("ex:meshId", lit(mid)),
                                  ("skos:exactMatch", iri.mesh_external(mid))])
        return s

    def publication(self, pmid):
        s = iri.publication(pmid)
        self._once("pub", s, s, [("a", "ex:Publication"), ("ex:pmid", lit(pmid)),
                                 ("skos:exactMatch", iri.pubmed_external(pmid))])
        return s

    def country(self, name):
        s = iri.country(name)
        self._once("country", s, s, [("a", "ex:Country"), ("rdfs:label", lit(name))])
        return s


def convert_study(w, rec, retrieved_at):
    """Write all triples for one study. Returns the NCT ID, or None if skipped."""
    ps = rec.get("protocolSection") or {}
    ident = ps.get("identificationModule") or {}
    nct = (ident.get("nctId") or "").strip().upper()
    if not nct:
        return None
    S = iri.study(nct)

    status = ps.get("statusModule") or {}
    sponsor = ps.get("sponsorCollaboratorsModule") or {}
    oversight = ps.get("oversightModule") or {}
    desc = ps.get("descriptionModule") or {}
    conds = ps.get("conditionsModule") or {}
    design = ps.get("designModule") or {}
    dinfo = design.get("designInfo") or {}
    mask = dinfo.get("maskingInfo") or {}
    enroll = design.get("enrollmentInfo") or {}
    elig = ps.get("eligibilityModule") or {}
    ipd = ps.get("ipdSharingStatementModule") or {}
    resp = sponsor.get("responsibleParty") or {}

    # --- the study node ------------------------------------------------------
    pairs = [("a", "ex:ClinicalStudy"), ("rdfs:label", text_lit(ident.get("briefTitle")))]
    pairs += provenance(DATASET, nct, source_url=f"https://clinicaltrials.gov/study/{nct}",
                        retrieved_at=retrieved_at)
    pairs += [
        ("skos:exactMatch", iri.ctgov_page(nct)),
        ("ex:nctId", lit(nct)),
        ("ex:orgStudyId", lit(_g(ident, "orgStudyIdInfo", "id"))),
        ("ex:briefTitle", text_lit(ident.get("briefTitle"))),
        ("ex:officialTitle", text_lit(ident.get("officialTitle"))),
        ("ex:acronym", lit(ident.get("acronym"))),
        ("ex:overallStatus", lit(status.get("overallStatus"))),
        ("ex:lastKnownStatus", lit(status.get("lastKnownStatus"))),
        ("ex:whyStopped", text_lit(status.get("whyStopped"))),
        ("ex:statusVerifiedDate", date_lit(status.get("statusVerifiedDate"))),
        ("ex:hasResults", bool_lit(rec.get("hasResults"))),
        ("ex:studyType", lit(design.get("studyType"))),
        ("ex:primaryPurpose", lit(dinfo.get("primaryPurpose"))),
        ("ex:allocation", lit(dinfo.get("allocation"))),
        ("ex:interventionModel", lit(dinfo.get("interventionModel"))),
        ("ex:interventionModelDescription", text_lit(dinfo.get("interventionModelDescription"))),
        ("ex:observationalModel", lit(dinfo.get("observationalModel"))),
        ("ex:timePerspective", lit(dinfo.get("timePerspective"))),
        ("ex:masking", lit(mask.get("masking"))),
        ("ex:enrollment", int_lit(enroll.get("count"))),
        ("ex:enrollmentType", lit(enroll.get("type"))),
        ("ex:briefSummary", text_lit(desc.get("briefSummary"))),
        ("ex:detailedDescription", text_lit(desc.get("detailedDescription"))),
        ("ex:eligibilityCriteria", text_lit(elig.get("eligibilityCriteria"))),
        ("ex:healthyVolunteers", bool_lit(elig.get("healthyVolunteers"))),
        ("ex:sex", lit(elig.get("sex"))),
        ("ex:genderBased", bool_lit(elig.get("genderBased"))),
        ("ex:minimumAge", lit(elig.get("minimumAge"))),
        ("ex:maximumAge", lit(elig.get("maximumAge"))),
        ("ex:studyPopulation", text_lit(elig.get("studyPopulation"))),
        ("ex:samplingMethod", lit(elig.get("samplingMethod"))),
        ("ex:hasDataMonitoringCommittee", bool_lit(oversight.get("oversightHasDmc"))),
        ("ex:isFdaRegulatedDrug", bool_lit(oversight.get("isFdaRegulatedDrug"))),
        ("ex:isFdaRegulatedDevice", bool_lit(oversight.get("isFdaRegulatedDevice"))),
        ("ex:isUnapprovedDevice", bool_lit(oversight.get("isUnapprovedDevice"))),
        ("ex:isPediatricPostmarketSurveillance", bool_lit(oversight.get("isPpsd"))),
        ("ex:isUsExport", bool_lit(oversight.get("isUsExport"))),
        ("ex:ipdSharing", lit(ipd.get("ipdSharing"))),
        ("ex:ipdSharingDescription", text_lit(ipd.get("description"))),
        ("ex:responsiblePartyType", lit(resp.get("type"))),
        ("ex:responsibleInvestigatorTitle", lit(resp.get("investigatorTitle"))),
        ("ex:responsiblePartyOldNameTitle", lit(resp.get("oldNameTitle"))),
        ("ex:responsiblePartyOldOrganization", lit(resp.get("oldOrganization"))),
        ("ex:orgStudyIdType", lit(_g(ident, "orgStudyIdInfo", "type"))),
        ("ex:orgStudyIdLink", lit(_g(ident, "orgStudyIdInfo", "link"))),
        ("ex:firstQcReleaseDate", date_lit(_g(rec, "derivedSection", "miscInfoModule", "submissionTracking",
                                              "firstMcpInfo", "postDateStruct", "date"))),
        ("ex:studyFirstSubmitDate", date_lit(status.get("studyFirstSubmitDate"))),
        ("ex:studyFirstSubmitQcDate", date_lit(status.get("studyFirstSubmitQcDate"))),
        ("ex:lastUpdateSubmitDate", date_lit(status.get("lastUpdateSubmitDate"))),
        ("ex:resultsFirstSubmitDate", date_lit(status.get("resultsFirstSubmitDate"))),
        ("ex:resultsFirstSubmitQcDate", date_lit(status.get("resultsFirstSubmitQcDate"))),
        ("ex:dispositionFirstSubmitDate", date_lit(status.get("dispFirstSubmitDate"))),
        ("ex:dispositionFirstSubmitQcDate", date_lit(status.get("dispFirstSubmitQcDate"))),
        ("ex:hasExpandedAccess", bool_lit(_g(status, "expandedAccessInfo", "hasExpandedAccess"))),
        ("ex:expandedAccessNctId", lit(_g(status, "expandedAccessInfo", "nctId"))),
        ("ex:expandedAccessStatus", lit(_g(status, "expandedAccessInfo", "statusForNctId"))),
        ("ex:patientRegistry", bool_lit(design.get("patientRegistry"))),
        ("ex:targetDuration", lit(design.get("targetDuration"))),
        ("ex:maskingDescription", text_lit(mask.get("maskingDescription"))),
        ("ex:bioSpecRetention", lit(_g(design, "bioSpec", "retention"))),
        ("ex:bioSpecDescription", text_lit(_g(design, "bioSpec", "description"))),
        ("ex:genderDescription", text_lit(elig.get("genderDescription"))),
        ("ex:ipdAccessCriteria", text_lit(ipd.get("accessCriteria"))),
        ("ex:ipdTimeFrame", text_lit(ipd.get("timeFrame"))),
        ("ex:ipdUrl", lit(ipd.get("url"))),
        ("ex:fdaaa801Violation", bool_lit(oversight.get("fdaaa801Violation"))),
        ("ex:sourceVersionDate", date_lit(_g(rec, "derivedSection", "miscInfoModule", "versionHolder"))),
        ("ex:estimatedResultsFirstSubmitDate", date_lit(_g(rec, "derivedSection", "miscInfoModule",
                                                            "submissionTracking", "estimatedResultsFirstSubmitDate"))),
    ]
    for pred, key in (("ex:startDate", "startDateStruct"),
                      ("ex:primaryCompletionDate", "primaryCompletionDateStruct"),
                      ("ex:completionDate", "completionDateStruct"),
                      ("ex:firstPostDate", "studyFirstPostDateStruct"),
                      ("ex:resultsFirstPostDate", "resultsFirstPostDateStruct"),
                      ("ex:lastUpdatePostDate", "lastUpdatePostDateStruct")):
        pairs += _date_pairs(pred, status.get(key))
    pairs += [("ex:phase", lit(p)) for p in as_list(design.get("phases"))]
    pairs += [("ex:maskedRole", lit(r)) for r in as_list(mask.get("whoMasked"))]
    pairs += [("ex:stdAge", lit(a)) for a in as_list(elig.get("stdAges"))]
    pairs += [("ex:keyword", lit(k)) for k in as_list(conds.get("keywords"))]
    pairs += [("ex:ipdInfoType", lit(t)) for t in as_list(ipd.get("infoTypes"))]
    pairs += [("ex:nctIdAlias", lit(a)) for a in as_list(ident.get("nctIdAliases"))]
    pairs += [("ex:removedCountry", lit(c)) for c in as_list(_g(rec, "derivedSection", "miscInfoModule", "removedCountries"))]
    pairs += [("ex:expandedAccessType", lit(k)) for k, v in sorted((design.get("expandedAccessTypes") or {}).items()) if v]
    w.block(S, pairs)

    # --- sponsor, collaborators, responsible party ---------------------------
    lead = sponsor.get("leadSponsor") or {}
    if (lead.get("name") or "").strip():
        w.block(S, [("ex:leadSponsor", w.organization(lead["name"], lead.get("class")))])
    for c in sponsor.get("collaborators") or []:
        if (c.get("name") or "").strip():
            w.block(S, [("ex:collaborator", w.organization(c["name"], c.get("class")))])
    if (resp.get("investigatorFullName") or "").strip():
        w.block(S, [("ex:responsibleInvestigator",
                     w.person(resp["investigatorFullName"], resp.get("investigatorAffiliation")))])
    org = ident.get("organization") or {}
    if (org.get("fullName") or "").strip():
        w.block(S, [("ex:submittingOrganization", w.organization(org["fullName"], org.get("class")))])

    # --- conditions and MeSH (every study links; fixes the legacy bug) --------
    for c in as_list(conds.get("conditions")):
        w.block(S, [("ex:hasCondition", w.condition(c))])
    for kind, pred in (("conditionBrowseModule", "ex:conditionMesh"),
                       ("interventionBrowseModule", "ex:interventionMesh")):
        for m in _g(rec, "derivedSection", kind, "meshes") or []:
            mid = (m.get("id") or "").strip()
            if mid:
                try:
                    w.block(S, [(pred, w.mesh(mid, m.get("term")))])
                except ValueError:
                    pass

    # --- arms and interventions (per study) ----------------------------------
    ai = ps.get("armsInterventionsModule") or {}
    arm_iri = {}
    for i, a in enumerate(ai.get("armGroups") or []):
        A = iri.arm(nct, i)
        label = (a.get("label") or "").strip() or f"Arm {i + 1}"
        arm_iri[label] = A
        w.block(A, [("a", "ex:ArmGroup"), ("rdfs:label", text_lit(label)),
                    ("ex:armType", lit(a.get("type"))),
                    ("ex:description", text_lit(a.get("description")))])
        w.block(S, [("ex:hasArm", A)])
    iv_by_name = {}
    for i, iv in enumerate(ai.get("interventions") or []):
        nm = (iv.get("name") or "").strip().lower()
        if nm:
            iv_by_name.setdefault(nm, iri.intervention(nct, i))
    for i, a in enumerate(ai.get("armGroups") or []):
        for ref in as_list(a.get("interventionNames")):
            target = iv_by_name.get(ref.split(":", 1)[-1].strip().lower())
            if target:
                w.block(target, [("ex:inArm", iri.arm(nct, i))])
    for i, iv in enumerate(ai.get("interventions") or []):
        I = iri.intervention(nct, i)
        pairs = [("a", "ex:Intervention"), ("rdfs:label", text_lit(iv.get("name"))),
                 ("ex:interventionType", lit(iv.get("type"))),
                 ("ex:interventionName", text_lit(iv.get("name"))),
                 ("ex:description", text_lit(iv.get("description")))]
        pairs += [("ex:otherName", text_lit(n)) for n in as_list(iv.get("otherNames"))]
        pairs += [("ex:inArm", arm_iri[l]) for l in as_list(iv.get("armGroupLabels")) if l in arm_iri]
        w.block(I, pairs)
        w.block(S, [("ex:hasIntervention", I)])

    # --- planned outcomes ------------------------------------------------------
    om_mod = ps.get("outcomesModule") or {}
    for kind, key, pred in (("PRIMARY", "primaryOutcomes", "ex:hasPrimaryOutcome"),
                            ("SECONDARY", "secondaryOutcomes", "ex:hasSecondaryOutcome"),
                            ("OTHER", "otherOutcomes", "ex:hasOtherOutcome")):
        for i, o in enumerate(om_mod.get(key) or []):
            if not (o.get("measure") or "").strip():
                continue
            O = iri.planned_outcome(nct, kind, i)
            w.block(O, [("a", "ex:PlannedOutcome"), ("rdfs:label", text_lit(o.get("measure"))),
                        ("ex:outcomeType", lit(kind)),
                        ("ex:description", text_lit(o.get("description"))),
                        ("ex:timeFrame", text_lit(o.get("timeFrame")))])
            w.block(S, [(pred, O)])

    # --- overall officials (published); contacts never written ----------------
    cl = ps.get("contactsLocationsModule") or {}
    for i, off in enumerate(cl.get("overallOfficials") or []):
        if not (off.get("name") or "").strip():
            continue
        O = iri.official(nct, i)
        w.block(O, [("a", "ex:StudyOfficial"),
                    ("ex:person", w.person(off["name"], off.get("affiliation"))),
                    ("ex:officialRole", lit(off.get("role")))])
        w.block(S, [("ex:hasOfficial", O)])

    # --- locations (site, city, state, ZIP, country, point) -------------------
    for i, loc in enumerate(cl.get("locations") or []):
        L = iri.location(nct, i)
        pairs = [("a", "ex:StudySite"), ("rdfs:label", text_lit(loc.get("facility"))),
                 ("ex:facility", text_lit(loc.get("facility"))),
                 ("ex:recruitmentStatus", lit(loc.get("status"))),
                 ("ex:city", lit(loc.get("city"))), ("ex:state", lit(loc.get("state"))),
                 ("ex:postalCode", lit(loc.get("zip")))]
        if (loc.get("country") or "").strip():
            pairs.append(("ex:country", w.country(loc["country"])))
        gp = loc.get("geoPoint") or {}
        wkt = _wkt(gp.get("lat"), gp.get("lon"))
        if wkt:
            pairs.append(("geo:asWKT", wkt))
        w.block(L, pairs)
        w.block(S, [("ex:hasSite", L)])

    # --- references (PMID joins to PubMed and nih-reporter-kg) ----------------
    for i, ref in enumerate(_g(ps, "referencesModule", "references") or []):
        R = iri.reference(nct, i)
        pmid = str(ref.get("pmid") or "").strip()
        pairs = [("a", "ex:StudyReference"), ("ex:referenceType", lit(ref.get("type"))),
                 ("ex:citation", text_lit(ref.get("citation")))]
        if pmid.isdigit():
            pairs.append(("ex:publication", w.publication(pmid)))
        for rt in ref.get("retractions") or []:
            rp = str(rt.get("pmid") or "").strip()
            if rp.isdigit():
                pairs.append(("ex:retractionNotice", w.publication(rp)))
            pairs.append(("ex:retractionSource", text_lit(rt.get("source"))))
        if ref.get("retractions"):
            pairs.append(("ex:isRetracted", '"true"^^xsd:boolean'))
        w.block(R, pairs)
        w.block(S, [("ex:hasReference", R)])
    for i, sa in enumerate(_g(ps, "referencesModule", "seeAlsoLinks") or []):
        if not (sa.get("url") or "").strip():
            continue
        X = iri.see_also(nct, i)
        w.block(X, [("a", "ex:SeeAlsoLink"), ("rdfs:label", text_lit(sa.get("label"))),
                    ("ex:url", lit(sa.get("url")))])
        w.block(S, [("ex:hasSeeAlsoLink", X)])
    for i, d in enumerate(_g(ps, "referencesModule", "availIpds") or []):
        X = iri.ipd(nct, i)
        w.block(X, [("a", "ex:AvailableIpd"), ("ex:ipdId", lit(d.get("id"))),
                    ("ex:ipdType", lit(d.get("type"))), ("ex:url", lit(d.get("url"))),
                    ("ex:comment", text_lit(d.get("comment")))])
        w.block(S, [("ex:hasAvailableIpd", X)])

    # --- secondary IDs, plus exact-identifier links into the linkage file -----
    link_i = 0
    for i, sid in enumerate(ident.get("secondaryIdInfos") or []):
        val = (sid.get("id") or "").strip()
        if not val:
            continue
        X = iri.secondary_id(nct, i)
        w.block(X, [("a", "ex:SecondaryIdentifier"), ("ex:identifierValue", lit(val)),
                    ("ex:identifierType", lit(sid.get("type"))),
                    ("ex:identifierDomain", text_lit(sid.get("domain"))),
                    ("ex:identifierLink", lit(sid.get("link")))])
        w.block(S, [("ex:hasSecondaryId", X)])
        for sub_type, number in identifiers.fda_ids(val, sid.get("type")):
            Lk = iri.fda_link(nct, link_i)
            link_i += 1
            w.link_block(Lk, [("a", "ex:FdaSubmissionLink"), ("ex:study", S),
                              ("ex:submissionType", lit(sub_type)),
                              ("ex:submissionNumber", lit(number)),
                              ("ex:linkMethod", lit("secondary-id-pattern")),
                              ("ex:linkConfidence", '"high"'),
                              ("ex:fromSecondaryId", X)])
        for core in identifiers.nih_core_projects(val, sid.get("type")):
            w.link_block(S, [("ex:nihCoreProjectNumber", lit(core)),
                             ("ex:fundedByNihProject", iri.nih_project(core))])

    # --- results -----------------------------------------------------------------
    res = rec.get("resultsSection") or {}
    _outcome_measures(w, nct, S, _g(res, "outcomeMeasuresModule", "outcomeMeasures") or [])
    _adverse_events(w, nct, S, res.get("adverseEventsModule") or {})
    _participant_flow(w, nct, S, res.get("participantFlowModule") or {})
    _baseline(w, nct, S, res.get("baselineCharacteristicsModule") or {})
    _documents(w, nct, S, _g(rec, "documentSection", "largeDocumentModule") or {})
    _annotations(w, nct, S, _g(rec, "annotationSection", "annotationModule") or {})
    _submissions(w, nct, S, _g(rec, "derivedSection", "miscInfoModule", "submissionTracking",
                               "submissionInfos") or [])
    more = res.get("moreInfoModule") or {}
    if more:
        lim = more.get("limitationsAndCaveats") or {}
        agree = more.get("certainAgreement") or {}
        w.block(S, [("ex:limitationsAndCaveats", text_lit(lim.get("description"))),
                    ("ex:piSponsorEmployee", bool_lit(agree.get("piSponsorEmployee"))),
                    ("ex:restrictiveAgreement", bool_lit(agree.get("restrictiveAgreement"))),
                    ("ex:restrictionType", lit(agree.get("restrictionType"))),
                    ("ex:restrictionDetails", text_lit(agree.get("otherDetails"))),
                    ("ex:resultsPointOfContactOrganization",
                     text_lit(_g(more, "pointOfContact", "organization")))])
    return nct


def _outcome_measures(w, nct, S, measures):
    for om_i, om in enumerate(measures):
        M = iri.outcome_measure(nct, om_i)
        w.block(M, [("a", "ex:OutcomeMeasure"), ("rdfs:label", text_lit(om.get("title"))),
                    ("ex:outcomeType", lit(om.get("type"))),
                    ("ex:title", text_lit(om.get("title"))),
                    ("ex:description", text_lit(om.get("description"))),
                    ("ex:populationDescription", text_lit(om.get("populationDescription"))),
                    ("ex:reportingStatus", lit(om.get("reportingStatus"))),
                    ("ex:anticipatedPostingDate", date_lit(om.get("anticipatedPostingDate"))),
                    ("ex:paramType", lit(om.get("paramType"))),
                    ("ex:dispersionType", lit(om.get("dispersionType"))),
                    ("ex:unitOfMeasure", text_lit(om.get("unitOfMeasure"))),
                    ("ex:calculatePercent", bool_lit(om.get("calculatePct"))),
                    ("ex:timeFrame", text_lit(om.get("timeFrame"))),
                    ("ex:denomUnitsSelected", lit(om.get("denomUnitsSelected"))),
                    ("ex:typeUnitsAnalyzed", lit(om.get("typeUnitsAnalyzed")))])
        w.block(S, [("ex:hasOutcomeMeasure", M)])
        groups = {}
        for g in om.get("groups") or []:
            gid = (g.get("id") or "").strip()
            if not gid:
                continue
            G = iri.outcome_group(nct, om_i, gid)
            groups[gid] = G
            w.block(G, [("a", "ex:OutcomeGroup"), ("rdfs:label", text_lit(g.get("title"))),
                        ("ex:groupId", lit(gid)),
                        ("ex:description", text_lit(g.get("description")))])
            w.block(M, [("ex:hasGroup", G)])
        for d_i, d in enumerate(om.get("denoms") or []):
            for c in d.get("counts") or []:
                gid = (c.get("groupId") or "").strip()
                if not gid:
                    continue
                D = iri.denom_count(nct, om_i, d_i, gid)
                w.block(D, [("a", "ex:DenominatorCount"), ("ex:units", lit(d.get("units"))),
                            ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                            ("ex:count", int_lit(c.get("value")))])
                w.block(M, [("ex:hasDenominator", D)])
        k = 0
        for cls in om.get("classes") or []:
            for cat in cls.get("categories") or []:
                for ms in cat.get("measurements") or []:
                    gid = (ms.get("groupId") or "").strip()
                    X = iri.measurement(nct, om_i, k)
                    k += 1
                    w.block(X, [("a", "ex:OutcomeMeasurement"),
                                ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                                ("ex:classTitle", text_lit(cls.get("title"))),
                                ("ex:categoryTitle", text_lit(cat.get("title"))),
                                ("ex:valueText", lit(ms.get("value"))),
                                ("ex:value", float_lit(ms.get("value"))),
                                ("ex:spread", float_lit(ms.get("spread"))),
                                ("ex:lowerLimit", float_lit(ms.get("lowerLimit"))),
                                ("ex:upperLimit", float_lit(ms.get("upperLimit"))),
                                ("ex:comment", text_lit(ms.get("comment")))])
                    w.block(M, [("ex:hasMeasurement", X)])
        for a_i, an in enumerate(om.get("analyses") or []):
            A = iri.analysis(nct, om_i, a_i)
            pairs = [("a", "ex:StatisticalAnalysis"),
                     ("ex:pValueText", lit(an.get("pValue"))),
                     ("ex:pValue", float_lit(an.get("pValue"))),
                     ("ex:statisticalMethod", text_lit(an.get("statisticalMethod"))),
                     ("ex:paramType", text_lit(an.get("paramType"))),
                     ("ex:paramValue", float_lit(an.get("paramValue"))),
                     ("ex:ciPercent", float_lit(an.get("ciPctValue"))),
                     ("ex:ciNumSides", lit(an.get("ciNumSides"))),
                     ("ex:ciLowerLimit", float_lit(an.get("ciLowerLimit"))),
                     ("ex:ciUpperLimit", float_lit(an.get("ciUpperLimit"))),
                     ("ex:nonInferiorityType", lit(an.get("nonInferiorityType"))),
                     ("ex:nonInferiorityComment", text_lit(an.get("nonInferiorityComment"))),
                     ("ex:groupDescription", text_lit(an.get("groupDescription"))),
                     ("ex:pValueComment", text_lit(an.get("pValueComment"))),
                     ("ex:statisticalComment", text_lit(an.get("statisticalComment"))),
                     ("ex:estimateComment", text_lit(an.get("estimateComment"))),
                     ("ex:dispersionType", lit(an.get("dispersionType"))),
                     ("ex:dispersionValue", float_lit(an.get("dispersionValue"))),
                     ("ex:testedNonInferiority", bool_lit(an.get("testedNonInferiority"))),
                     ("ex:otherAnalysisDescription", text_lit(an.get("otherAnalysisDescription"))),
                     ("ex:ciLowerLimitComment", text_lit(an.get("ciLowerLimitComment"))),
                     ("ex:ciUpperLimitComment", text_lit(an.get("ciUpperLimitComment")))]
            pairs += [("ex:comparesGroup", groups[g]) for g in as_list(an.get("groupIds")) if g in groups]
            w.block(A, pairs)
            w.block(M, [("ex:hasAnalysis", A)])


def _adverse_events(w, nct, S, ae):
    if not ae:
        return
    AE = iri.ae_module(nct)
    w.block(AE, [("a", "ex:AdverseEventReport"),
                 ("ex:frequencyThreshold", float_lit(ae.get("frequencyThreshold"))),
                 ("ex:timeFrame", text_lit(ae.get("timeFrame"))),
                 ("ex:description", text_lit(ae.get("description"))),
                 ("ex:allCauseMortalityComment", text_lit(ae.get("allCauseMortalityComment")))])
    w.block(S, [("ex:hasAdverseEventReport", AE)])
    groups = {}
    for g in ae.get("eventGroups") or []:
        gid = (g.get("id") or "").strip()
        if not gid:
            continue
        G = iri.ae_group(nct, gid)
        groups[gid] = G
        w.block(G, [("a", "ex:AdverseEventGroup"), ("rdfs:label", text_lit(g.get("title"))),
                    ("ex:groupId", lit(gid)), ("ex:description", text_lit(g.get("description"))),
                    ("ex:deathsNumAffected", int_lit(g.get("deathsNumAffected"))),
                    ("ex:deathsNumAtRisk", int_lit(g.get("deathsNumAtRisk"))),
                    ("ex:seriousNumAffected", int_lit(g.get("seriousNumAffected"))),
                    ("ex:seriousNumAtRisk", int_lit(g.get("seriousNumAtRisk"))),
                    ("ex:otherNumAffected", int_lit(g.get("otherNumAffected"))),
                    ("ex:otherNumAtRisk", int_lit(g.get("otherNumAtRisk")))])
        w.block(AE, [("ex:hasGroup", G)])
    for kind, key in (("SERIOUS", "seriousEvents"), ("OTHER", "otherEvents")):
        for i, ev in enumerate(ae.get(key) or []):
            if not (ev.get("term") or "").strip():
                continue
            T = iri.ae_term(nct, kind, i)
            w.block(T, [("a", "ex:AdverseEvent"), ("rdfs:label", text_lit(ev.get("term"))),
                        ("ex:seriousness", lit(kind)),
                        ("ex:term", text_lit(ev.get("term"))),
                        ("ex:organSystem", text_lit(ev.get("organSystem"))),
                        ("ex:sourceVocabulary", lit(ev.get("sourceVocabulary"))),
                        ("ex:assessmentType", lit(ev.get("assessmentType"))),
                        ("ex:notes", text_lit(ev.get("notes")))])
            w.block(AE, [("ex:hasEvent", T)])
            for st in ev.get("stats") or []:
                gid = (st.get("groupId") or "").strip()
                if not gid:
                    continue
                X = iri.ae_stat(nct, kind, i, gid)
                w.block(X, [("a", "ex:AdverseEventStatistic"),
                            ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                            ("ex:numEvents", int_lit(st.get("numEvents"))),
                            ("ex:numAffected", int_lit(st.get("numAffected"))),
                            ("ex:numAtRisk", int_lit(st.get("numAtRisk")))])
                w.block(T, [("ex:hasStatistic", X)])


def _participant_flow(w, nct, S, pf):
    if not pf:
        return
    w.block(S, [("ex:recruitmentDetails", text_lit(pf.get("recruitmentDetails"))),
                ("ex:preAssignmentDetails", text_lit(pf.get("preAssignmentDetails"))),
                ("ex:flowTypeUnitsAnalyzed", lit(pf.get("typeUnitsAnalyzed")))])
    groups = {}
    for g in pf.get("groups") or []:
        gid = (g.get("id") or "").strip()
        if not gid:
            continue
        G = iri.pf_group(nct, gid)
        groups[gid] = G
        w.block(G, [("a", "ex:FlowGroup"), ("rdfs:label", text_lit(g.get("title"))),
                    ("ex:groupId", lit(gid)), ("ex:description", text_lit(g.get("description")))])
        w.block(S, [("ex:hasFlowGroup", G)])
    for p_i, per in enumerate(pf.get("periods") or []):
        P = iri.pf_period(nct, p_i)
        w.block(P, [("a", "ex:FlowPeriod"), ("rdfs:label", text_lit(per.get("title") or f"Period {p_i + 1}"))])
        w.block(S, [("ex:hasFlowPeriod", P)])
        for m_i, ms in enumerate(per.get("milestones") or []):
            for ach in ms.get("achievements") or []:
                gid = (ach.get("groupId") or "").strip()
                if not gid:
                    continue
                X = iri.pf_milestone(nct, p_i, m_i, gid)
                w.block(X, [("a", "ex:FlowMilestone"), ("ex:milestoneType", lit(ms.get("type"))),
                            ("ex:comment", text_lit(ms.get("comment") or ach.get("comment"))),
                            ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                            ("ex:numSubjects", int_lit(ach.get("numSubjects"))),
                            ("ex:numUnits", int_lit(ach.get("numUnits")))])
                w.block(P, [("ex:hasMilestone", X)])
        for d_i, dw in enumerate(per.get("dropWithdraws") or []):
            for r_i, rs in enumerate(dw.get("reasons") or []):
                gid = (rs.get("groupId") or "").strip()
                X = iri.pf_withdrawal(nct, p_i, d_i, r_i)
                w.block(X, [("a", "ex:FlowWithdrawal"), ("ex:withdrawalReason", lit(dw.get("type"))),
                            ("ex:comment", text_lit(dw.get("comment") or rs.get("comment"))),
                            ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                            ("ex:numSubjects", int_lit(rs.get("numSubjects")))])
                w.block(P, [("ex:hasWithdrawal", X)])


def _baseline(w, nct, S, bl):
    if not bl:
        return
    w.block(S, [("ex:baselinePopulationDescription", text_lit(bl.get("populationDescription"))),
                ("ex:baselineTypeUnitsAnalyzed", lit(bl.get("typeUnitsAnalyzed")))])
    groups = {}
    for g in bl.get("groups") or []:
        gid = (g.get("id") or "").strip()
        if not gid:
            continue
        G = iri.bl_group(nct, gid)
        groups[gid] = G
        w.block(G, [("a", "ex:BaselineGroup"), ("rdfs:label", text_lit(g.get("title"))),
                    ("ex:groupId", lit(gid)), ("ex:description", text_lit(g.get("description")))])
        w.block(S, [("ex:hasBaselineGroup", G)])
    for d_i, d in enumerate(bl.get("denoms") or []):
        for c in d.get("counts") or []:
            gid = (c.get("groupId") or "").strip()
            if not gid:
                continue
            D = iri.bl_denom(nct, d_i, gid)
            w.block(D, [("a", "ex:BaselineDenominator"), ("ex:units", lit(d.get("units"))),
                        ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                        ("ex:count", int_lit(c.get("value")))])
            w.block(S, [("ex:hasBaselineDenominator", D)])
    for m_i, ms in enumerate(bl.get("measures") or []):
        M = iri.bl_measure(nct, m_i)
        w.block(M, [("a", "ex:BaselineMeasure"), ("rdfs:label", text_lit(ms.get("title"))),
                    ("ex:title", text_lit(ms.get("title"))),
                    ("ex:description", text_lit(ms.get("description"))),
                    ("ex:populationDescription", text_lit(ms.get("populationDescription"))),
                    ("ex:paramType", lit(ms.get("paramType"))),
                    ("ex:dispersionType", lit(ms.get("dispersionType"))),
                    ("ex:unitOfMeasure", text_lit(ms.get("unitOfMeasure"))),
                    ("ex:calculatePercent", bool_lit(ms.get("calculatePct"))),
                    ("ex:denomUnitsSelected", lit(ms.get("denomUnitsSelected")))])
        w.block(S, [("ex:hasBaselineMeasure", M)])
        k = 0
        for cls in ms.get("classes") or []:
            for cat in cls.get("categories") or []:
                for x in cat.get("measurements") or []:
                    gid = (x.get("groupId") or "").strip()
                    X = iri.bl_measurement(nct, m_i, k)
                    k += 1
                    w.block(X, [("a", "ex:BaselineMeasurement"),
                                ("ex:group", groups.get(gid)), ("ex:groupId", lit(gid)),
                                ("ex:classTitle", text_lit(cls.get("title"))),
                                ("ex:categoryTitle", text_lit(cat.get("title"))),
                                ("ex:valueText", lit(x.get("value"))),
                                ("ex:value", float_lit(x.get("value"))),
                                ("ex:spread", float_lit(x.get("spread"))),
                                ("ex:lowerLimit", float_lit(x.get("lowerLimit"))),
                                ("ex:upperLimit", float_lit(x.get("upperLimit"))),
                                ("ex:comment", text_lit(x.get("comment")))])
                    w.block(M, [("ex:hasMeasurement", X)])


def _documents(w, nct, S, ld):
    """Protocol, statistical analysis plan and consent form PDFs. The URL follows
    ClinicalTrials.gov's large-document pattern and is labelled as derived."""
    if ld.get("noSap") is not None:
        w.block(S, [("ex:noStatisticalAnalysisPlan", bool_lit(ld.get("noSap")))])
    for i, d in enumerate(ld.get("largeDocs") or []):
        fn = (d.get("filename") or "").strip()
        X = iri.document(nct, i)
        url = f"https://cdn.clinicaltrials.gov/large-docs/{nct[-2:]}/{nct}/{fn}" if fn else None
        w.block(X, [("a", "ex:StudyDocument"), ("rdfs:label", text_lit(d.get("label") or fn)),
                    ("ex:documentType", lit(d.get("typeAbbrev"))),
                    ("ex:hasProtocol", bool_lit(d.get("hasProtocol"))),
                    ("ex:hasSap", bool_lit(d.get("hasSap"))),
                    ("ex:hasIcf", bool_lit(d.get("hasIcf"))),
                    ("ex:documentDate", date_lit(d.get("date"))),
                    ("ex:uploadDate", date_lit((d.get("uploadDate") or "")[:10] or None)),
                    ("ex:filename", lit(fn)), ("ex:sizeBytes", int_lit(d.get("size"))),
                    ("ex:derivedUrl", lit(url))])
        w.block(S, [("ex:hasDocument", X)])


def _annotations(w, nct, S, an):
    """Unposted-results events and FDAAA 801 violation events NLM attaches to a record."""
    up = an.get("unpostedAnnotation") or {}
    if up.get("unpostedResponsibleParty"):
        w.block(S, [("ex:unpostedResponsibleParty", text_lit(up.get("unpostedResponsibleParty")))])
    for i, ev in enumerate(up.get("unpostedEvents") or []):
        X = iri.annotation(nct, "unposted", i)
        w.block(X, [("a", "ex:UnpostedResultsEvent"), ("ex:eventType", lit(ev.get("type"))),
                    ("ex:eventDate", date_lit(ev.get("date"))),
                    ("ex:dateUnknown", bool_lit(ev.get("dateUnknown")))])
        w.block(S, [("ex:hasUnpostedEvent", X)])
    for i, ev in enumerate(_g(an, "violationAnnotation", "violationEvents") or []):
        X = iri.annotation(nct, "violation", i)
        w.block(X, [("a", "ex:ViolationEvent"), ("ex:eventType", lit(ev.get("type"))),
                    ("ex:description", text_lit(ev.get("description"))),
                    ("ex:creationDate", date_lit(ev.get("creationDate"))),
                    ("ex:issuedDate", date_lit(ev.get("issuedDate"))),
                    ("ex:releaseDate", date_lit(ev.get("releaseDate"))),
                    ("ex:postedDate", date_lit(ev.get("postedDate")))])
        w.block(S, [("ex:hasViolationEvent", X)])



def _submissions(w, nct, S, infos):
    """Results submission and quality-control cycles (release, unrelease, reset)."""
    for i, si in enumerate(infos):
        X = iri.annotation(nct, "submission", i)
        w.block(X, [("a", "ex:ResultsSubmissionCycle"),
                    ("ex:releaseDate", date_lit(si.get("releaseDate"))),
                    ("ex:unreleaseDate", date_lit(si.get("unreleaseDate"))),
                    ("ex:unreleaseDateUnknown", bool_lit(si.get("unreleaseDateUnknown"))),
                    ("ex:resetDate", date_lit(si.get("resetDate"))),
                    ("ex:qcReviewRound", int_lit(si.get("mcpReleaseN")))])
        w.block(S, [("ex:hasResultsSubmissionCycle", X)])

# ---------------------------------------------------------------------------
def _open_json(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def convert_page(in_path, out_dir, retrieved_at):
    """Convert one page file. Returns (studies, triples, link_triples, skipped)."""
    data = _open_json(in_path)
    studies = data.get("studies") if isinstance(data, dict) else data
    base = os.path.basename(in_path).split(".")[0]
    os.makedirs(out_dir, exist_ok=True)
    out_p = os.path.join(out_dir, base + ".ttl")
    link_p = os.path.join(out_dir, base + ".links.ttl")
    n = skipped = 0
    with open(out_p + ".tmp", "w", encoding="utf-8") as out, \
         open(link_p + ".tmp", "w", encoding="utf-8") as links:
        out.write(PREFIX + "\n")
        links.write(PREFIX + "\n")
        w = Writer(out, links)
        for rec in studies or []:
            try:
                if convert_study(w, rec, retrieved_at):
                    n += 1
                else:
                    skipped += 1
            except ValueError as e:
                skipped += 1
                print(f"[ct_to_rdf] skipped record in {base}: {e}", file=sys.stderr)
    os.replace(out_p + ".tmp", out_p)
    os.replace(link_p + ".tmp", link_p)
    return n, w.triples, w.link_triples, skipped


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("download_dir", help="folder with page_*.json(.gz) and manifest.json")
    ap.add_argument("out_dir")
    args = ap.parse_args(argv)
    man = _open_json(os.path.join(args.download_dir, "manifest.json"))
    retrieved_at = man["retrieved_at"]
    pages = sorted(p for p in os.listdir(args.download_dir)
                   if p.startswith("page_") and (p.endswith(".json") or p.endswith(".json.gz")))
    tot = {"studies": 0, "triples": 0, "link_triples": 0, "skipped": 0}
    for p in pages:
        n, t, lt, sk = convert_page(os.path.join(args.download_dir, p), args.out_dir, retrieved_at)
        tot["studies"] += n
        tot["triples"] += t
        tot["link_triples"] += lt
        tot["skipped"] += sk
        print(f"[ct_to_rdf] {p}: {n} studies, {t} triples, {lt} link triples")
    tot["pages"] = len(pages)
    tot["retrieved_at"] = retrieved_at
    tot["manifest_total"] = man.get("total_count")
    with open(os.path.join(args.out_dir, "convert_stats.json"), "w") as f:
        json.dump(tot, f, indent=2)
    print(json.dumps(tot, indent=2))
    if man.get("total_count") is not None and tot["studies"] + tot["skipped"] != man["total_count"]:
        print("[ct_to_rdf] ERROR: converted + skipped != manifest total", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
