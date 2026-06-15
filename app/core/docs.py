API_TITLE = "Translation API"
API_VERSION = "1.0.0"

API_DESCRIPTION = """A modular FastAPI application for high-quality, context-aware translation services.

## Features

- **Multi-engine translation** — NLLB-200 for simple texts, LLM (Gemini / Ollama) for complex texts
- **Multi-tier semantic caching** — exact → normalized → vector similarity lookup
- **Brand context injection** — tone, glossary, audience, entities
- **Reusable translation units** — known phrases/entities auto-injected as glossary
- **Quality estimation** — cosine-similarity-based scoring
- **Language detection** — automatic source-language identification

## Authentication

All endpoints (except `/health`) require **HTTP Basic Authentication**. Include an `Authorization: Basic <base64(username:password)>` header with every request.
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
            "detection, and document translation through a multi-stage pipeline "
            "(verification → caching → complexity routing → MarianMT / LLM → "
            "quality scoring)."
        ),
    },
    {
        "name": "brands",
        "description": (
            "Brand profile management (CRUD). Brand profiles inject domain-specific "
            "context — industry, tone, audience, glossary, named entities — into "
            "the LLM translation pipeline for brand-aligned output."
        ),
    },
]
