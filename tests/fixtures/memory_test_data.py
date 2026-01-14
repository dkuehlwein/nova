"""
Shared Test Data for Memory Extraction Tests

This module contains test data and expected extractions used by both
unit tests (tests/unit/memory/) and integration tests (tests/integration/memory/).

Ontology aligned with schema.org for semantic clarity:
- https://schema.org/Person
- https://schema.org/Organization
- https://schema.org/Course / https://schema.org/CourseInstance
- https://schema.org/Event
- https://schema.org/EmailMessage

See backend/memory/entity_types.py for full ontology documentation.
"""

from typing import Dict, List, Any, Set


# =============================================================================
# TEST DATA: German Corporate Email Thread
# =============================================================================

EMAIL_THREAD_PROJECT_CODE = """
Hallo Anna,

bitte entschuldige die späte Rückmeldung. Ich habe auf einen Termin mit Sabine gewartet, in den ich deine Frage mitnehmen konnte. Da der Termin leider geschoben wurde, kann ich dir erst just jetzt antworten:
Es ist der MTG code: 740020199

Herzliche Grüße
Lisa

From: Müller, Anna anna.mueller@nextera-consulting.com
Sent: Montag, 12. Januar 2026 13:08
To: Schmidt, Maria maria.schmidt@nextera-consulting.com; Weber, Lisa lisa.weber@nextera-consulting.com
Cc: Hoffmann, Thomas thomas.hoffmann@nextera-consulting.com; DL DE Cloud Services Management cloudservices.management@nextera-consulting.com
Subject: Wichtig: Project Code für interne Kosten benötigt für Cloud Engineering Bootcamp 1 2026

Hallo Lisa, hallo Maria,

Ich hatte letzte Woche schon Kontakt mit Lisa aufgenommen und um den Projektcode gebeten, mit dem interne Bestellungen getätigt werden können.

Thomas Hoffmann strebt an, nächste Woche für 2 Wochen das Cloud Engineering Bootcamp 1 für 2026 zu starten. Dafür ist jedoch Voraussetzung, dass alle Teilnehmer eine 1-Monats-Lizenz von Copilot für Git haben.
Thomas hat letztes Jahr bereits eine Genehmigung für 500€ Budget für Copilot-Lizenzen von Charlotte bekommen.

Da die Beantragung und Bereitstellung i.d.R. ein paar Tage dauern, bräuchten wir den Project Code tatsächlich dringend, sonst muss das Bootcamp verschoben werden!

Vielen Dank,

Anna

Anna Müller
Senior Cloud Solutions Architect & Team Lead | Cloud & Infrastructure

Nextera Consulting | Frankfurt, Germany
Mob.: +49 166 98 76 123
www.nextera-consulting.com/de
"""

EMAIL_METADATA_PROJECT_CODE = {
    "id": "test_email_project_code_001",
    "subject": "Re: Wichtig: Project Code für interne Kosten benötigt für Cloud Engineering Bootcamp 1 2026",
    "from": "lisa.weber@nextera-consulting.com",
    "to": "anna.mueller@nextera-consulting.com, maria.schmidt@nextera-consulting.com",
    "cc": "thomas.hoffmann@nextera-consulting.com, cloudservices.management@nextera-consulting.com",
    "date": "2026-01-13T10:30:00+01:00",
    "thread_id": "thread_bootcamp_projectcode_001",
}


# =============================================================================
# EXPECTED EXTRACTIONS - Schema.org Aligned Ontology
# =============================================================================

