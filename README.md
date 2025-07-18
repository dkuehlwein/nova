# Nova: Your Private, On-Premise AI Secretary

<br/>
<p align="center">
  <!-- TODO: Add a compelling GIF or video link here showing the Nova workflow -->
  <img src="https://placehold.co/800x400?text=Nova+In+Action+(Video+Coming+Soon)" alt="Nova Workflow Demo"/>
</p>
<br/>

Most AI assistants require you to send your data to the cloud. Nova is built on a simple, powerful idea: **your AI should work for you, on your hardware, under your control.**

Nova is an open-source AI secretary that runs entirely on-premise. It brings the power of a dedicated assistant to your workflow while guaranteeing that your data remains private. Period.

---

## How Nova Works

Nova acts as a true secretary, with privacy as its most important duty.

*   🔒 **Private & On-Premise:** This is Nova's core promise. Run it on your own servers. Your data, conversations, and models never leave your infrastructure.
*   👀 **Transparent & Autonomous:** Nova manages its own task list on a kanban board. You can watch it work, provide guidance, and have the final say, offering the perfect blend of autonomy and control.
*   🧠 **Remembers & Improves:** With a persistent graph memory, Nova learns from your interactions. If it lacks a skill, it can request a new tool from its developers, creating a foundation for continuous improvement.
*   🔌 **Adaptable Skills:** While it comes with core secretarial skills (task management, email processing), Nova can be extended with new abilities via MCPs to fit your specific needs.

<br/>
<p align="center">
  <!-- TODO: Add a clean screenshot of the Kanban UI -->
  <img src="https://placehold.co/800x450?text=Nova+Kanban+UI" alt="Nova UI Screenshot"/>
</p>
<br/>

---

## A Vision in Progress: Help Us Build the Future

**This is a project driven by a vision, but it is still in its early stages.** Many of the features described here are under active development. We are looking for enthusiastic developers and contributors to help us turn this proof-of-concept into a robust, real-world application.

If you are excited by the idea of a private, collaborative AI, we invite you to join us. Your contributions can help shape the future of Nova.

---

## Try it Now

Get your own AI secretary running in under a minute.

1.  **Prerequisites:** Ensure you have `docker` and `docker-compose` installed.
2.  **Run Nova:**
    ```bash
    docker-compose up -d
    ```
3.  **Open Your Browser:** Navigate to `http://localhost:3000` and give Nova your first task.

---

## Dive Deeper

*   **Want to see how it works?** ➡️ Read our **[Architecture Deep Dive](docs/3_Architecture_Deep_Dive/3.1_System_Overview.md)**.
*   **Want to contribute?** ➡️ Check out the **[Developer Setup Guide](docs/1_Setup_and_Installation.md)**.
*   **Want to see the full vision?** ➡️ Explore our **[Documentation](docs/README.md)**.

---

## Tech Stack

**Backend:** FastAPI, LangChain/LangGraph, SQLAlchemy, PostgreSQL, Redis
**Frontend:** Next.js, React, TailwindCSS
**AI:** Google (default), configurable for local models via LiteLLM
