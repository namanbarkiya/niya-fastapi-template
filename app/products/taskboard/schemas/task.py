"""
Pydantic schemas for taskboard Tasks.
"""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TaskStatus = Literal["todo", "in_progress", "done", "canceled"]
TaskPriority = Literal[0, 1, 2, 3]  # none, low, medium, high


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: TaskStatus = "todo"
    priority: TaskPriority = 0
    assigned_to: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    created_by: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: int
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
