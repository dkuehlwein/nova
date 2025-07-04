# User Context Configuration – Implementation Document

## 1. Overview
This document provides detailed implementation specifications for adding user context configuration to Nova. The implementation allows Nova to understand basic user information (name, email, timezone, notes) for better personalization and context-aware responses.

## 2. Architecture Decisions

### 2.1 Persistence Strategy
- **Decision**: Use YAML file for MVP with explicit migration path to database
- **Rationale**: Aligns with existing config patterns, enables rapid development
- **Security**: Add `configs/user_profile.yaml` to `.gitignore` to prevent PII commits

### 2.2 Hot-Reloading Pattern
- **Decision**: Follow existing Redis pub/sub pattern for configuration updates
- **Implementation**: Use `user_profile_updated` event with WebSocket propagation
- **Consistency**: Maintains architectural consistency with prompt and MCP config updates

### 2.3 Runtime Access Pattern
- **Decision**: Inject `UserProfile` object into agent context during initialization
- **Benefits**: Explicit dependencies, avoid global state
- **Implementation**: Pass through agent creation and tool execution contexts

## 3. Data Models

### 3.1 Core Models
```python
# File: backend/models/user_profile.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
import pytz

class UserProfile(BaseModel):
    """User profile configuration for Nova agent personalization."""
    
    full_name: str = Field(..., description="User's full name")
    email: EmailStr = Field(..., description="Primary email address")
    timezone: str = Field(..., description="IANA timezone identifier")
    notes: Optional[str] = Field(None, description="Additional user context notes")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone is a valid IANA identifier."""
        try:
            pytz.timezone(v)
            return v
        except pytz.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")
    
    @validator('notes')
    def validate_notes_length(cls, v):
        """Ensure notes don't exceed reasonable length."""
        if v and len(v) > 5000:
            raise ValueError("Notes cannot exceed 5000 characters")
        return v

class UserProfileUpdate(BaseModel):
    """Model for updating user profile."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None
```

### 3.2 Event Model
```python
# Add to backend/models/events.py
class UserProfileUpdatedEvent(BaseModel):
    """Event published when user profile is updated."""
    event_type: str = "user_profile_updated"
    timestamp: datetime = Field(default_factory=datetime.now)
    profile: UserProfile
    source: str = "api"  # "api" or "file_watcher"
```

## 4. Configuration Management

### 4.1 YAML Structure
```yaml
# File: configs/user_profile.yaml
full_name: "Ada Lovelace"
email: "ada@example.com"
timezone: "Europe/London"
notes: |
  Prefers concise status updates.
  Enjoys historical anecdotes.
  Technical background: Strong in Python, TypeScript, and system architecture.
created_at: "2024-01-01T00:00:00Z"
updated_at: "2024-01-01T00:00:00Z"
```

### 4.2 Config Loader Extension
```python
# Extend backend/utils/config_loader.py
def load_user_profile(self) -> UserProfile:
    """Load user profile from YAML file."""
    profile_path = Path("configs/user_profile.yaml")
    
    if not profile_path.exists():
        # Create default profile
        default_profile = UserProfile(
            full_name="Nova User",
            email="user@example.com",
            timezone="UTC",
            notes="Add your personal context here."
        )
        self.save_user_profile(default_profile)
        return default_profile
    
    try:
        with open(profile_path, 'r') as f:
            data = yaml.safe_load(f)
        return UserProfile(**data)
    except Exception as e:
        logger.error("Failed to load user profile", extra={"data": {"error": str(e)}})
        raise

def save_user_profile(self, profile: UserProfile) -> None:
    """Save user profile to YAML file."""
    profile_path = Path("configs/user_profile.yaml")
    profile_path.parent.mkdir(exist_ok=True)
    
    profile.updated_at = datetime.now()
    
    try:
        with open(profile_path, 'w') as f:
            yaml.safe_dump(profile.dict(), f, default_flow_style=False)
    except Exception as e:
        logger.error("Failed to save user profile", extra={"data": {"error": str(e)}})
        raise
```

## 5. System Prompt Integration

### 5.1 Template Updates
```markdown
<!-- Add to backend/agent/prompts/NOVA_SYSTEM_PROMPT.md -->

**User Context:**
- Name: {{user.full_name}}
- Email: {{user.email}}
- Timezone: {{user.timezone}}
- Current Time: {{current_time_user_tz}}

{{#if user.notes}}
**Additional User Context:**
{{user.notes}}
{{/if}}
```

### 5.2 Prompt Loader Updates
```python
# Update backend/utils/prompt_loader.py
def load_system_prompt(self) -> str:
    """Load system prompt with user context injection."""
    prompt_template = self._load_template("NOVA_SYSTEM_PROMPT.md")
    user_profile = self.config_loader.load_user_profile()
    
    # Get current time in user's timezone
    user_tz = pytz.timezone(user_profile.timezone)
    current_time = datetime.now(user_tz)
    
    context = {
        "user": user_profile.dict(),
        "current_time_user_tz": current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    }
    
    return self._render_template(prompt_template, context)
```

## 6. API Implementation

