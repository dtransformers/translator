"""
Translation API — main application entry point.

FastAPI application with OpenAPI/Swagger documentation, health check,
exception handlers, and Basic HTTP Authentication.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.core.config import settings
from app.machine_translation import marian_mt_service
from app.db.session import init_db

# --------------------------------------------------------------------- #
#  OpenAPI Tag Metadata
# --------------------------------------------------------------------- #

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


# --------------------------------------------------------------------- #
#  Lifespan
# --------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    if not settings.IS_DYNAMIC_LOADING:
        marian_mt_service.preload_models()
    yield


# --------------------------------------------------------------------- #
#  Application
# --------------------------------------------------------------------- #

app = FastAPI(
    title="Translation API",
    version="1.0.0",
    description=(
        "A modular FastAPI application for high-quality, context-aware "
        "translation services.\n\n"
        "## Features\n\n"
        "- **Multi-engine translation** — MarianMT for simple texts, LLM "
        "(Gemini / Ollama) for complex texts\n"
        "- **Multi-tier semantic caching** — exact → normalized → vector "
        "similarity lookup\n"
        "- **Brand context injection** — tone, glossary, audience, entities\n"
        "- **Reusable translation units** — known phrases/entities auto-injected "
        "as glossary\n"
        "- **Quality estimation** — cosine-similarity-based scoring\n"
        "- **Language detection** — automatic source-language identification\n\n"
        "## Authentication\n\n"
        "All endpoints (except `/health`) require **HTTP Basic Authentication**. "
        "Include an `Authorization: Basic <base64(username:password)>` header "
        "with every request."
    ),
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# --------------------------------------------------------------------- #
#  Health Check (no auth)
# --------------------------------------------------------------------- #

@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    description="Returns service status. Use for liveness/readiness probes.",
    operation_id="health_check",
)
async def health():
    """Lightweight liveness probe."""
    return {"status": "healthy"}


# --------------------------------------------------------------------- #
#  Exception Handlers
# --------------------------------------------------------------------- #

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        loc = ".".join(str(x) for x in error.get("loc", []))
        msg = error.get("msg", "invalid value")
        errors.append(f"{loc}: {msg}")
    error_msg = "; ".join(errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "data": None,
            "error": f"Validation error - {error_msg}"
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": exc.detail
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "error": f"Internal server error: {str(exc)}"
        }
    )


# --------------------------------------------------------------------- #
#  Router Registration
# --------------------------------------------------------------------- #

app.include_router(api_router, prefix="/api/v1")


# --------------------------------------------------------------------- #
#  Dev Server
# --------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
