API_TITLE = "Translation API"
API_VERSION = "1.0.0"

API_DESCRIPTION = """A modular FastAPI application for high-quality, context-aware translation services.

## Features

- **Multi-engine translation** — NLLB-200 for simple texts, LLM (Gemini / Ollama / OpenRouter) for complex texts
- **Multi-tier semantic caching** — exact → normalized → vector similarity lookup
- **LLM context** — industry, summary, glossary, domain rules, and retrieved examples
- **Reusable translation units** — known phrases/entities auto-injected as glossary
- **Text quality estimation** — multilingual-e5 cosine similarity
- **Language detection** — automatic source-language identification

## Authentication

Translation, document, bucket, review, brand, and domain endpoints require **HTTP Basic Authentication**. Health endpoints, generated documentation, and the current debug database route do not require authentication.
"""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Operational health checks. No authentication required.",
    },
    {
        "name": "translation",
        "description": (
            "Core translation endpoints. Supports text translation, language "
            "detection. Text translation uses a multi-stage pipeline "
            "(verification → caching → context and complexity routing → NLLB-200 / LLM → "
            "quality scoring)."
        ),
    },
    {
        "name": "brands",
        "description": (
            "Brand profile management (CRUD). Brand profiles inject domain-specific "
            "context. The active draft prompt consumes industry, summary, and glossary; "
            "keyword/glossary matches influence routing."
        ),
    },
]
