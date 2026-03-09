"""
Pydantic schemas for product_alpha Resources.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class CreateResourceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class UpdateResourceRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    data: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class ResourceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
