# Translator

A FastAPI translation service with local NLLB-200 inference, configurable LLM providers, PostgreSQL/pgvector caching, and JSON document processing. Supported API language pairs are English ↔ French, Spanish, Arabic, and Chinese (`en` ↔ `fr`, `es`, `ar`, `zh`).

## Translation process

For a text request, the service:

1. Skips non-translatable input and records the skip; otherwise detects the source language and checks the requested language pair.
2. Searches trusted translations in order: **exact → normalized → semantic**. An accepted hit returns immediately.
3. On a miss, builds brand/reusable-unit/domain context and calculates complexity.
4. Uses the LLM for a glossary/keyword match or complexity at or above `COMPLEXITY_THRESHOLD` (default **28**). Other inputs use `facebook/nllb-200-3.3B`.
5. For LLM translation, retrieves similar stored translations as prompt examples (RAG).
6. Scores the result with `intfloat/multilingual-e5-large` and saves the translation, metadata, source hashes, and source embedding.

**Semantic cache reuse and RAG are separate operations.** A cache hit returns an existing translation with `source: "semantic_cache"`. RAG provides examples to a new LLM generation, whose source remains `"llm"`. Both NLLB and LLM results saved by the text pipeline can become cache candidates.

## Entry points

| Entry point | Processing |
| --- | --- |
| `POST /api/v1/translate` | Full text pipeline, including cache lookup and result persistence |
| `POST /api/v1/document` | Fetch JSON, build an AST, send simple nodes through the text pipeline and complex/brand-matched nodes through one LLM batch |
| `POST /api/v1/bucket` | Start background S3/MinIO JSON processing; reuse unchanged files or translate each node through the text pipeline |
| `POST /api/v1/detect` | Source-language detection |
| `POST /api/v1/review/start` | Start one background review of stored translations |

Document LLM batches retrieve semantic examples but currently bypass per-node cache reuse, quality scoring, and persistence. Document/bucket segment failures retain original text; successful document structure validation does not mean every segment was translated.

## Run locally

Use Python 3.10 or newer and install the dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`: configure PostgreSQL credentials, Duckling, API credentials, and your LLM provider/model. The selected LLM must support native JSON-schema structured output. `GEMINI_API_KEY` must be present in the configuration even for other providers; it may be empty when unused.

Start the bundled database and entity parser, then the API:

```sh
docker compose up -d db duckling
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

For this host-run setup, use `POSTGRES_HOST=127.0.0.1` and `DUCKLING_URL=http://127.0.0.1:8001/parse`. Set a nonempty database password that matches the database container. When running the API in Docker instead, use `POSTGRES_HOST=db` and an LLM address reachable from that container.

The server starts before model loading completes. Wait for `GET /health` to return 200 before translating; gated routes return 503 while dependencies are unavailable. Initial model downloads can take time and substantial memory. `GET /health/live` only checks that the process is serving.

Interactive API documentation is at `/docs`, with ReDoc at `/redoc` and the generated contract at `/openapi.json`. Translation endpoints require HTTP Basic authentication:

```sh
curl -u "$API_USERNAME:$API_PASSWORD" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world","source_lang":"en","target_lang":"fr"}' \
  http://127.0.0.1:8000/api/v1/translate
```

Set those shell variables to your configured API credentials; `.env` is loaded by the application, not automatically by the shell. Text responses use `{ "success": true, "data": { ... }, "error": null }`. The `data.source` value is `llm`, `machine_translation`, `exact_cache`, `normalized_cache`, or `semantic_cache`; skipped input has a null source.

## Configuration defaults

| Setting | Default | Purpose |
| --- | --- | --- |
| `COMPLEXITY_THRESHOLD` | `28` | Minimum score for complexity-based LLM routing |
| `COMPLEXITY_LLM_WINDOW` | `8` | Near-threshold window for an LLM complexity rating |
| `TRUST_SCORE_THRESHOLD` | `0.85` | Minimum stored trust for cache reuse |
| `SEMANTIC_CACHE_MAX_DISTANCE` | `0.02` | Maximum cosine distance for semantic reuse |
| `READINESS_CHECK_INTERVAL` | `20` | Seconds between readiness cycles |
| `READINESS_CHECK_TIMEOUT` | `5.0` | HTTP readiness-check timeout in seconds |

`.env` can override these defaults. LLM providers are `gemini`, `ollama`, and `openrouter`. Model loading is managed by readiness; `IS_DYNAMIC_LOADING` is not a current setting.

## Documentation and checks

- [Architecture and design](docs/architecture.md): components, routing, cache rules, RAG, document/bucket behavior, and implementation limits.
- [Operations and troubleshooting](docs/operations.md): readiness, logs, cache diagnosis, review, and verification.
- [Documentation index](docs/README.md): current guides and historical design records.

Run the local test suite with `python -m pytest -q`. Tests use dependency doubles for many external boundaries; passing tests do not establish live provider or database availability.
