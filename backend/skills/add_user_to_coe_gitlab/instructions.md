# Add User to CoE GitLab

Add users to CoE (Center of Excellence) GitLab projects by creating IAM accounts in LAM, GitLab user accounts, and granting project access.

## Prerequisites

### Required MCP Servers

**MS Graph MCP Server** - Required for person lookup (`resolve_participant_email` tool)
- Must be configured in `configs/mcp_servers.yaml`
- Requires Microsoft Graph API access with `User.Read.All` permission
- Used to search the organization directory for email addresses and login names

If the MS Graph MCP server is not available, you'll need to ask users to provide email addresses and usernames manually.

## Workflow

### 1. Parse the User's Input

The user provides participants in any format - names, emails, CSV, mixed. Parse directly into participant objects:

```json
[
  {"email": "alice@example.com", "first_name": "Alice", "last_name": "Smith"},
  {"name": "Bob Jones"}
]
```

### 2. Resolve Missing Emails and Get Login Name

For entries without email, use `add_user_to_coe_gitlab__resolve_participant_email(name="Bob Jones")`.

This tool uses MS Graph to search the organization directory and returns:
- `email` - the user's email address
- `display_name` - full name
- `mail_nickname` - **IMPORTANT**: the short login name (e.g., "bjones"). Use this as the Unix username!
- `first_name`, `last_name` - parsed from display_name

If lookup fails, ask the user for the email address.

### 3. Process Each Participant (3-Step Sequence)

For each participant with a complete email, execute these tools **in sequence**:

#### Step A: Create IAM Account
```
add_user_to_coe_gitlab__create_iam_account(
    email="user@example.com",
    first_name="First",
    last_name="Last",
    mail_nickname="flast"  # From step 2 - becomes the Unix username
)
```
- Creates LDAP account via LAM browser automation
- The `mail_nickname` (lowercase) becomes the Unix username
- **Important**: Always use `resolve_participant_email` first to get the `mail_nickname`
- **Note the username** - you'll need it for the next step

#### Step B: Create GitLab User Account
```
add_user_to_coe_gitlab__create_gitlab_user_account(
    email="user@example.com",
    username="flast",  # Use username from step A
    display_name="First Last"
)
```
- Creates GitLab user linked to LDAP for SSO
- Must use the **same username** as the IAM account

#### Step C: Add to GitLab Project
```
# Option 1: Use default project from config
add_user_to_coe_gitlab__add_user_to_gitlab_project(
    user_identifier="user@example.com"
)

# Option 2: Specify project by exact path
add_user_to_coe_gitlab__add_user_to_gitlab_project(
    user_identifier="user@example.com",
    gitlab_project="group/project-name"
)

# Option 3: Search for project by name (no "/" in value)
add_user_to_coe_gitlab__add_user_to_gitlab_project(
    user_identifier="user@example.com",
    gitlab_project="project-name"  # Will search and use first match
)
```
- Adds user to the GitLab project with developer access
- Can use email or username as identifier
- If `gitlab_project` contains `/`, it's treated as an exact path
- If `gitlab_project` has no `/`, it searches for matching projects

### 4. Report Results

After processing all participants, provide a clear summary:
- List successful additions with usernames
- List any failures with error details and hints
- If users are blocked, explain they need admin intervention

## Tools

| Tool | Purpose |
|------|---------|
| `add_user_to_coe_gitlab__resolve_participant_email` | Look up email and mail_nickname via MS Graph directory |
| `add_user_to_coe_gitlab__create_iam_account` | Create LDAP account in LAM |
| `add_user_to_coe_gitlab__create_gitlab_user_account` | Create GitLab user linked to LDAP |
| `add_user_to_coe_gitlab__search_gitlab_project` | Search for GitLab projects by name |
| `add_user_to_coe_gitlab__add_user_to_gitlab_project` | Add user to a GitLab repository |

## Searching for GitLab Projects

To add users to a project other than the default, you can:

1. **Search by name**: `search_gitlab_project(search_query="my-project")`
   - Returns a list of matching projects with their full paths
   - Use the `path_with_namespace` value for `add_user_to_gitlab_project`

2. **Directly in add_user_to_gitlab_project**: If you pass a project name without `/`, it will automatically search:
   ```
   add_user_to_gitlab_project(user_identifier="user@example.com", gitlab_project="my-project")
   ```

## User Format

```json
{
    "email": "user@example.com",    // REQUIRED
    "first_name": "First",          // for username generation fallback
    "last_name": "Last",            // for username generation fallback
    "name": "Full Name",            // alternative to first/last
    "mail_nickname": "flast"        // preferred - from MS Graph lookup
}
```

## Handling Errors

### User Already Exists in IAM
- The tool returns a hint to proceed to GitLab user creation
- Use the expected username (from mail_nickname or first_initial + lastname)

### User Already Exists in GitLab
- This is fine - proceed to add them to the project

### User is Blocked in GitLab
- The tool will indicate `blocked: true`
- Tell the user: "An admin needs to unblock this user in GitLab Admin > Users"
- Do NOT retry - this requires manual intervention

### User Not Found When Adding to Project
- Make sure `add_user_to_coe_gitlab__create_gitlab_user_account` was called first
- The user must exist in GitLab before they can be added to a project

### Project Not Found
- Use `add_user_to_coe_gitlab__search_gitlab_project` to find available projects
- Or ask the user for the exact project path

## Partial Operations

If the user wants to skip steps:

- **Skip IAM creation**: User already has LDAP account
  - Start from `add_user_to_coe_gitlab__create_gitlab_user_account`, but you need to know the username
  - Look up the user via MS Graph to get the mail_nickname (which is likely their existing username)

- **Skip GitLab user creation**: User already has GitLab account
  - Go directly to `add_user_to_coe_gitlab__add_user_to_gitlab_project`

- **Only add to project**: User has both IAM and GitLab accounts
  - Just call `add_user_to_coe_gitlab__add_user_to_gitlab_project`

## Example Conversation

**User**: Add Alice Smith to the training project

**Agent**:
1. Looking up Alice Smith in directory...
   - Found: alice.smith@example.com, mail_nickname: asmith

2. Creating IAM account for Alice Smith (username: asmith)...
   - Result: Success, username: asmith

3. Creating GitLab user account...
   - Result: Success, user_id: 123

4. Adding to project...
   - Result: Success, added as developer

**Summary**: Alice Smith (asmith) has been fully set up and has developer access to the GitLab project.

---

**User**: Add Bob Jones to the data-science project

**Agent**:
1. Looking up Bob Jones in directory...
   - Found: bob.jones@example.com, mail_nickname: bjones

2. Searching for project "data-science"...
   - Found: coe/data-science-toolkit

3. Adding to project...
   - Result: Success, added as developer

**Summary**: Bob Jones now has developer access to coe/data-science-toolkit.
