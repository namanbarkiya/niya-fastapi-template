"""
Import all taskboard models so SQLAlchemy registers them on Base.metadata.
Order matters: Project before Task (Task has FK to Project).
"""
from app.products.taskboard.models.project import Project  # noqa: F401
from app.products.taskboard.models.task import Task  # noqa: F401
