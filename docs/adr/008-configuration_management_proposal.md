# Configuration Management Proposal

**Status**: ENHANCED by [ADR-012: Multi-Input Hook Architecture Design](./012-multi-input-hook-architecture-design.md)

## 🎯 Current Problems
1. **Hardcoded values** in docker-compose.yml (passwords, DB URLs)
2. **No onboarding path** for new users 
3. **Manual .env file creation** required
4. **Settings scattered** across multiple files
5. **No runtime configuration** updates

## 🏗️ Proposed Solution: Enhanced 3-Tier Configuration System

**Note**: This system has been enhanced by ADR-012's hook architecture to better organize configuration responsibilities.

### Tier 1: Development Defaults (Built-in)
- **Purpose**: Zero-config development setup
- **Location**: `backend/config.py` defaults
- **Examples**: `LOG_LEVEL=INFO`, `HOST="0.0.0.0"`, `PORT=8000`

### Tier 2: Deployment Environment (.env + Hook Configs)
- **Purpose**: Infrastructure secrets & deployment-specific settings
- **Location**: 
  - `.env` file (gitignored) - secrets and infrastructure
  - `configs/input_hooks.yaml` - input source configurations (from ADR-012)
  - `configs/mcp_servers.yaml` - tool configurations
- **Examples**: 
  - API keys, database URLs, service endpoints (`.env`)
  - Hook polling intervals, enabled states (`input_hooks.yaml`)
  - Available MCP tools and capabilities (`mcp_servers.yaml`)

### Tier 3: User Settings (Database)
- **Purpose**: Runtime configurable user preferences and profile
- **Location**: `user_settings` table
- **Examples**: User profile, UI preferences, notification settings, onboarding state

## 📋 Enhanced Settings Classification

```yaml
# TIER 1: Development Defaults (config.py)
development:
  LOG_LEVEL: "INFO"
  HOST: "0.0.0.0"
  PORT: 8000
  DEFAULT_LLM_MODEL: "phi-4-Q4_K_M"

# TIER 2A: Deployment Secrets (.env)
secrets:
  DATABASE_URL: "postgresql://..."
  REDIS_URL: "redis://..."
  GOOGLE_API_KEY: "your_key_here"
  LINEAR_API_KEY: "your_key_here"
  NEO4J_PASSWORD: "secure_password"

# TIER 2B: Hook Configurations (configs/input_hooks.yaml - from ADR-012)
hooks:
  email:
    name: "email"
    hook_type: "email"
    enabled: true
    polling_interval: 300
    create_tasks: true
    hook_settings:
      max_per_fetch: 50
      label_filter: null
  calendar:
    name: "calendar"
    hook_type: "calendar"
    enabled: false
    polling_interval: 600
    create_tasks: true
    hook_settings:
      calendar_ids: ["primary"]

# TIER 2C: Tool Configurations (configs/mcp_servers.yaml)
mcp_servers:
  google_workspace:
    command: "uv"
    args: ["--directory", "/path/to/mcp-google-workspace", "run", "mcp-google-workspace"]

# TIER 3: User Settings (database)
user_preferences:
  user_name: "User Name"
  user_email: "user@example.com" 
  onboarding_complete: false
  notification_preferences: {...}
  ui_theme: "light"
  chat_llm_model: "phi-4-Q4_K_M"
  chat_llm_temperature: 0.1
```

## 🚀 Implementation Plan

### Phase 1: Fix Hardcoded Values
1. Create `.env.example` template
2. Replace hardcoded values with environment variables
3. Add validation for required secrets

### Phase 2: Database Settings
1. Create `user_settings` table
2. Add settings API endpoints
3. Create simple frontend settings page

### Phase 3: Smart Onboarding
1. Auto-detect missing configuration
2. Guide users through setup
3. Validate API keys during setup

