from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from app.core.config import settings

def get_llm() -> BaseChatModel:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set in environment when using gemini provider.")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
            convert_system_message_to_human=True # Required for older gemini models sometimes, but generally useful
        )
        
    elif provider == "ollama":
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL_NAME,
            temperature=0.3
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Please choose 'gemini' or 'ollama'.")
