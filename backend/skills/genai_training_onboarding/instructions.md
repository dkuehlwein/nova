# GenAI Training Participant Onboarding

Onboard participants for GenAI training by creating IAM accounts in LAM, GitLab user accounts, and adding them to the training GitLab project.

## Workflow

### 1. Parse the User's Input

The user provides participants in any format - names, emails, CSV, mixed. Parse directly into participant objects:

```json
[
  {"email": "alice@example.com", "first_name": "Alice", "last_name": "Smith"},
  {"name": "Bob Jones"}
]
```

### 2. Resolve Missing Emails

For entries without email, use `resolve_participant_email(name="Bob Jones")`.

If lookup fails, ask the user for the email address.

### 3. Process Each Participant (3-Step Sequence)

For each participant with a complete email, execute these tools **in sequence**:

#### Step A: Create IAM Account
```
create_iam_account(
    email="user@example.com",
    first_name="First",
    last_name="Last"
)
```
- Creates LDAP account via LAM browser automation
- Returns the generated username (first_initial + lastname)
- **Note the username** - you'll need it for the next step

#### Step B: Create GitLab User Account
```
create_gitlab_user_account(
    email="user@example.com",
    username="flast",  # Use username from step A
    display_name="First Last"
)
```
- Creates GitLab user linked to LDAP for SSO
- Must use the **same username** as the IAM account

#### Step C: Add to GitLab Project
```
add_user_to_gitlab_project(
    user_identifier="user@example.com"
)
```
- Adds user to the training repository with developer access
- Can use email or username as identifier

### 4. Report Results

After processing all participants, provide a clear summary:
- List successful onboardings with usernames
- List any failures with error details and hints
- If users are blocked, explain they need admin intervention

## Tools

| Tool | Purpose |
|------|---------|
| `resolve_participant_email` | Look up email via Outlook contacts |
| `create_iam_account` | Create LDAP account in LAM |
| `create_gitlab_user_account` | Create GitLab user linked to LDAP |
| `add_user_to_gitlab_project` | Add user to training repository |

## Participant Format

```json
{
    "email": "user@example.com",    // REQUIRED
    "first_name": "First",          // for username generation
    "last_name": "Last",            // for username generation
    "name": "Full Name"             // alternative to first/last
}
```

## Handling Errors

### User Already Exists in IAM
- The tool returns a hint to proceed to GitLab user creation
- Use the expected username (first_initial + lastname)

### User Already Exists in GitLab
- This is fine - proceed to add them to the project

### User is Blocked in GitLab
- The tool will indicate `blocked: true`
- Tell the user: "An admin needs to unblock this user in GitLab Admin > Users"
- Do NOT retry - this requires manual intervention

### User Not Found When Adding to Project
- Make sure `create_gitlab_user_account` was called first
- The user must exist in GitLab before they can be added to a project

## Partial Operations

If the user wants to skip steps:

- **Skip IAM creation**: User already has LDAP account
  - Start from `create_gitlab_user_account`, but you need to know the username
  - Ask user for the username if not obvious

- **Skip GitLab user creation**: User already has GitLab account
  - Go directly to `add_user_to_gitlab_project`

- **Only add to project**: User has both IAM and GitLab accounts
  - Just call `add_user_to_gitlab_project`

## Example Conversation

**User**: Onboard Alice Smith (alice.smith@example.com) for the GenAI training

**Agent**:
1. Creating IAM account for Alice Smith...
   - Result: Success, username: asmith

2. Creating GitLab user account...
   - Result: Success, user_id: 123

3. Adding to training project...
   - Result: Success, added as developer

**Summary**: Alice Smith (asmith) has been fully onboarded and has developer access to the training repository.
