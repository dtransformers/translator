"""
Central application readiness.

Every dependency the translation pipeline needs reports into one shared state.
The app is ready only when every check passes; a background monitor re-runs the
checks on an interval so the state follows outages and recoveries without a restart.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CheckStatus:
    ok: bool = False
    error: str | None = "pending"
    checked_at: datetime | None = None


class Readiness:
    CHECKS = (
        "db",
        "duckling",
        "llm",
        "nllb",
        "embedding_model",
        "quality_model",
        "complexity_models",
        "nltk_punkt",
    )

    def __init__(self) -> None:
        self.checks: dict[str, CheckStatus] = {name: CheckStatus() for name in self.CHECKS}
        self._db_initialized = False
        self._task: asyncio.Task | None = None

    @property
    def is_ready(self) -> bool:
        return all(check.ok for check in self.checks.values())

    def failing(self) -> dict[str, str]:
        return {name: check.error or "failed" for name, check in self.checks.items() if not check.ok}

    def snapshot(self) -> dict:
        return {
            "ready": self.is_ready,
            "components": {
                name: {
                    "status": "ok" if check.ok else "error",
                    "error": check.error,
                    "checked_at": check.checked_at.isoformat() if check.checked_at else None,
                }
                for name, check in self.checks.items()
            },
        }

    def _set(self, name: str, ok: bool, error: str | None = None) -> None:
        previous = self.checks[name]
        if previous.ok != ok:
            if ok:
                logger.info("Readiness check '%s' is now OK", name)
            else:
                logger.warning("Readiness check '%s' failed: %s", name, error)
        self.checks[name] = CheckStatus(ok=ok, error=None if ok else error, checked_at=datetime.now(timezone.utc))

    async def _run(self, name: str, check) -> None:
        try:
            await check()
            self._set(name, True)
        except Exception as e:
            self._set(name, False, f"{type(e).__name__}: {e}" if str(e) else type(e).__name__)

    # --- External services: re-checked on every cycle ---

    async def _check_db(self) -> None:
        from app.db.session import engine, init_db

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        if not self._db_initialized:
            await init_db()
            self._db_initialized = True

    async def _check_duckling(self) -> None:
        async with httpx.AsyncClient(timeout=settings.READINESS_CHECK_TIMEOUT) as client:
            resp = await client.post(settings.DUCKLING_URL, data={"text": "hello", "locale": "en_XX"})
            resp.raise_for_status()

    async def _check_llm(self) -> None:
        provider = settings.LLM_PROVIDER.lower()
        async with httpx.AsyncClient(timeout=settings.READINESS_CHECK_TIMEOUT) as client:
            if provider == "ollama":
                resp = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                resp.raise_for_status()
                installed = {m["name"] for m in resp.json().get("models", [])}
                wanted = settings.LLM_MODEL_NAME
                if wanted not in installed and f"{wanted}:latest" not in installed:
                    raise RuntimeError(f"model '{wanted}' is not installed in Ollama")
            elif provider == "openrouter":
                if not settings.OPENROUTER_API_KEY:
                    raise RuntimeError("OPENROUTER_API_KEY is not set")
                resp = await client.get(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/key",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                )
                resp.raise_for_status()
            elif provider == "gemini":
                resp = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL_NAME}",
                    params={"key": settings.GEMINI_API_KEY},
                )
                resp.raise_for_status()
            else:
                raise RuntimeError(f"unsupported LLM_PROVIDER '{provider}'")

    # --- Models: loaded once, retried on later cycles if loading failed ---

    async def _load_nllb(self) -> None:
        from app.machine_translation import nllb_service

        await asyncio.to_thread(nllb_service.preload_models)

    async def _load_embedding_model(self) -> None:
        from app.pipeline.embeddings import get_embedding_model

        await asyncio.to_thread(get_embedding_model)

    async def _load_quality_model(self) -> None:
        from app.pipeline.quality import _get_model

        await asyncio.to_thread(_get_model)

    async def _load_complexity_models(self) -> None:
        from app.pipeline import complexity

        if complexity._readability_pipe is None or complexity._lcp_pipe is None:
            # _load_models logs and swallows its own failures, so allow a retry and inspect the result
            complexity._models_loaded = False
            await asyncio.to_thread(complexity._load_models)
        missing = [
            name
            for name, pipe in (("readability", complexity._readability_pipe), ("lcp", complexity._lcp_pipe))
            if pipe is None
        ]
        if missing:
            raise RuntimeError(f"failed to load: {', '.join(missing)} (see logs)")

    async def _load_nltk_punkt(self) -> None:
        import nltk

        try:
            await asyncio.to_thread(nltk.data.find, "tokenizers/punkt")
        except LookupError:
            await asyncio.to_thread(nltk.download, "punkt", quiet=True)
            await asyncio.to_thread(nltk.data.find, "tokenizers/punkt")

    async def check_services(self) -> None:
        await asyncio.gather(
            self._run("db", self._check_db),
            self._run("duckling", self._check_duckling),
            self._run("llm", self._check_llm),
        )

    async def load_models(self) -> None:
        loaders = {
            "nllb": self._load_nllb,
            "embedding_model": self._load_embedding_model,
            "quality_model": self._load_quality_model,
            "complexity_models": self._load_complexity_models,
            "nltk_punkt": self._load_nltk_punkt,
        }
        # Loaded one at a time to keep peak memory down; loaded models are not re-tested
        for name, loader in loaders.items():
            if not self.checks[name].ok:
                if self.checks[name].error == "pending":
                    self.checks[name].error = "loading"
                await self._run(name, loader)

    async def _monitor(self) -> None:
        while True:
            try:
                await self.check_services()
                await self.load_models()
            except Exception:
                logger.exception("Readiness monitor cycle failed")
            await asyncio.sleep(settings.READINESS_CHECK_INTERVAL)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


readiness = Readiness()


async def require_ready() -> None:
    """FastAPI dependency that rejects requests with 503 while any readiness check is failing."""
    if not readiness.is_ready:
        reasons = "; ".join(f"{name}: {error}" for name, error in readiness.failing().items())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready - {reasons}",
            headers={"Retry-After": str(settings.READINESS_CHECK_INTERVAL)},
        )
