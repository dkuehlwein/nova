# NOV-125: Extract shared browser automation utility from LAM module

**Linear ticket:** NOV-125
**Branch:** `refactor/NOV-125-extract-shared-browser-automation`

## Investigation/Analysis

The file `backend/skills/add_user_to_coe_gitlab/lam_automation.py` contains two categories of code:

1. **Generic browser automation** (reusable across skills):
   - `_get_browser_cache()` - Process-level browser cache via `sys.modules`
   - `_get_profile_dir()` - Browser profile directory management (reads config)
   - `_get_storage_state_path()` - Cookie storage path
   - `_restore_sso_cookies()` - Restore SSO cookies with domain filtering
   - `_save_sso_cookies()` - Save cookies to disk
   - `_get_or_create_browser_context()` - Cached Playwright persistent context with auto-recovery
   - `close_lam_browser()` - Clean shutdown

2. **LAM-specific automation** (stays in the skill module):
   - `_build_lam_url()` - LAM URL construction
   - `generate_password()` - Password generation
   - `_load_config()` - Loads skill-specific config.yaml
   - `create_lam_account()` - Form automation
   - `check_lam_connection()` - Connection test

The generic functions currently depend on `_load_config()` which reads the skill's `config.yaml`. The shared module needs to decouple from this by accepting a `cache_key`, `default_profile_dir`, and `storage_state_filename` as parameters so each skill provides its own namespace.

## Approach

**TDD approach:**
1. Write failing tests for `backend/utils/browser_automation.py` (the shared module)
2. Implement the shared module to make tests pass
3. Refactor `lam_automation.py` to import from the shared module
4. Run existing GitLab skill tests to verify no regression

**Key design decisions:**
- The shared module functions accept configuration parameters instead of reading config files directly. This avoids coupling the shared module to any specific skill's config.
- Each skill provides its own `cache_key` to `sys.modules` so multiple skills can have independent browser instances.
- `get_profile_dir()` accepts a `default_dir` parameter; callers provide their own default.
- `get_storage_state_path()` accepts a `profile_dir` and `filename` parameter.
- `restore_sso_cookies()` and `save_sso_cookies()` are thin wrappers that operate on a context and a path.
- `get_or_create_browser_context()` takes a `cache_key` and `profile_dir` to decouple from any config loader.
- `close_browser()` takes a `cache_key` to close the right cached instance.

## Key Files

| Action | File |
|--------|------|
| Create | `backend/utils/browser_automation.py` |
| Create | `tests/unit/utils/test_browser_automation.py` |
| Modify | `backend/skills/add_user_to_coe_gitlab/lam_automation.py` |

## Open Questions / Risks

- The existing `TestPersistentBrowserProfile` and `TestBrowserCache` tests in `test_add_user_to_coe_gitlab.py` test the browser automation functions on the `lam_automation_module` fixture. After refactoring, those tests should still pass because `lam_automation.py` will delegate to the shared module. No test changes should be needed if the function signatures in `lam_automation.py` remain the same (they will -- the private functions just delegate now).
- The `_load_config()` function in `lam_automation.py` is used by both `_get_profile_dir()` and the LAM-specific code. After extraction, `_get_profile_dir()` in `lam_automation.py` will read config and pass the result to the shared module.
