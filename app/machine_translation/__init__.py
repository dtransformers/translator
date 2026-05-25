from .marian_service import MarianMTService
from app.core.config import settings

marian_mt_service = MarianMTService(is_dynamic_loading=settings.IS_DYNAMIC_LOADING)

__all__ = ["MarianMTService", "marian_mt_service"]