### 6.1 Config Endpoints
```python
# Add to backend/api/config_endpoints.py
@config_router.get("/user-profile", response_model=UserProfile)
async def get_user_profile():
    """Get current user profile configuration."""
    try:
        profile = config_loader.load_user_profile()
        logger.info("User profile retrieved")
        return profile
    except Exception as e:
        logger.error("Failed to retrieve user profile", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail="Failed to retrieve user profile")

@config_router.put("/user-profile", response_model=UserProfile)
async def update_user_profile(update: UserProfileUpdate):
    """Update user profile configuration."""
    try:
        current_profile = config_loader.load_user_profile()
        
        # Apply updates
        update_data = update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(current_profile, field, value)
        
        # Save updated profile
        config_loader.save_user_profile(current_profile)
        
        # Publish update event
        event = UserProfileUpdatedEvent(profile=current_profile)
        await redis_manager.publish("user_profile_updated", event.dict())
        
        logger.info("User profile updated", extra={"data": {"updated_fields": list(update_data.keys())}})
        return current_profile
        
    except Exception as e:
        logger.error("Failed to update user profile", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail="Failed to update user profile")
```

## 7. Agent Integration

### 7.1 Agent Context Updates
```python
# Update backend/agent/chat_agent.py
async def create_chat_agent(reload_tools: bool = False) -> CompiledGraph:
    """Create chat agent with user context."""
    
    # Load user profile
    user_profile = config_loader.load_user_profile()
    
    # Create agent state with user context
    agent_state = {
        "user_profile": user_profile,
        # ... existing state ...
    }
    
    # Load system prompt with user context
    system_prompt = prompt_loader.load_system_prompt()
    
    # ... rest of existing agent creation ...
```

## 8. Frontend Implementation

### 8.1 User Settings Page
```typescript
// File: frontend/src/app/settings/user/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'

interface UserProfile {
  full_name: string
  email: string
  timezone: string
  notes?: string
}

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Australia/Sydney',
]

export default function UserSettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchUserProfile()
  }, [])

  const fetchUserProfile = async () => {
    try {
      const response = await fetch('/api/config/user-profile')
      if (response.ok) {
        const data = await response.json()
        setProfile(data)
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load user profile",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!profile) return
    
    setSaving(true)
    try {
      const response = await fetch('/api/config/user-profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(profile),
      })
      
      if (response.ok) {
        toast({
          title: "Success",
          description: "User profile updated successfully",
        })
      } else {
        throw new Error('Failed to update profile')
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update user profile",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div>Loading...</div>
  if (!profile) return <div>Failed to load user profile</div>

  return (
    <div className="container mx-auto py-6">
      <Card>
        <CardHeader>
          <CardTitle>User Profile</CardTitle>
          <CardDescription>
            Configure your personal information for better Nova personalization
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="full_name">Full Name</Label>
            <Input
              id="full_name"
              value={profile.full_name}
              onChange={(e) => setProfile({...profile, full_name: e.target.value})}
              placeholder="Enter your full name"
            />
          </div>
          
          <div>
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={(e) => setProfile({...profile, email: e.target.value})}
              placeholder="Enter your email address"
            />
          </div>
          
          <div>
            <Label htmlFor="timezone">Timezone</Label>
            <Select
              value={profile.timezone}
              onValueChange={(value) => setProfile({...profile, timezone: value})}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {COMMON_TIMEZONES.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <Label htmlFor="notes">Additional Notes</Label>
            <Textarea
              id="notes"
              value={profile.notes || ''}
              onChange={(e) => setProfile({...profile, notes: e.target.value})}
              placeholder="Add any additional context you'd like Nova to know about you..."
              rows={6}
            />
          </div>
          
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
```

## 9. Implementation Checklist

### Phase 1: Core Implementation
- [ ] Create `UserProfile` and `UserProfileUpdate` models
- [ ] Add `UserProfileUpdatedEvent` to events model
- [ ] Extend `ConfigLoader` with user profile methods
- [ ] Create default `user_profile.yaml` template
- [ ] Add `configs/user_profile.yaml` to `.gitignore`

### Phase 2: System Integration
- [ ] Update system prompt template with user context blocks
- [ ] Modify `PromptLoader` to inject user context
- [ ] Add timezone handling with `pytz`
- [ ] Update agent creation to include user profile

### Phase 3: API & Events
- [ ] Add user profile endpoints to `config_endpoints.py`
- [ ] Implement Redis event publishing for profile updates
- [ ] Add event handlers to services

### Phase 4: Frontend
- [ ] Create user settings page component
- [ ] Add timezone selection with IANA names
- [ ] Implement profile update API calls
- [ ] Add navigation menu item

### Phase 5: Testing
- [ ] Write unit tests for models and utilities
- [ ] Create integration tests for API endpoints
- [ ] Test event system and hot-reloading
- [ ] Test frontend functionality

## 10. Security & Deployment

### 10.1 Security Measures
- Add `configs/user_profile.yaml` to `.gitignore`
- Implement input validation and sanitization
- Add logging for all profile operations
- Validate timezone handling edge cases

### 10.2 Migration Path
For future database migration, the YAML structure directly maps to database schema:
```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    timezone VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

This implementation provides a robust foundation for user context in Nova while maintaining consistency with existing architecture patterns and addressing all the feedback from the design review. 