## 📁 Enhanced File Structure (post ADR-012)
```
configs/
├── .env.example           # Template for new users (Tier 2A)
├── input_hooks.yaml       # Hook configurations (Tier 2B) - NEW from ADR-012
├── mcp_servers.yaml       # MCP config (Tier 2C) - existing
└── user_profile.yaml      # Legacy - migrated to database (Tier 3)

backend/
├── config.py              # Tier 1 defaults
├── input_hooks/           # Hook system (NEW from ADR-012)
│   ├── base_hook.py       # BaseInputHook abstract class
│   ├── hook_registry.py   # InputHookRegistry 
│   └── email_hook.py      # EmailInputHook implementation
├── models/
│   ├── settings.py        # Tier 3 user settings model
│   └── models.py          # Enhanced with processed_items table
├── api/settings_endpoints.py # Enhanced settings API
└── utils/config_registry.py  # Enhanced ConfigRegistry (existing)

frontend/
└── app/settings/          # Enhanced settings UI pages
```

## 🛠️ Implementation Details

### New User Experience
1. **Copy `.env.example` to `.env`**
2. **Run setup wizard via web UI**
3. **System validates API keys and saves to database**

### Enhanced Configuration Priority (post ADR-012)
- User settings (database) → Hook configs (YAML) → .env → defaults
- Runtime changes affect Tier 3 settings and some Tier 2B hook settings

### Service Restart Logic (Enhanced)
- **Tier 1 changes**: require full restart
- **Tier 2A (.env) changes**: require restart  
- **Tier 2B (hook configs) changes**: hot reload via ConfigRegistry pattern (from ADR-012)
- **Tier 2C (MCP configs) changes**: hot reload (existing functionality)
- **Tier 3 changes**: hot reload via API updates

## 🔧 Example .env.example Template

```bash
# Database Configuration
DATABASE_URL=postgresql://nova:password@localhost:5432/nova_kanban
POSTGRES_PASSWORD=secure_password_here

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Neo4j Configuration
NEO4J_PASSWORD=secure_password_here

# API Keys (get from respective services)
GOOGLE_API_KEY=your_google_api_key_here
LINEAR_API_KEY=your_linear_api_key_here

# Optional: Flower Monitoring
FLOWER_USER=admin
FLOWER_PASSWORD=secure_flower_password

# Optional: Service Configuration
EMAIL_ENABLED=false
LOG_LEVEL=INFO
```

## 🎯 Benefits

1. **Secure by Default**: No secrets in code
2. **Easy Onboarding**: Copy one file, run setup wizard
3. **Hot Reload**: Runtime changes for user preferences
4. **Consistent**: All config follows same pattern
5. **Scalable**: Easy to add new settings

## 📊 Migration Strategy

1. **Phase 1**: Immediate fixes (hardcoded values)
2. **Phase 2**: Database settings (non-breaking)
3. **Phase 3**: Frontend UI (enhancement)

This approach maintains backward compatibility while providing a path to better configuration management.
---
## Review Notes (Gemini)

This proposal correctly identifies the core issues with the current configuration and onboarding process. The 3-tier system is a robust and scalable model that provides a clear separation of concerns between development defaults, deployment secrets, and user-configurable settings. This aligns perfectly with the project's privacy-first, on-premise philosophy.

**Key Strengths:**

*   **Clear Problem-Solution Fit:** The proposed 3-tier system directly addresses the problems of hardcoded values and scattered settings.
*   **Focus on Onboarding:** The plan prioritizes the new user experience, which is critical for adoption. The idea of a setup wizard is excellent.
*   **Security-Minded:** Moving secrets to a git-ignored `.env` file and providing a `.env.example` is a fundamental security improvement.

**Points for Consideration:**

*   **API Key Validation:** The plan mentions validating API keys. This should be done carefully. The validation logic in the backend should make a simple, low-cost API call (e.g., `get_user` or `list_projects`) to confirm the key is valid before saving it.
*   **Settings API Security:** The API endpoints for settings must be carefully designed. Endpoints should never expose Tier 1 or Tier 2 values (from `config.py` or `.env`) to the frontend, only the Tier 3 user settings from the database.

This is a solid and necessary proposal. The phased approach is practical and will deliver value at each stage.

## Analysis of Existing Configuration Files

The new 3-tier model provides a clear place for the existing configuration files:

