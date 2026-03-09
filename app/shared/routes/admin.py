"""
Admin routes — cross-product dashboard and platform management.

All endpoints require the caller to be authenticated.
The dashboard endpoint additionally requires org owner/admin role when
an org_id is supplied; the service enforces that check internally.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.shared.models.user import User
from app.shared.schemas.dashboard import AdminDashboardResponse
from app.shared.services.dashboard_service import AdminDashboardService

router = APIRouter()


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    org_id: Optional[uuid.UUID] = Query(
        default=None,
        description=(
            "Scope the dashboard to a specific organisation. "
            "The caller must be owner or admin of that org. "
            "Omit for a platform-wide (no per-member breakdown) view."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    """
    Return an aggregate admin dashboard.

    - **With org_id**: verifies caller is org owner/admin, returns per-member
      activity across all products.
    - **Without org_id**: returns platform-wide aggregate counters only
      (no per-member breakdown).

    Data is aggregated from multiple product schemas via separate async
    queries combined in Python — no cross-schema SQL joins.
    """
    service = AdminDashboardService(db)
    return await service.get_dashboard(
        requesting_user_id=current_user.id,
        org_id=org_id,
    )
