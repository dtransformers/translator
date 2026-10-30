from functools import lru_cache
from langchain_core.language_models.chat_models import BaseChatModel

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

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

def _get_openrouter_model() -> ChatOpenAI:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY must be set in environment when using openrouter provider.")
    return ChatOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.LLM_MODEL_NAME,
        temperature=0.3,
        # Only route to upstream providers that honor response_format (json_schema)
        extra_body={"provider": {"require_parameters": True}}
    )

@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "gemini":
        return _get_gemini_model()
    elif provider == "ollama":
        return _get_ollama_model()
    elif provider == "openrouter":
        return _get_openrouter_model()
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Please choose 'gemini', 'ollama' or 'openrouter'.")
