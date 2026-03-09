"""
Pydantic schemas for organizations.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    logo_url: Optional[str] = None


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class ChangeRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|member)$")


class AcceptInviteRequest(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MembershipResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgWithRoleResponse(BaseModel):
    org: OrgResponse
    role: str


class InviteResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: str
    token: str
    invited_by: uuid.UUID
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
