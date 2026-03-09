"""
product_alpha top-level router.
Mount sub-routers for each resource domain here.
"""
from fastapi import APIRouter

from app.products.product_alpha.routes.resources import router as resources_router

router = APIRouter()

router.include_router(resources_router, prefix="/resources", tags=["alpha:resources"])