class ExpectedExtractions:
    """
    Documents what should be extracted from the email thread.
    Organized by confidence level.

    Entity types follow schema.org vocabulary:
    - Person: https://schema.org/Person
    - Organization: https://schema.org/Organization
    - Course: https://schema.org/Course (training program definition)
    - CourseInstance: https://schema.org/CourseInstance (specific offering)
    - Identifier: Custom type for project codes, booking codes
    - EmailMessage: https://schema.org/EmailMessage

    Edge types follow schema.org properties where possible:
    - WORKS_FOR: schema:worksFor
    - REPORTS_TO: org:reportsTo (W3C ORG vocabulary)
    - ORGANIZED_BY: schema:organizer
    - FUNDED_BY: schema:funder
    - IDENTIFIES: Custom (Identifier → Project/Course)
    """

    # -------------------------------------------------------------------------
    # HARD FACTS - Explicitly stated, MUST extract
    # -------------------------------------------------------------------------

    HARD_FACTS = {
        # Identifiers (custom type for business codes)
        # Schema.org has identifier as a property, not a type
        "identifiers": [
            {
                "value": "740020199",
                "identifier_type": "mtg_code",
                "description": "Internal orders/booking code for project costs",
            }
        ],

        # Persons (schema:Person)
        # https://schema.org/Person
        "persons": [
            {
                "name": "Lisa Weber",
                "email": "lisa.weber@nextera-consulting.com",
                "job_title": None,  # Not explicitly stated
            },
            {
                "name": "Anna Müller",
                "email": "anna.mueller@nextera-consulting.com",
                "job_title": "Senior Cloud Solutions Architect & Team Lead | Cloud & Infrastructure",
                "telephone": "+49 166 98 76 123",
            },
            {
                "name": "Maria Schmidt",
                "email": "maria.schmidt@nextera-consulting.com",
                "job_title": None,
            },
            {
                "name": "Thomas Hoffmann",
                "email": "thomas.hoffmann@nextera-consulting.com",
                "job_title": None,  # "Leading bootcamp" is a role, not job title
            },
            {
                "name": "Charlotte",
                "email": None,  # Not provided
                "job_title": None,  # Budget approver implied but not stated
            },
            {
                "name": "Sabine",
                "email": None,
                "job_title": None,
            },
        ],

        # Organizations (schema:Organization)
        # https://schema.org/Organization
        "organizations": [
            {
                "name": "Nextera Consulting",
                "organization_type": "company",
                "url": "www.nextera-consulting.com/de",
                "description": "Consulting company, Frankfurt, Germany",
            },
            {
                "name": "DL DE Cloud Services Management",
                "organization_type": "team",  # Distribution list = team/group
                "email": "cloudservices.management@nextera-consulting.com",
            },
        ],

        # Course (schema:Course) - The training program itself
        # https://schema.org/Course
        "courses": [
            {
                "name": "Cloud Engineering Bootcamp",
                "course_code": None,  # Not a course catalog code
                "provider": "Nextera Consulting",  # Inferred
                "duration": "2 weeks",
                "description": "Internal cloud engineering training program",
            }
        ],

        # CourseInstance (schema:CourseInstance) - Specific offering
        # https://schema.org/CourseInstance
        "course_instances": [
            {
                "name": "Cloud Engineering Bootcamp 1 2026",
                "course_name": "Cloud Engineering Bootcamp",
                "start_date": "2026-01-19",  # "next week" from Jan 12, 2026
                "end_date": "2026-01-30",  # 2 weeks duration
                "location": None,  # Not specified
                "course_mode": "onsite",  # Implied by need for licenses
            }
        ],

        # Budget/Financial information (no direct schema.org type)
        "financial": [
            {
                "amount": "500",
                "currency": "EUR",
                "purpose": "Copilot licenses",
                "approved_by": "Charlotte",
                "approved_when": "2025",  # "last year" relative to Jan 2026
            }
        ],

        # Products/Services mentioned
        "products": [
            {
                "name": "Copilot for Git",
                "license_duration": "1 month",
            }
        ],

        # Process facts (domain knowledge)
        "process_facts": [
            "License provisioning takes 'a few days' lead time",
            "Internal orders require a project code (MTG code)",
        ],
    }

    # -------------------------------------------------------------------------
    # EXPECTED EDGES - Relationships to extract
    # -------------------------------------------------------------------------

    EXPECTED_EDGES = {
        # Person → Organization (schema:worksFor)
        "works_for": [
            {"source": "Lisa Weber", "target": "Nextera Consulting"},
            {"source": "Anna Müller", "target": "Nextera Consulting"},
            {"source": "Maria Schmidt", "target": "Nextera Consulting"},
            {"source": "Thomas Hoffmann", "target": "Nextera Consulting"},
        ],

        # Person → Organization (schema:memberOf)
        "member_of": [
            {"source": "Lisa Weber", "target": "DL DE Cloud Services Management"},
            {"source": "Maria Schmidt", "target": "DL DE Cloud Services Management"},
        ],

        # Course → Organization (schema:provider / custom: ORGANIZED_BY)
        "organized_by": [
            {"source": "Cloud Engineering Bootcamp", "target": "Nextera Consulting"},
        ],

        # CourseInstance → Course (schema:hasCourseInstance inverse)
        "instance_of": [
            {"source": "Cloud Engineering Bootcamp 1 2026", "target": "Cloud Engineering Bootcamp"},
        ],

        # Identifier → CourseInstance (custom: IDENTIFIES)
        "identifies": [
            {"source": "740020199", "target": "Cloud Engineering Bootcamp 1 2026"},
        ],

        # Person → CourseInstance (custom role - leading/coordinating)
        "leads": [
            {"source": "Thomas Hoffmann", "target": "Cloud Engineering Bootcamp 1 2026"},
        ],

        # Person → Person (schema:funder - budget approval)
        "approved_budget_for": [
            {"source": "Charlotte", "target": "Thomas Hoffmann", "context": "500 EUR for Copilot licenses"},
        ],

        # EmailMessage → Person (schema:sender, schema:recipient)
        "email_sent_by": [
            {"source": "EMAIL_METADATA_PROJECT_CODE", "target": "Lisa Weber"},
        ],
        "email_sent_to": [
            {"source": "EMAIL_METADATA_PROJECT_CODE", "target": "Anna Müller"},
            {"source": "EMAIL_METADATA_PROJECT_CODE", "target": "Maria Schmidt"},
        ],
    }

    # -------------------------------------------------------------------------
    # REASONABLE INFERENCES - Strongly implied, SHOULD extract
    # -------------------------------------------------------------------------

    REASONABLE_INFERENCES = {
        # Inferred roles based on behavior
        "inferred_roles": [
            {
                "person": "Lisa Weber",
                "inferred_job_function": "Finance/Operations",
                "evidence": "Provides project codes, consulted Sabine for approval",
                "edge_type": "WORKS_IN_FUNCTION",
            },
            {
                "person": "Sabine",
                "inferred_job_function": "Lisa's approver/superior",
                "evidence": "Lisa waited for meeting with Sabine to get the answer",
                "edge_type": "REPORTS_TO",
            },
            {
                "person": "Maria Schmidt",
                "inferred_job_function": "Finance/Operations (same team as Lisa)",
                "evidence": "Contacted alongside Lisa for project codes",
                "edge_type": "COLLEAGUE_OF",
            },
            {
                "person": "Thomas Hoffmann",
                "inferred_job_function": "Training/initiative leader",
                "evidence": "Leading bootcamp, got budget approval",
                "edge_type": None,  # Role, not permanent position
            },
        ],

        # Inferred relationships (edges)
        "inferred_edges": [
            {
                "source": "Anna Müller",
                "target": "Thomas Hoffmann",
                "edge_type": "SUPPORTS",  # Custom
                "evidence": "Anna executing requests for Thomas's initiative",
            },
            {
                "source": "Lisa Weber",
                "target": "Sabine",
                "edge_type": "REPORTS_TO",  # org:reportsTo
                "evidence": "Lisa waited for Sabine meeting to answer",
            },
            {
                "source": "Lisa Weber",
                "target": "Maria Schmidt",
                "edge_type": "COLLEAGUE_OF",  # schema:colleague
                "evidence": "Both handle project code requests",
            },
        ],

        # Process knowledge
        "process_knowledge": [
            "Budget approval (Charlotte) is separate from project code assignment (Lisa/Sabine)",
            "Project codes follow 'MTG' format prefix",
            "Multiple approvers may be needed: budget vs. operational codes",
        ],
    }

    # -------------------------------------------------------------------------
    # ASSUMPTIONS - Plausible but speculative, MAYBE extract with low confidence
    # -------------------------------------------------------------------------

    ASSUMPTIONS = {
        "hierarchy_assumptions": [
            {
                "assumption": "Charlotte is senior leadership",
                "confidence": "medium",
                "evidence": "Has budget authority for 500 EUR",
                "would_create_edge": ("Charlotte", "SENIOR_TO", "Thomas Hoffmann"),
            },
            {
                "assumption": "Thomas Hoffmann manages Anna Müller",
                "confidence": "low",
                "evidence": "He's leading initiative, she's executing - but could be project role only",
                "would_create_edge": ("Thomas Hoffmann", "MANAGES", "Anna Müller"),
            },
            {
                "assumption": "Sabine is in Finance/Ops management",
                "confidence": "medium",
                "evidence": "Approves project code requests that Lisa handles",
                "would_create_edge": ("Sabine", "MANAGES", "Lisa Weber"),
            },
        ],

        "organizational_assumptions": [
            {
                "assumption": "Cloud Services Management DL is shared mailbox for ops/finance team",
                "confidence": "medium",
                "evidence": "Named 'DL DE Cloud Services Management', handles project codes",
            },
            {
                "assumption": "Cloud & Infrastructure is a department within Nextera",
                "confidence": "high",
                "evidence": "Part of Anna's title structure",
                "would_create_edge": ("Cloud & Infrastructure", "SUB_ORGANIZATION", "Nextera Consulting"),
            },
        ],
    }

    # -------------------------------------------------------------------------
    # CONTEXTUAL KNOWLEDGE - Patterns useful to remember
    # -------------------------------------------------------------------------

    CONTEXTUAL_KNOWLEDGE = {
        "identifier_patterns": [
            {
                "identifier_type": "mtg_code",
                "pattern": r"\d{9}",
                "example": "740020199",
                "purpose": "Internal project/cost tracking",
            },
        ],

        "process_timelines": [
            {"process": "License provisioning", "typical_duration": "a few days"},
            {"process": "Budget approval to execution", "typical_duration": "variable"},
        ],

        "approval_chains": [
            {"approval_type": "Budget", "approver_role": "Senior leadership (Charlotte)"},
            {"approval_type": "Project codes", "approver_role": "Finance/Ops (Sabine via Lisa)"},
        ],

        "email_patterns": [
            {"domain": "nextera-consulting.com", "format": "firstname.lastname@domain"},
            {"distribution_list_prefix": "DL DE", "purpose": "German distribution lists"},
        ],
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_entity_names(entities: List[Dict[str, Any]], label: str) -> Set[str]:
    """Extract names of entities with a specific label."""
    return {
        e["name"] for e in entities
        if label in e.get("labels", [])
    }


def find_facts_mentioning(facts: List[Dict[str, Any]], keyword: str) -> List[str]:
    """Find all facts that mention a keyword."""
    return [
        f["fact"] for f in facts
        if keyword.lower() in f["fact"].lower()
    ]


def check_edge_exists(facts: List[Dict[str, Any]], source: str, target: str) -> bool:
    """Check if any fact mentions both source and target entities."""
    for fact in facts:
        fact_text = fact.get("fact", "").lower()
        if source.lower() in fact_text and target.lower() in fact_text:
            return True
    return False
