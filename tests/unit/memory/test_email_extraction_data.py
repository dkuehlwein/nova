"""
Unit Tests for Email Extraction Test Data

These tests validate that our expected extractions are well-formed.
They don't test actual extraction - just that our test data is valid.

No external dependencies required (no Neo4j, no LLM).

Run with: cd backend && uv run pytest ../tests/unit/memory/test_email_extraction_data.py -v
"""

import pytest

from tests.fixtures.memory_test_data import ExpectedExtractions


class TestExpectedExtractionsDocumentation:
    """
    Unit tests that validate our expected extractions are well-formed.
    These don't test actual extraction, just that our test data is valid.
    """

    def test_all_persons_have_names(self):
        """Every person in hard facts must have a name (schema:name)."""
        for person in ExpectedExtractions.HARD_FACTS["persons"]:
            assert person.get("name"), f"Person missing name: {person}"

    def test_all_persons_with_email_have_valid_format(self):
        """Email addresses should look valid (schema:email)."""
        for person in ExpectedExtractions.HARD_FACTS["persons"]:
            email = person.get("email")
            if email:
                assert "@" in email, f"Invalid email for {person['name']}: {email}"

    def test_identifier_is_documented(self):
        """The main identifier (MTG code) should be documented."""
        identifiers = ExpectedExtractions.HARD_FACTS["identifiers"]
        assert any(i["value"] == "740020199" for i in identifiers)

    def test_course_and_instance_are_separate(self):
        """Course (program) and CourseInstance (offering) should be separate."""
        courses = ExpectedExtractions.HARD_FACTS["courses"]
        instances = ExpectedExtractions.HARD_FACTS["course_instances"]

        assert len(courses) > 0, "Expected at least one Course"
        assert len(instances) > 0, "Expected at least one CourseInstance"

        # Instance should reference the course
        for instance in instances:
            assert instance.get("course_name"), f"CourseInstance missing course_name: {instance}"

    def test_inference_has_evidence(self):
        """Every inference should have supporting evidence."""
        for role in ExpectedExtractions.REASONABLE_INFERENCES["inferred_roles"]:
            assert role.get("evidence"), f"Missing evidence for {role['person']}"

        for edge in ExpectedExtractions.REASONABLE_INFERENCES["inferred_edges"]:
            assert edge.get("evidence"), f"Missing evidence for edge: {edge}"

    def test_assumptions_have_confidence(self):
        """Every assumption should have a confidence level."""
        for assumption in ExpectedExtractions.ASSUMPTIONS["hierarchy_assumptions"]:
            assert assumption.get("confidence") in ["low", "medium", "high"], \
                f"Invalid confidence for: {assumption}"

    def test_expected_edges_have_source_and_target(self):
        """All expected edges should have source and target."""
        for edge_type, edges in ExpectedExtractions.EXPECTED_EDGES.items():
            for edge in edges:
                assert "source" in edge, f"Edge missing source in {edge_type}: {edge}"
                assert "target" in edge, f"Edge missing target in {edge_type}: {edge}"

    def test_ontology_uses_schema_org_types(self):
        """Verify we're using schema.org aligned type names."""
        # Check that we use "persons" not "people"
        assert "persons" in ExpectedExtractions.HARD_FACTS
        # Check that we use "organizations" not "companies"
        assert "organizations" in ExpectedExtractions.HARD_FACTS
        # Check that we have Course and CourseInstance
        assert "courses" in ExpectedExtractions.HARD_FACTS
        assert "course_instances" in ExpectedExtractions.HARD_FACTS
        # Check that we use "identifiers" not "project_codes"
        assert "identifiers" in ExpectedExtractions.HARD_FACTS
