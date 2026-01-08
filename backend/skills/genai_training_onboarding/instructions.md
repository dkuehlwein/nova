# GenAI Training Participant Onboarding

Onboard participants for GenAI training by creating IAM accounts in LAM and adding them to GitLab.

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

### 3. Execute Onboarding

Once all participants have emails, call `execute_batch_onboarding` with the participant list. The tool approval system will show the user what's about to happen.

Report results clearly - especially usernames and temporary passwords for new IAM accounts.

## Tools

| Tool | Purpose |
|------|---------|
| `resolve_participant_email` | Look up email via Outlook contacts |
| `execute_batch_onboarding` | Create IAM accounts and add to GitLab |

## Participant Format

```json
{
    "email": "user@example.com",    // REQUIRED
    "first_name": "First",          // for IAM username
    "last_name": "Last",            // for IAM username
    "name": "Full Name"             // alternative to first/last
}
```

## Partial Operations

Users can skip steps:
- `skip_iam=True`: Only add to GitLab (accounts exist)
- `skip_gitlab=True`: Only create IAM accounts
