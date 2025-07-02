# Nova: High-Level Integration Tests

## Philosophy

These tests validate complete, real-world user scenarios from end-to-end. They interact with the Nova system as a black box through its public-facing APIs. The goal is to ensure key user workflows function correctly across multiple integrated services.

## Setup & Teardown

All tests run against a live, containerized instance of the Nova ecosystem.

1. Start the System:
From the project root, run the test environment compose file. This brings up the entire stack in a clean state.
```bash
docker-compose -f docker-compose.test.yml up --build -d
```

2. Run the Tests:
Use pytest to run the test suite.
```bash      
pytest backend/uv run pytest ../tests/integration/
```

3. Tear Down the System:
After tests are complete, the environment must be torn down to delete all test-generated data.
```bash      
docker-compose -f docker-compose.test.yml down -v
```

## Writing a New Test

Each integration test is a single Python file (test_*.py) that contains both the specification and the implementation.

### Test File Structure

Every test file must begin with a module-level docstring that describes the test case in a structured format. This serves as our official test description.

The structure is as follows:
Generated python
      
"""
Test ID: TC_[Domain]_[ID]
Use Case: [A short, one-sentence description of the user's goal.]
Tags: [domain], [feature], [priority]

Given (The Pre-conditions):
- Describes the state of the system BEFORE the test runs.
- Each condition is a separate bullet point.

When (The Action):
- Describes the single trigger or event that initiates the test.

Then (The Expected Outcome):
- Describes the state of the system AFTER the action is complete.
- Each verifiable outcome is a separate bullet point.
"""

# ... pytest code follows ...

    