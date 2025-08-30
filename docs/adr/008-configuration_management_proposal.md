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

## Enhanced UI Design and Flow Proposal (post ADR-012)

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

## Summary

This enhanced configuration management proposal integrates ADR-012's hook architecture to provide a comprehensive, scalable system for managing Nova's configuration needs across development, deployment, and user preference contexts.

The 3-tier system provides clear separation of concerns:
- **Tier 1**: Development defaults in code
- **Tier 2**: Deployment configuration (secrets, hook configs, tool configs)  
- **Tier 3**: User preferences and profile data

The hook system from ADR-012 enhances this by adding hot-reloadable configuration for input sources while maintaining security through proper tier separation.