*   **`mcp_servers.yaml`**: This file defines the available tools and services for Nova. This is a **Tier 2 (Deployment Environment)** configuration. It's not a user preference but a core part of the environment's setup that defines the agent's capabilities. It should remain a YAML file, as it's not secret but is fundamental to the deployment.
*   **`user_profile.yaml`**: This contains user-specific data like name and email. This information belongs in **Tier 3 (User Settings)**. During the first run of the new setup wizard, the data from this file should be migrated into the new `user_settings` database table. After migration, this file should be deprecated and removed to centralize all user settings in the database.

## UI Design and Flow Proposal

### Onboarding Wizard (First-Time Setup)

To ensure the wizard runs only once, a new flag should be added to the `user_settings` table: `onboarding_complete (boolean)`.

**Flow:**

1.  **Initial Check:** When a user accesses the UI, the backend checks if `onboarding_complete` is `true`. If so, it loads the main application. Otherwise, it redirects to the setup wizard.
2.  **Welcome:** A brief introduction to Nova, framed by the "AI Coworker" philosophy.
3.  **Connect Services:** A form for required API keys (Google, Linear, etc.). Each field will have a link to instructions. The backend validates each key in real-time before allowing the user to proceed.
4.  **User Profile & Preferences:** A form to confirm user details (migrated from `user_profile.yaml` on first run) and set initial preferences like timezone.
5.  **Completion:** The backend sets `onboarding_complete` to `true` in the database. The user is then directed to the main application.

### Centralized Settings Page

The existing settings page is a strong foundation. The primary work is in the backend to align the data storage with the 3-tier model and to build the onboarding logic that directs new users to the settings page.

**Enhanced Structure (post ADR-012):**

*   **Tab 1: User Profile:** Manage name, email, etc. (Tier 3)
*   **Tab 2: System Prompt:** Edit the agent's core prompt. (Tier 3)
*   **Tab 3: Input Sources:** Manage hook configurations (from ADR-012). Hook enabled/disabled states, polling intervals, and hook-specific settings.
*   **Tab 4: Connected Services (MCP):** Manage which tools are enabled. Tool availability is Tier 2C, but enabled/disabled state is Tier 3.
*   **Tab 5: System Status:** A read-only view of system health.

## User Installation Proposal

### Recommended Solution: "Getting Started" Script

A setup script provides a user-friendly installation process that respects the on-premise model.

**How it Works:**

1.  **Download:** The user downloads `start-nova.sh` (Linux/macOS) or `start-nova.bat` (Windows).
2.  **Execute:** The user runs the script.
3.  **The Script's Logic:**
    *   **Dependency Check:** Verifies Docker is installed and running. If not, provides a link to the Docker Desktop download page and exits.
    *   **Initialize Environment:** If `.env` doesn't exist, it copies `.env.example` to `.env`.
    *   **Launch:** Runs `docker-compose up -d`.
    *   **Open Browser:** Opens the user's browser to `http://localhost:8000`, where the onboarding wizard will begin.

This approach automates the technical setup, making Nova accessible to a broader audience without compromising the privacy-first, on-premise architecture.

---
## Review Notes (Gemini)

This proposal correctly identifies the core issues with the current configuration and onboarding process. The 3-tier system is a robust and scalable model that provides a clear separation of concerns between development defaults, deployment secrets, and user-configurable settings. This aligns perfectly with the project's privacy-first, on-premise philosophy.

**Key Strengths:**

*   **Clear Problem-Solution Fit:** The proposed 3-tier system directly addresses the problems of hardcoded values and scattered settings.
*   **Focus on Onboarding:** The plan prioritizes the new user experience, which is critical for adoption. The idea of a setup wizard is excellent.
*   **Security-Minded:** Moving secrets to a git-ignored `.env` file and providing a `.env.example` is a fundamental security improvement.

**Points for Consideration:**

*   **API Key Validation:** The plan mentions validating API keys. This should be done carefully. The validation logic in the backend should make a simple, low-cost API call (e.g., `get_user` or `list_projects`) to confirm the key is valid before saving it.
*   **Settings API Security:** The API endpoints for settings must be carefully designed. Endpoints should never expose Tier 1 or Tier 2 values (from `config.py` or `.env`) to the frontend, only the Tier 3 user settings from the database.

