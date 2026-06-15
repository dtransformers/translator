from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from app.core.config import settings

def _get_gemini_model() -> ChatGoogleGenerativeAI:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY must be set in environment when using gemini provider.")
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL_NAME,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
        convert_system_message_to_human=True
    )

def _get_ollama_model() -> ChatOllama:
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.LLM_MODEL_NAME,
        temperature=0.3
    )

@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "gemini":
        return _get_gemini_model()
    elif provider == "ollama":
        return _get_ollama_model()
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Please choose 'gemini' or 'ollama'.")
