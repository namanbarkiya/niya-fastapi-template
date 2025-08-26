from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional


class UserModel(BaseModel):
    """User model with email and password validation"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class EmailModel(BaseModel):
    """Email model for password reset"""
    email: EmailStr = Field(..., description="Email address for password reset")


class NewPasswordModel(BaseModel):
    """New password model with confirmation"""
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @validator('confirm_password')
    def validate_passwords_match(cls, v, values):
        """Validate password confirmation"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserProfileModel(BaseModel):
    """User profile model"""
    name: Optional[str] = Field(None, max_length=100, description="User's full name")
    avatar_url: Optional[str] = Field(None, description="User's avatar URL")
    bio: Optional[str] = Field(None, max_length=500, description="User's bio")


class UserResponseModel(BaseModel):
    """User response model"""
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AuthResponseModel(BaseModel):
    """Authentication response model"""
    status: str
    data: dict
    message: Optional[str] = None
