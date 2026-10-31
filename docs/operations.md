# Operations and troubleshooting

## Startup and readiness

The FastAPI lifespan starts a background readiness monitor. “Application startup complete” means HTTP serving has started; it does not mean translation models have finished loading.

- `GET /health/live` returns 200 while the process is serving.
- `GET /health` returns 200 only when all tracked components are ready, otherwise 503 with component errors/statuses.
- Translation, detection, document, bucket, and review routes depend on the same readiness state and return 503 with `Retry-After` when it is not ready.

The monitor checks PostgreSQL, Duckling, and the configured LLM provider, then loads NLLB, the embedding model, the quality model, the readability model, and NLTK Punkt sequentially to limit peak memory. Successful local model loads are retained; failed loads are retried. It sleeps `READINESS_CHECK_INTERVAL` (default 20 seconds) between cycles. HTTP dependency checks use `READINESS_CHECK_TIMEOUT` (default 5 seconds).

The LLM readiness probe checks provider/model availability or credentials, not a complete structured translation. A healthy probe does not prove that the selected provider/model supports the output schema.

Database initialization enables the `vector` extension, creates missing tables, and adds missing trust/complexity columns. This startup initialization is not a general versioned migration system.

## Reading logs

SQLAlchemy is configured with `echo=True` in [session.py](../app/db/session.py), so query statements and bound values appear in logs. Application loggers contain cache decisions and routing details, but Uvicorn's default logging configuration may not show their INFO messages; configure application logger levels/handlers when diagnosing cache misses.

| Log pattern | Meaning |
| --- | --- |
| `SELECT 1`, followed by `ROLLBACK` at intervals | Readiness database probe closing its read transaction |
| Text equality / `text_hash`, `LIMIT 1` | L1 exact lookup |
| `normalized_hash`, `LIMIT 1` | L2 normalized lookup |
| `embedding <=> ...`, trust filter, `LIMIT 1` | L3 semantic-cache candidate search |
| `embedding <=> ...`, no trust filter, `LIMIT 3` | RAG example search |
| `INSERT INTO translations` followed by `COMMIT` | Translation record persisted |
| `[cached since ...]` in SQLAlchemy output | Reuse of a compiled SQL statement, not a translation cache hit |

A SQL query log proves that a lookup ran; it does not show the returned candidate distance, acceptance decision, or final prompt. A later read-transaction rollback does not undo an earlier committed translation.

## Why a response is not `semantic_cache`

1. Inspect `data.source`. Exact matches win first, so repeated identical text should usually report `exact_cache`. Normalized matches precede semantic lookup too.
2. Confirm this entry point uses cache reuse. URL-document LLM batches retrieve examples but bypass per-node cache reuse and persistence. Text, bucket nodes, CLI nodes, and non-batched document nodes use the text pipeline.
3. Confirm a candidate exists for the same source/target language pair, is successful, has an embedding, and meets `TRUST_SCORE_THRESHOLD` (default 0.85). A result with a null trust score cannot qualify.
4. Check the nearest candidate's cosine distance against `SEMANTIC_CACHE_MAX_DISTANCE` (default 0.02). High quality score does not imply low retrieval distance: different models and text pairs produce these values.
5. Check entities. L2 rejects incoming entities. L3 permits them when the incoming and cached source entities match by dimension and literal body in source order. Changed numbers/dates or a failed candidate extraction can reject reuse.
6. Check negation differences. L3 compares normalized negation-word sets for English, French, and Spanish. Only one nearest candidate is examined.
7. Check application warnings for embedding/retrieval errors. RAG failures yield no examples and can still be followed by a successful LLM generation.

For a manual check, first translate a sentence and confirm it has sufficient trust, then submit a slight wording variation that preserves numbers and negation. An identical repeat tests L1, not L3. Do not assume an arbitrary paraphrase must pass the deliberately strict distance cutoff. The response source describes where the returned text came from, not whether a vector query ran.

## Authentication and response behavior

Translation, document, bucket, review, brand, and domain APIs use HTTP Basic authentication. `/health`, `/health/live`, and generated documentation are public. The current `/api/v1/debug/check_db` route also lacks authentication and exposes a small database sample; it is not covered by the protected router dependencies.

Text success responses use the `success` / `data` / `error` envelope. Common failures include 401 for authentication, 422 for validation, 503 for readiness, 400 for unsupported pairs, and 502 for translation-engine failure. URL-document errors use 400; individual segment/batch errors can instead retain original text. Consult the generated OpenAPI for each operation's schema.

## Background jobs and review

Poll `GET /api/v1/bucket/{operation_id}` and `GET /api/v1/bucket/{operation_id}/files` for bucket progress. Inspect failure counters and individual file errors even when the operation is `COMPLETED`. Jobs run in-process and are not a durable queue.

`POST /api/v1/review/start` returns 202 and starts one review pass. It has no built-in recurring schedule or status endpoint. See [review behavior](architecture.md#review-and-current-limits) for its selection and update rules.

## Verification

```sh
python -m pytest -q
python -m pytest tests/test_semantic_cache.py tests/test_document_translation.py -q
```

These checks cover local behavior with mocked external boundaries. Live verification additionally needs working PostgreSQL/pgvector, Duckling, loaded models, provider credentials, and a schema-capable LLM. Some existing tests load local NLP dependencies and can be slower on a cold environment.

For documentation-only edits, validate relative links, generate `app.openapi()`, and check that descriptions agree with controller/service code. Historical files under `docs/superpowers` are planning records rather than current runtime guarantees.
