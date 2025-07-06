# Nova Documentation Overhaul Plan

This document outlines the plan to create a new, comprehensive, and philosophy-driven documentation suite for the Nova project.

## Guiding Philosophy

The documentation will be built around two core principles:

1.  **AI as a Coworker:** Nova is not just a tool for automation. It is a flexible, collaborative partner designed to handle the complexities of modern knowledge work. It can reason about tasks, ask for help when it's stuck (`escalate_to_human`), and even identify its own limitations to request new capabilities (`feature_request` MCP).
2.  **Privacy-First & On-Premise:** Nova is a private assistant. All data remains under the user's control. The architecture is designed with a clear path towards full on-premise operation using local models like Ollama, ensuring data never has to be shared with third-party providers.

## Plan of Action

### Phase 1: Create a New Top-Level `README.md`

The project's root `README.md` will be rewritten to serve as the main entry point and project manifesto.

*   **Content:**
    *   **What is Nova?** A clear mission statement leading with the "AI as a Coworker" and "Privacy-First" philosophy.
    *   **The Nova Workflow:** A visual and descriptive summary of the collaborative loop: receiving a task, working on it, and interacting with the user when necessary.
    *   **Core Capabilities:** A list of features framed in the context of the philosophy (e.g., "Extensible Skillset via MCPs," "Persistent Memory," "Collaborative Chat").
    *   **Tech Stack:** A list of the key technologies used.
    *   **Getting Started:** A simple, 3-step guide to get the project running with `docker-compose`, linking to the more detailed `docs/1_Setup_and_Installation.md`.
    *   **Documentation:** A prominent link to the `/docs` directory for more in-depth information.

### Phase 2: Restructure and Rewrite the `docs` Directory

The `/docs` directory will be completely reorganized to create a logical, narrative-driven onboarding experience for new developers.

*   **Proposed Directory Structure:**

    ```
    docs/
    ├── README.md                   # The "Table of Contents" for all documentation
    ├── 1_Setup_and_Installation.md # Detailed setup guide
    ├── 2_The_Nova_Philosophy.md    # The foundational ideas of Nova
    ├── 3_Architecture_Deep_Dive/
    │   ├── 3.1_System_Overview.md      # The main components and how they connect
    │   ├── 3.2_The_Agent_Lifecycle.md  # The step-by-step flow of a task
    │   ├── 3.3_The_Memory_System.md    # How the agent's memory works
    │   └── 3.4_Real_Time_System.md     # How live updates are pushed to the UI
    ├── 4_Extending_Nova/
    │   ├── 4.1_Tools_and_MCPs.md       # Explains the tool architecture and existing MCPs
    │   └── 4.2_Adding_a_New_MCP.md     # A practical guide for developers
    └── archive/                        # Old, raw markdown files will be moved here
    ```

*   **Key Content Highlights:**
    *   **`2_The_Nova_Philosophy.md`**: This new file will be the cornerstone, detailing the core vision.
    *   **`3.2_The_Agent_Lifecycle.md`**: This will provide the narrative of how the agent "thinks" and processes a task from start to finish.
    *   **`3.3_The_Memory_System.md`**: This document will explain the concept of the agent's memory, clarifying that it is *implemented* using a knowledge graph but focusing on its conceptual role.
    *   **`4_Extending_Nova/`**: This section will be framed as "Growing Your Coworker's Abilities," making extensibility a core part of the story.

This plan will result in a professional, well-organized, and maintainable documentation suite that effectively communicates the project's unique vision and empowers developers to contribute meaningfully.
