"""
taskboard top-level router.
"""
from fastapi import APIRouter

from app.products.taskboard.routes.projects import router as projects_router
from app.products.taskboard.routes.tasks import router as tasks_router

router = APIRouter()

router.include_router(projects_router, prefix="/projects", tags=["taskboard:projects"])

# Tasks are nested: /projects/{project_id}/tasks
router.include_router(
    tasks_router,
    prefix="/projects/{project_id}/tasks",
    tags=["taskboard:tasks"],
)
