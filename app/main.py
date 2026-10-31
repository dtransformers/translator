
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.readiness import readiness


from app.core.docs import API_TITLE, API_VERSION, API_DESCRIPTION, OPENAPI_TAGS


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The server starts serving immediately; translation routes stay gated
    # until the readiness monitor reports every dependency as OK.
    readiness.start()
    yield
    await readiness.stop()

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)




@app.get(
    "/health",
    tags=["health"],
    summary="Readiness check",
    description=(
        "Returns 200 only when every dependency is ready (DB, Duckling, LLM, and all models), "
        "otherwise 503 with the status of each component. Translation routes are gated on the same state."
    ),
    operation_id="health_check",
)
async def health():
    snapshot = readiness.snapshot()
    if not snapshot["ready"]:
        return JSONResponse(status_code=503, content={"status": "not_ready", **snapshot})
    return {"status": "ready", **snapshot}


@app.get(
    "/health/live",
    tags=["health"],
    summary="Liveness check",
    description="Returns 200 whenever the process is up and serving, regardless of dependency state.",
    operation_id="liveness_check",
)
async def liveness():
    return {"status": "alive"}




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
        },
        headers=getattr(exc, "headers", None),
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




app.include_router(api_router, prefix="/api/v1")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
