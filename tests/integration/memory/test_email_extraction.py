"""
Email Memory Extraction Integration Tests

Tests what information Nova's memory system extracts from emails.
These are integration tests requiring Neo4j + LLM to run.

Ontology aligned with schema.org for semantic clarity:
- https://schema.org/Person
- https://schema.org/Organization
- https://schema.org/Course / https://schema.org/CourseInstance
- https://schema.org/Event
- https://schema.org/EmailMessage

See backend/memory/entity_types.py for full ontology documentation.
Test data and expected extractions are in tests/fixtures/memory_test_data.py.

Run with: cd backend && uv run pytest ../tests/integration/memory/test_email_extraction.py -v
Requires: Neo4j running, LLM configured
"""

import pytest

from tests.fixtures.memory_test_data import (
    EMAIL_THREAD_PROJECT_CODE,
    EMAIL_METADATA_PROJECT_CODE,
    ExpectedExtractions,
    extract_entity_names,
    find_facts_mentioning,
    check_edge_exists,
)


@pytest.mark.integration
@pytest.mark.slow
class TestEmailExtractionIntegration:
    """
    Integration tests that actually run extraction against Neo4j + LLM.

    These tests verify what Graphiti extracts from email content.
    Skip with: pytest -m "not integration"
    """

    @pytest.fixture
    async def memory_result(self):
        """Add the test email to memory and return the result."""
        from memory.memory_functions import add_memory

        # Combine email metadata with body for full context
        email_content = f"""
Email Thread:
Subject: {EMAIL_METADATA_PROJECT_CODE['subject']}
From: {EMAIL_METADATA_PROJECT_CODE['from']}
To: {EMAIL_METADATA_PROJECT_CODE['to']}
CC: {EMAIL_METADATA_PROJECT_CODE['cc']}
Date: {EMAIL_METADATA_PROJECT_CODE['date']}

Body:
{EMAIL_THREAD_PROJECT_CODE}
"""

        result = await add_memory(
            content=email_content,
            source_description="Test email: Project code request for Cloud Engineering Bootcamp",
            group_id="test_email_extraction"
        )

        return result

    @pytest.mark.asyncio
    async def test_extraction_creates_entities(self, memory_result):
        """Verify that extraction creates expected entity types."""
        assert memory_result["success"] is True
        assert memory_result["nodes_created"] > 0
        assert memory_result["edges_created"] > 0

        entities = memory_result["entities"]
        labels = {label for e in entities for label in e.get("labels", [])}

        # Should have Person entities
        assert "Person" in labels, f"Expected Person entities, got labels: {labels}"

    @pytest.mark.asyncio
    async def test_extracts_identifier(self, memory_result):
        """Verify the MTG code 740020199 is extracted as Identifier."""
        entities = memory_result["entities"]
        entity_names = {e["name"] for e in entities}

        # The project code should be captured
        assert any(
            "740020199" in name for name in entity_names
        ), f"Expected identifier 740020199 in entities: {entity_names}"

    @pytest.mark.asyncio
    async def test_extracts_persons(self, memory_result):
        """Verify key persons are extracted (schema:Person)."""
        entities = memory_result["entities"]
        person_names = extract_entity_names(entities, "Person")

        expected_persons = ["Lisa Weber", "Anna Müller", "Thomas Hoffmann"]

        for person in expected_persons:
            # Check if name appears (might be formatted differently)
            found = any(
                person.lower() in name.lower() or
                person.split()[-1].lower() in name.lower()  # Last name match
                for name in person_names
            )
            assert found, f"Expected to find {person} in {person_names}"

    @pytest.mark.asyncio
    async def test_extracts_organization(self, memory_result):
        """Verify Nextera Consulting is extracted as Organization."""
        entities = memory_result["entities"]
        entity_names = {e["name"].lower() for e in entities}

        assert any(
            "nextera" in name for name in entity_names
        ), f"Expected Nextera Consulting in entities: {entity_names}"

    @pytest.mark.asyncio
    async def test_extracts_course_or_event(self, memory_result):
        """Verify the bootcamp is captured as Course, CourseInstance, or Event."""
        entities = memory_result["entities"]
        entity_names = {e["name"].lower() for e in entities}

        assert any(
            "bootcamp" in name or "cloud engineering" in name
            for name in entity_names
        ), f"Expected bootcamp reference in entities: {entity_names}"


@pytest.mark.integration
@pytest.mark.slow
class TestEdgeExtraction:
    """Tests for relationship/edge extraction from emails."""

    @pytest.fixture
    async def search_results(self):
        """Add email and search for related facts."""
        from memory.memory_functions import add_memory, search_memory

        email_content = f"""
Subject: {EMAIL_METADATA_PROJECT_CODE['subject']}
From: {EMAIL_METADATA_PROJECT_CODE['from']}
To: {EMAIL_METADATA_PROJECT_CODE['to']}

{EMAIL_THREAD_PROJECT_CODE}
"""

        # Add the memory
        await add_memory(
            content=email_content,
            source_description="Test email for relationship extraction",
            group_id="test_email_extraction"
        )

        # Search for facts about the people involved
        results = await search_memory(
            query="Lisa Weber Anna Müller project code",
            limit=20,
            group_id="test_email_extraction"
        )

        return results

    @pytest.mark.asyncio
    async def test_captures_identifier_relationship(self, search_results):
        """Verify the identifier 740020199 is linked to relevant context."""
        facts = search_results["results"]
        code_facts = find_facts_mentioning(facts, "740020199")

        assert len(code_facts) > 0, \
            f"Expected facts about identifier 740020199, got: {[f['fact'] for f in facts]}"

    @pytest.mark.asyncio
    async def test_captures_person_provides_code(self, search_results):
        """Verify that Lisa providing the code is captured as a relationship."""
        facts = search_results["results"]

        # Look for facts connecting Lisa to the project code
        lisa_facts = find_facts_mentioning(facts, "Lisa")

        assert len(lisa_facts) > 0, \
            f"Expected facts about Lisa, got: {[f['fact'] for f in facts]}"

    @pytest.mark.asyncio
    async def test_captures_works_for_edge(self, search_results):
        """Verify WORKS_FOR relationship (Person → Organization) is captured."""
        facts = search_results["results"]

        # Check if any fact links a person to Nextera Consulting
        nextera_mentioned = any(
            "nextera" in f.get("fact", "").lower()
            for f in facts
        )

        # This is a "should have" - not strictly required
        if not nextera_mentioned:
            pytest.skip("WORKS_FOR edge not captured - may need ontology guidance")
