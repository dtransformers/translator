from .marian_service import MarianMTService
from app.core.config import settings

marian_mt_service = MarianMTService()

__all__ = ["MarianMTService", "marian_mt_service"]
