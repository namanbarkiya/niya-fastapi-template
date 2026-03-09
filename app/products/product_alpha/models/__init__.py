"""
Import all product_alpha models so SQLAlchemy registers them on Base.metadata.
"""
from app.products.product_alpha.models.resource import Resource  # noqa: F401
