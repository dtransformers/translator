# End-to-End Testing for CLI and Endpoints Design

## Goal
Implement a robust, fast, and comprehensive end-to-end (E2E) test suite (`tests/test_e2e.py`) to verify the behavior of both the translation CLI (`scripts/translate_json.py`) and the application API endpoints under a mocked/controlled environment.

## Design

### 1. CLI E2E Tests
We will verify the Typer CLI commands using `typer.testing.CliRunner`.

*   **`init` command**:
    *   Tests that all startup dependency checks (Database, Duckling, LLM, translation/embedding/quality models, NLTK tokenizer) are triggered.
    *   Mocks the checks at the boundary level:
        *   Database: `init_db()` and `engine.begin()`.
        *   Duckling: `httpx.AsyncClient.post()` response.
        *   LLM: `get_llm().ainvoke()`.
        *   Models: `preload_models()`, `get_embedding_model()`, `_get_model()`, and `nltk.download()`.
    *   Verifies correct console output and exit code (0 for success, non-zero on failure).
*   **`translate` command**:
    *   Takes an input file, output file, target language, and optional arguments.
    *   Uses pytest's `tmp_path` fixture to manage test-isolated files.
    *   Mocks the main translation controller (`TextTranslationController.translate_text`) to return a simulated response immediately.
    *   Verifies that the CLI processes the AST, executes translations for translatable nodes, verifies AST compatibility, and writes the translated JSON back to the destination.
    *   Verifies that errors (such as a missing input file) are handled gracefully with the correct exit code.

### 2. API Endpoints E2E Tests
We will verify the FastAPI endpoint paths using `httpx.AsyncClient` along with the valid authentication header (`TEST_AUTH` from `tests/conftest.py`).

*   **Health Check (`/health`)**:
    *   Verifies that the health endpoint checks all components and returns a 200 status code.
*   **Text Translation (`/api/v1/translate`)**:
    *   Verifies request parameter validation, authentication, and successful translation routing.
    *   Mocks downstream translation services to avoid model downloads.
*   **Document Translation (`/api/v1/document`)**:
    *   Verifies JSON fetching, AST parsing, translation, and AST verification.
*   **Brand CRUD (`/api/v1/brands`)**:
    *   Tests POST, GET, PUT, and DELETE operations.
*   **Domain CRUD (`/api/v1/domains`)**:
    *   Tests POST, GET, PUT, and DELETE operations.
*   **Reviewer Module (`/api/v1/review/start`)**:
    *   Verifies triggering the background review process and returning 202 Accepted.

## Proposed Code Structure
We will create a single new file: `tests/test_e2e.py`. All tests will run inside `pytest` using the conda environment `translator`.