This is a solid and necessary proposal. The phased approach is practical and will deliver value at each stage.

## Analysis of Existing Configuration Files

The new 3-tier model provides a clear place for the existing configuration files:

*   **`mcp_servers.yaml`**: This file defines the available tools and services for Nova. This is a **Tier 2 (Deployment Environment)** configuration. It's not a user preference but a core part of the environment's setup that defines the agent's capabilities. It should remain a YAML file, as it's not secret but is fundamental to the deployment.
*   **`user_profile.yaml`**: This contains user-specific data like name and email. This information belongs in **Tier 3 (User Settings)**. During the first run of the new setup wizard, the data from this file should be migrated into the new `user_settings` database table. After migration, this file should be deprecated and removed to centralize all user settings in the database.

## UI Design and Flow Proposal

### Onboarding Wizard (First-Time Setup)

To ensure the wizard runs only once, a new flag should be added to the `user_settings` table: `onboarding_complete (boolean)`.

**Flow:**

1.  **Initial Check:** When a user accesses the UI, the backend checks if `onboarding_complete` is `true`. If so, it loads the main application. Otherwise, it redirects to the setup wizard.
2.  **Welcome:** A brief introduction to Nova, framed by the "AI Coworker" philosophy.
3.  **Connect Services:** A form for required API keys (Google, Linear, etc.). Each field will have a link to instructions. The backend validates each key in real-time before allowing the user to proceed.
4.  **User Profile & Preferences:** A form to confirm user details (migrated from `user_profile.yaml` on first run) and set initial preferences like timezone.
5.  **Completion:** The backend sets `onboarding_complete` to `true` in the database. The user is then directed to the main application.

### Centralized Settings Page

A dedicated **Settings** page will allow users to manage their preferences at runtime.

**Structure:**

*   **Tab 1: User Profile:** Manage name, email, etc.
*   **Tab 2: Preferences:** Control all Tier 3 settings (email polling, notifications).
*   **Tab 3: Connected Services:** Shows the *status* of integrations ("Google: Connected"). Provides a secure way to update or disconnect services.
*   **Tab 4: System Status (Advanced):** A **read-only** view of non-sensitive Tier 1 and Tier 2 info (app version, log level), for debugging. **No secrets will be displayed.**

## User Installation Proposal

### Recommended Solution: "Getting Started" Script

A setup script provides a user-friendly installation process that respects the on-premise model.

**How it Works:**

1.  **Download:** The user downloads `start-nova.sh` (Linux/macOS) or `start-nova.bat` (Windows).
2.  **Execute:** The user runs the script.
3.  **The Script's Logic:**
    *   **Dependency Check:** Verifies Docker is installed and running. If not, provides a link to the Docker Desktop download page and exits.
    *   **Initialize Environment:** If `.env` doesn't exist, it copies `.env.example` to `.env`, preserving any existing user changes.
    *   **Launch:** Runs `docker-compose up -d`.
    *   **Open Browser:** Opens the user's browser to `http://localhost:8000`, where the onboarding wizard will begin.

This approach automates the technical setup, making Nova accessible to a broader audience without compromising the privacy-first, on-premise architecture.
---
## Review Notes (Gemini)

This proposal correctly identifies the core issues with the current configuration and onboarding process. The 3-tier system is a robust and scalable model that provides a clear separation of concerns between development defaults, deployment secrets, and user-configurable settings.

**Key Strengths:**

*   **Clear Problem-Solution Fit:** The proposed 3-tier system directly addresses the problems of hardcoded values and scattered settings.
*   **Focus on Onboarding:** The plan prioritizes the new user experience, which is critical for adoption. The idea of a setup wizard is excellent.
*   **Security-Minded:** Moving secrets to a git-ignored `.env` file and providing a `.env.example` is a fundamental security improvement.

**Points for Consideration:**

*   **API Key Validation:** The plan mentions validating API keys. This should be done carefully. The validation logic in the backend should make a simple, low-cost API call (e.g., `get_user` or `list_projects`) to confirm the key is valid before saving it.
*   **Settings API Security:** The API endpoints for settings must be carefully designed. Endpoints should never expose Tier 1 or Tier 2 values (from `config.py` or `.env`) to the frontend, only the Tier 3 user settings from the database.

