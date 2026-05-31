# Translator Module

We are building a highly scalable, Google Translation API-compatible service. This service provides intelligent translation for multiple language pairs, with built-in quality estimation, database caching, brand integration, and an offline reviewer system.

## 🚀 Key Features
- **Intelligent Pre-processing:** Automatically skips translation for emojis, links, numbers, and HTML tags.
- **Brand Name Protection:** Preserves your exact brand name across translations by using variable placeholder injection (`{{BRAND_NAME}}`).
- **Language Detection:** Uses `langdetect` to verify source languages.
- **Complexity Routing:** Computes text readability and complexity. Simple text uses fast local models; complex text leverages LLM integration for contextual and nuanced translations.
- **Machine Translation:** Powered by Hugging Face `MarianMT` (Helsinki-NLP) models.
- **LLM Translation Integration:** Automatically routes highly complex or context-heavy JSON structures to the LLM backend.
- **Quality Estimation:** Scores every translation natively using cross-lingual semantic similarity (`sentence-transformers`).
- **Caching Layer:** Exact translations (scoring >= 85%) are automatically cached and retrieved from PostgreSQL to save compute.
- **S3 Bucket Processing:** Asynchronously translates entire directories of JSON documents stored in AWS S3 or MinIO.
- **Offline Reviewer Module:** Automatically scans the translation cache database in the background to fix translations with high complexity and low trust scores using the LLM backend.

---

## 🏗️ Architecture Pipeline

Once we receive an input text via the API, it passes through the following strict, step-by-step pipeline:

### 1. Verification Step
Before invoking any heavy translation models, the input is validated and verified:
- **Translatability Check:** Checks if the input is actually translatable (Links, Emojis, Numbers, Currency Symbols, HTML tags, etc.).
- **Source/Target Compatibility:** Automatically detects the input language using `langdetect` to verify it matches the requested source language.
- **Language Supported:** Validates that the requested source and target languages are within our supported pairs.
- **Cache Check:** Queries the PostgreSQL database. If this exact text was translated before with a high trust score (>=85%), we return the cached result immediately.

### 2. Context Integration Step
- **Brand Context:** If a `brand_uuid` is supplied, the pipeline extracts the brand's industry, tone, target audience, and glossary.
- **Brand Protection:** The brand's exact name is wrapped in a `{{BRAND_NAME}}` placeholder so the translation engine avoids localizing the brand name.

### 3. Complexity Step
- If the text is valid and not cached, we calculate a complexity score from 1-100. This is done using a mix of NLP heuristics (token length, vocabulary diversity, and Flesch reading ease). 

### 4. Translation Step
- **Simple Inputs (Score < 50):** The text is passed to our local, fast Machine Translation model (`MarianMT` / `Helsinki-NLP`).
- **Complex Inputs (Score >= 50):** The text is routed through an LLM sequence using structured generation prompts that preserve structural integrity (e.g. JSON Arrays) and follow your specific brand guidelines.

### 5. Quality Estimation & Return Step
- **Quality Scoring:** The generated translation is scored alongside the source text using a reference-free, cross-lingual semantic similarity model. This gives us a confidence/quality score between 0.0 and 1.0.
- **Database Storage:** The original text, translated text, detected languages, translation time, and the quality score are all stored in the database.

### 6. Reviewer Module
- An asynchronous backend process (`/api/v1/review/start`) regularly audits the database. Any cached translation that falls below an 85% trust score while having a high complexity score is sent back through an LLM `fix_translation` prompt to automatically improve the cache over time.

---

## 🛠️ Configuration

You can control how the heavy machine learning models are loaded via the `.env` file:

- `IS_DYNAMIC_LOADING=true` (Default): Models are loaded into RAM *on-demand* the first time a specific language pair is requested. This allows the app to start up instantly.
- `IS_DYNAMIC_LOADING=false`: The application will download and load **all** supported language models during startup. *(Note: This can take several minutes and gigabytes of RAM during the first boot, but ensures zero latency on the first request).*
