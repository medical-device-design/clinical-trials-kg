#!/usr/bin/env python3
"""Synthetic ClinicalTrials.gov API v2 records for tests. Shapes follow the v2
JSON layout; all values are invented. Each record exercises a known risk."""

import gzip
import json
import os
import sys

DEVICE_WITH_RESULTS = {
    "hasResults": True,
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT09000001", "nctIdAliases": ["NCT08999999"],
            "orgStudyIdInfo": {"id": "TEST-001"},
            "secondaryIdInfos": [
                {"id": "G170123", "type": "FDA"},
                {"id": "5R01EB012345-03", "type": "NIH", "link": "https://reporter.nih.gov/x"},
                {"id": "K170999", "type": "OTHER"},           # bare K, must NOT link
                {"id": "PMA P100023/S045", "type": "OTHER", "domain": "FDA"},
            ],
            "organization": {"fullName": "Testco Medical, Inc.", "class": "INDUSTRY"},
            "briefTitle": "Test Dressing \"Alpha\" for Chronic Wounds",
            "officialTitle": "A Randomized Trial of Alpha vs. Sham",
        },
        "statusModule": {
            "overallStatus": "COMPLETED",
            "statusVerifiedDate": "2024-03",
            "startDateStruct": {"date": "2019-05", "type": "ACTUAL"},
            "primaryCompletionDateStruct": {"date": "2021-02-28", "type": "ACTUAL"},
            "completionDateStruct": {"date": "2021-06-30", "type": "ACTUAL"},
            "lastUpdatePostDateStruct": {"date": "2024-03-15", "type": "ACTUAL"},
        },
        "sponsorCollaboratorsModule": {
            "responsibleParty": {"type": "SPONSOR"},
            "leadSponsor": {"name": "Testco Medical, Inc.", "class": "INDUSTRY"},
            "collaborators": [{"name": "Hofstra University", "class": "OTHER"}],
        },
        "oversightModule": {"oversightHasDmc": True, "isFdaRegulatedDevice": True,
                            "isFdaRegulatedDrug": False},
        "descriptionModule": {
            "briefSummary": "Questions: write to study.lead@testco.example.com.\nLine two.",
            "detailedDescription": "X" * 50000,           # long text, must not be cut
        },
        "conditionsModule": {"conditions": ["Diabetic Foot Ulcer", "Wound Healing"],
                             "keywords": ["keratin", "dressing"]},
        "designModule": {
            "studyType": "INTERVENTIONAL", "phases": ["NA"],
            "designInfo": {"allocation": "RANDOMIZED", "interventionModel": "PARALLEL",
                           "primaryPurpose": "TREATMENT",
                           "maskingInfo": {"masking": "DOUBLE", "whoMasked": ["PARTICIPANT", "OUTCOMES_ASSESSOR"]}},
            "enrollmentInfo": {"count": 120, "type": "ACTUAL"},
        },
        "armsInterventionsModule": {
            "armGroups": [
                {"label": "Alpha", "type": "EXPERIMENTAL", "interventionNames": ["Device: Alpha dressing"]},
                {"label": "Sham", "type": "SHAM_COMPARATOR", "interventionNames": ["Device: Sham device"]},
            ],
            "interventions": [
                {"type": "DEVICE", "name": "Alpha dressing", "otherNames": ["ALPHA-1"],
                 "armGroupLabels": ["Alpha"]},
                {"type": "DEVICE", "name": "Sham device", "armGroupLabels": ["Sham"]},
            ],
        },
        "outcomesModule": {
            "primaryOutcomes": [{"measure": "Complete wound closure", "timeFrame": "12 weeks"}],
            "secondaryOutcomes": [{"measure": "Time to closure", "timeFrame": "12 weeks"}],
        },
        "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria:\n* Adults\n\nExclusion Criteria:\n* Infection",
                              "healthyVolunteers": False, "sex": "ALL", "minimumAge": "18 Years",
                              "stdAges": ["ADULT", "OLDER_ADULT"]},
        "contactsLocationsModule": {
            "centralContacts": [{"name": "Pat Contact", "role": "CONTACT",
                                 "phone": "555-0100", "email": "pat@testco.example.com"}],
            "overallOfficials": [{"name": "Jane Doe, MD", "affiliation": "Testco Medical",
                                  "role": "PRINCIPAL_INVESTIGATOR"},
                                 {"name": "Sam Roe sam.roe@uni.example.edu", "affiliation": "sam.roe@uni.example.edu",
                                  "role": "STUDY_DIRECTOR"}],
            "locations": [
                {"facility": "Hempstead Clinic", "city": "Hempstead", "state": "New York",
                 "zip": "11549", "country": "United States",
                 "geoPoint": {"lat": 40.7062, "lon": -73.6187},
                 "contacts": [{"name": "Site Person", "email": "site@clinic.example.org"}]},
            ],
        },
        "referencesModule": {"references": [
            {"pmid": "31234567", "type": "RESULT", "citation": "Doe J. Alpha trial. J Wound. 2022.",
             "retractions": [{"pmid": "39999999", "source": "J Wound. 2023"}]},
            {"type": "BACKGROUND", "citation": "Book chapter without PMID."},
        ], "seeAlsoLinks": [{"label": "Sponsor page", "url": "https://testco.example.com/alpha"},
                           {"label": "Write to us", "url": "mailto:info@testco.example.com"}]},
    },
    "resultsSection": {
        "outcomeMeasuresModule": {"outcomeMeasures": [{
            "type": "PRIMARY", "title": "Complete wound closure",
            "paramType": "COUNT_OF_PARTICIPANTS", "unitOfMeasure": "Participants",
            "timeFrame": "12 weeks", "reportingStatus": "POSTED",
            "groups": [{"id": "OG000", "title": "Alpha"}, {"id": "OG001", "title": "Sham"}],
            "denoms": [{"units": "Participants",
                        "counts": [{"groupId": "OG000", "value": "60"}, {"groupId": "OG001", "value": "60"}]}],
            "classes": [{"categories": [{"measurements": [
                {"groupId": "OG000", "value": "33"},
                {"groupId": "OG001", "value": "NA", "comment": "Not estimable"},
            ]}]}],
            "analyses": [{"groupIds": ["OG000", "OG001"], "pValue": "<0.001",
                          "statisticalMethod": "Chi-squared", "paramType": "Risk Ratio (RR)",
                          "paramValue": "2500000", "ciPctValue": "95",
                          "ciLowerLimit": "1.2", "ciUpperLimit": "3.4"}],
        }]},
        "adverseEventsModule": {
            "frequencyThreshold": "5", "timeFrame": "12 weeks",
            "eventGroups": [
                {"id": "EG000", "title": "Alpha", "seriousNumAffected": 2, "seriousNumAtRisk": 60,
                 "deathsNumAffected": 0, "deathsNumAtRisk": 60},
                {"id": "EG001", "title": "Sham", "seriousNumAffected": 3, "seriousNumAtRisk": 60},
            ],
            "seriousEvents": [{"term": "Cellulitis", "organSystem": "Infections and infestations",
                               "sourceVocabulary": "MedDRA 24.0", "assessmentType": "SYSTEMATIC_ASSESSMENT",
                               "stats": [{"groupId": "EG000", "numEvents": 1, "numAffected": 1, "numAtRisk": 60},
                                         {"groupId": "EG001", "numEvents": 2, "numAffected": 2, "numAtRisk": 60}]}],
            "otherEvents": [{"term": "Pruritus", "organSystem": "Skin",
                             "stats": [{"groupId": "EG000", "numAffected": 4, "numAtRisk": 60}]}],
        },
        "participantFlowModule": {
            "recruitmentDetails": "Recruited at one clinic.",
            "groups": [{"id": "FG000", "title": "Alpha"}, {"id": "FG001", "title": "Sham"}],
            "periods": [{"title": "Overall Study",
                         "milestones": [{"type": "STARTED", "achievements": [
                             {"groupId": "FG000", "numSubjects": "60"}, {"groupId": "FG001", "numSubjects": "60"}]},
                                        {"type": "COMPLETED", "achievements": [
                             {"groupId": "FG000", "numSubjects": "55"}, {"groupId": "FG001", "numSubjects": "57"}]}],
                         "dropWithdraws": [{"type": "Lost to Follow-up", "reasons": [
                             {"groupId": "FG000", "numSubjects": "5"}, {"groupId": "FG001", "numSubjects": "3"}]}]}],
        },
        "baselineCharacteristicsModule": {
            "groups": [{"id": "BG000", "title": "Alpha"}, {"id": "BG001", "title": "Total"}],
            "denoms": [{"units": "Participants", "counts": [{"groupId": "BG000", "value": "60"},
                                                            {"groupId": "BG001", "value": "120"}]}],
            "measures": [{"title": "Age, Continuous", "paramType": "MEAN", "dispersionType": "STANDARD_DEVIATION",
                          "unitOfMeasure": "years", "classes": [{"categories": [{"measurements": [
                              {"groupId": "BG000", "value": "61.2", "spread": "9.1"},
                              {"groupId": "BG001", "value": "60.8", "spread": "9.4"}]}]}]}],
        },
        "moreInfoModule": {"pointOfContact": {"title": "Dr. Contact", "organization": "Testco Medical",
                                              "email": "poc@testco.example.com", "phone": "555-0199"}},
    },
    "documentSection": {"largeDocumentModule": {"largeDocs": [
        {"typeAbbrev": "Prot_SAP", "hasProtocol": True, "hasSap": True, "hasIcf": False,
         "label": "Study Protocol and Statistical Analysis Plan", "date": "2019-01-10",
         "uploadDate": "2021-07-01T12:54", "filename": "Prot_SAP_000.pdf", "size": 989192}]}},
    "annotationSection": {"annotationModule": {"unpostedAnnotation": {
        "unpostedResponsibleParty": "Testco Medical",
        "unpostedEvents": [{"type": "RESET", "date": "2022-01-05"}]}}},
    "derivedSection": {
        "miscInfoModule": {"versionHolder": "2026-11-20",
                           "submissionTracking": {"submissionInfos": [{"releaseDate": "2021-07-01", "resetDate": "2021-08-01", "mcpReleaseN": 1}]}},
        "conditionBrowseModule": {"meshes": [{"id": "D017719", "term": "Diabetic Foot"}]},
        "interventionBrowseModule": {"meshes": []},
    },
}

