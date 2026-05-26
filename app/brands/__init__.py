"""Brands entity module.

Public interface:
    - BrandService: service class for all brand operations
    - Brand: SQLAlchemy model (for type hints only)
"""

from .models import Brand
from .service import BrandService

__all__ = ["BrandService", "Brand"]