This is a solid and necessary proposal. The phased approach is practical and will deliver value at each stage.

## UI Design and Flow Proposal

To complement the backend changes, here is a proposed design for the user-facing configuration flow.

### Onboarding Wizard (First-Time Setup)

A new user's first interaction should be a guided setup wizard, triggered automatically if the backend detects that essential configurations (like API keys) are missing.

**Flow:**

1.  **Welcome:** A brief introduction to Nova and the setup process.
2.  **Connect Services:**
    *   A form with input fields for required API keys (Google, Linear, etc.).
    *   Each field will be clearly labeled and include a link to the service's documentation on how to generate an API key.
    *   Upon submission, the backend attempts to validate each key. The UI provides real-time feedback (e.g., a green checkmark for success, a red error message for failure). The user cannot proceed until all required keys are validated.
3.  **User Preferences (Optional):**
    *   A simple form for initial Tier 3 settings, such as selecting a timezone or setting notification preferences. This step can be skipped.
4.  **Done:** A confirmation screen that directs the user to the main Nova application (e.g., the Kanban board).

### Centralized Settings Page

After onboarding, a dedicated **Settings** page should be accessible from the main navigation menu. This page will be the central hub for all user-configurable options.

**Structure:**

The page should use a tabbed or multi-section layout:

*   **Tab 1: User Profile:** Basic user information (name, email, etc.).
*   **Tab 2: Preferences:** Contains all Tier 3 settings from the database. This is where users can make runtime changes.
    *   **Email Polling:** A toggle to enable/disable and a number input for the interval.
    *   **Notifications:** A group of checkboxes to control different notification types.
    *   **Task Defaults:** Default settings for new tasks.
*   **Tab 3: Connected Services:**
    *   This section **does not** display the API keys. Instead, it shows the *status* of each integration (e.g., "Google: Connected", "Linear: Not Configured").
    *   Each service has a "Disconnect" or "Update Key" button. Clicking "Update Key" opens a secure modal for the user to enter a new key, triggering the validation flow again.
*   **Tab 4: System Status (Advanced):**
    *   A **read-only** section for advanced users or for debugging.
    *   It can display non-sensitive Tier 1 and Tier 2 information, such as the application version, log level, or whether email services are enabled in the deployment, but **never** secrets like database URLs or passwords.

## User Installation and Onboarding Proposal

### The Challenge: Beyond `docker-compose`

Expecting users to clone a repository and run `docker-compose up` is a significant barrier for anyone who isn't a developer. To make Nova accessible, the installation process must be simplified.

### Recommended Solution: "Getting Started" Script

The most practical short-term solution is to provide a user-friendly setup script.

**How it Works:**

1.  **Download:** The user downloads a single file: `start-nova.sh` (for Linux/macOS) or `start-nova.bat` (for Windows) from the project's website or GitHub Releases page.
2.  **Execute:** The user runs the script from their terminal.
3.  **The Script's Logic:**
    *   **Dependency Check:** The script first checks if Docker and Docker Compose are installed. If not, it prints a user-friendly message with a link to the official Docker Desktop installation page and then exits.
    *   **Download Assets:** It automatically pulls the required Docker images from a public registry (like Docker Hub).
    *   **Initialize Environment:** It checks for an `.env` file. If one doesn't exist, it copies the bundled `.env.example` to `.env`.
    *   **Launch:** It runs `docker-compose up -d` to start Nova in the background.
    *   **Open Browser:** It automatically opens the user's default web browser to the Nova UI (`http://localhost:8000`), where the onboarding wizard will take over.

This approach automates the technical steps while still leveraging the power and isolation of Docker.

### Long-Term Vision: Cloud-Hosted Nova

The ultimate goal for user accessibility should be a fully managed SaaS (Software as a Service) version of Nova. This would eliminate the need for any local installation, allowing users to simply sign up and start using the application from their web browser. This is a significant undertaking but represents the most user-friendly path forward.
