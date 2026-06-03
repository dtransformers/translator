from .nllb_service import NLLBService
from app.core.config import settings

nllb_service = NLLBService()

__all__ = ["NLLBService", "nllb_service"]