DRUG_NO_RESULTS = {
    "hasResults": False,
    "protocolSection": {
        "identificationModule": {"nctId": "NCT09000002", "briefTitle": "Drug Study",
                                 "secondaryIdInfos": [{"id": "IND 123456", "type": "OTHER"}]},
        "statusModule": {"overallStatus": "RECRUITING",
                         "startDateStruct": {"date": "2025", "type": "ESTIMATED"}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "MEDTRONIC INC", "class": "INDUSTRY"}},
        "conditionsModule": {"conditions": ["Diabetic Foot Ulcer"]},   # same condition text again
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE2", "PHASE3"]},
        "armsInterventionsModule": {"interventions": [{"type": "DEVICE", "name": "Sham device"}]},
    },
}

OBSERVATIONAL_SPARSE = {
    "hasResults": False,
    "protocolSection": {
        "identificationModule": {"nctId": "NCT09000003", "briefTitle": "Registry"},
        "statusModule": {"overallStatus": "UNKNOWN"},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Medtronic, Inc.", "class": "INDUSTRY"}},
        "designModule": {"studyType": "OBSERVATIONAL"},
    },
}

BAD_RECORD = {"protocolSection": {"identificationModule": {"nctId": "NOT-AN-NCT"}}}


def write(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    pages = [[DEVICE_WITH_RESULTS, DRUG_NO_RESULTS], [OBSERVATIONAL_SPARSE, BAD_RECORD]]
    man = {"retrieved_at": "2026-11-20", "total_count": 4, "pages": []}
    for i, studies in enumerate(pages, 1):
        name = f"page_{i:05d}.json.gz"
        with gzip.open(os.path.join(out_dir, name), "wt", encoding="utf-8") as f:
            json.dump({"studies": studies}, f)
        man["pages"].append({"file": name, "studies": len(studies)})
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(man, f, indent=2)


if __name__ == "__main__":
    write(sys.argv[1])
