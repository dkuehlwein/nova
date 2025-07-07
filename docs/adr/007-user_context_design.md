# User Context Configuration – MVP Design

## 1. Problem Statement
Nova currently lacks an authoritative profile for the human interacting in chat.  
Without basic facts such as the user's full name, email address, or timezone, Nova cannot:
- Correctly interpret references like "me", "my email", or "send it at 9 AM my time".
- Match information in its memory store (which may be indexed by name or email) to the correct person.
- Embed personal context in the system prompt, reducing response relevance and personalization.

## 2. Scope & Assumptions (MVP)
1. **Single-user system** – one admin operates Nova.  
2. **Required fields** – full name, primary email, timezone.  
3. **Optional free-text** – arbitrary notes the user wants the system to know.  
4. **No database changes** – configuration stored in a YAML file, editable via UI.  
5. **Security** – PII is acceptable for this personal agent; no additional safeguards in MVP.

## 3. Persistence Strategy
- **File**: `configs/user_profile.yaml` (new).  
- **Format**:
  ```yaml
  full_name: "Ada Lovelace"
  email: "ada@example.com"
  timezone: "Europe/London"
  notes: |
    Prefers concise status updates.
    Enjoys historical anecdotes.
  ```
- **Editing**: surfaced in a new "User Settings" tab (mirrors existing System Prompt settings UI).  
- **Loading**: extend `utils/config_loader.py` to read this YAML and expose a `UserProfile` dataclass / Pydantic model.

## 4. Prompt Integration
- Add a new **User Context** block to `NOVA_SYSTEM_PROMPT.md`, populated dynamically:
  ```md
  **User Context:**
  - Name: {{user.full_name}}
  - Email: {{user.email}}
  - Timezone: {{user.timezone}}
  {{user.notes}}
  ```
- `prompt_loader.py` renders the template with the loaded profile before feeding it to the LLM.

## 5. UI / Settings
- **Frontend**: new "Settings → User" page with a simple form (name, email, timezone dropdown, free-text).  
- **Backend**: add API endpoints mirroring `config_endpoints.py` pattern for reading/writing `user_profile.yaml`.

## 6. Runtime Usage
- Chat agent receives the `user_profile` object in its context for:
  1. Resolving pronouns ("my email" → `email`).
  2. Converting times to the user's timezone.
  3. Matching memories indexed by name/email.

## 7. Implementation Plan (high level)
1. **Data Model** – create `models/user_profile.py` with required + optional fields.
2. **Config Loader** – extend `utils/config_loader.py` to parse `user_profile.yaml`.
3. **System Prompt** – update template & loader to inject user context block.
4. **YAML File** – add default example in `configs/`.
5. **API Layer** – CRUD endpoints in `backend/api/config_endpoints.py` (pattern match system prompt endpoints).
6. **Frontend UI** – new settings tab mirroring system prompt editor.
7. **Tests** – unit tests for loader; integration test for prompt rendering.

> Team review this document before coding. Adjust scope or fields as needed. 

---
### Gemini's Critical Review & Suggestions

This is a strong, well-reasoned design document that aligns with the project's existing architectural patterns. The plan is pragmatic and focuses on delivering a valuable MVP. The following points are intended to strengthen the design and consider future evolution.

1.  **Persistence Strategy (YAML vs. Database):**
    *   **Critique:** The choice to use a YAML file is excellent for MVP speed and simplicity. However, this approach has long-term limitations. As the system evolves, especially if it ever needs to support multiple users, a database-backed model will be more scalable, secure, and manageable.
    *   **Suggestion:** For the MVP, proceed with YAML, but explicitly acknowledge this as a technical choice made for speed. It's also critical to prevent sensitive user information from being accidentally committed to version control.
    *   **Action:** Add `configs/user_profile.yaml` to the `.gitignore` file immediately.

2.  **Configuration Hot-Reloading:**
    *   **Critique:** The document doesn't specify how configuration changes are propagated at runtime. The project already has a sophisticated system for hot-reloading prompts and MCP configurations using `watchdog`, Redis pub/sub, and WebSockets.
    *   **Suggestion:** The user profile should follow this established pattern. When the `user_profile.yaml` file is updated via the API, a `user_profile_updated` event should be published on Redis. The `CoreAgent` and any other relevant services should subscribe to this event and reload the profile in memory, ensuring changes take effect immediately without a restart. This maintains architectural consistency.

3.  **Runtime Access & Dependency Injection:**
    *   **Critique:** Section 6, "Runtime Usage," is slightly ambiguous about *how* the agent and its tools will access the `user_profile` object.
    *   **Suggestion:** The design should be more explicit. A good pattern would be to load the `UserProfile` object once when the agent is initialized and pass it as part of its core state or context. Tools that require user information (e.g., a future `send_email` tool) should receive this context object during their execution, making dependencies explicit. Avoid using global objects.

4.  **Prompt Engineering & Bloat:**
    *   **Critique:** Directly embedding free-text `notes` into the system prompt is a good starting point, but it can lead to prompt bloat and may not be the most efficient use of the context window as the notes grow.
    *   **Suggestion:** For the MVP, this is acceptable. For future iterations, consider a more advanced approach. For example, the `notes` could be used as a document for a small RAG (Retrieval-Augmented Generation) system, where only the most relevant notes for the current query are injected into the prompt.

5.  **Timezone Handling:**
    *   **Critique:** The plan specifies a "timezone dropdown," which is great. The implementation detail is important.
    *   **Suggestion:** Ensure the frontend is populated with a standard list of IANA timezone names (e.g., "America/New_York", "Europe/London"). The backend should use a robust library like `pytz` or Python 3.9+'s built-in `zoneinfo` for all timezone-aware calculations to prevent common off-by-one or daylight saving time errors. 