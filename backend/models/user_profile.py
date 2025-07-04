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
    
    class Config:
        schema_extra = {
            "example": {
                "full_name": "Ada Lovelace",
                "email": "ada@example.com",
                "timezone": "Europe/London",
                "notes": "Prefers concise status updates.\nEnjoys historical anecdotes."
            }
        }


class UserProfileUpdate(BaseModel):
    """Model for updating user profile."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None
    notes: Optional[str] = None
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone is a valid IANA identifier."""
        if v is None:
            return v
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