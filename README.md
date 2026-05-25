# Translator Module

We are building a highly scalable, Google Translation API-compatible service. This service provides intelligent translation for multiple language pairs, with built-in quality estimation, database caching, and input complexity routing.

## 🚀 Key Features
- **Intelligent Pre-processing:** Automatically skips translation for emojis, links, numbers, and HTML tags.
- **Language Detection:** Uses `langdetect` to verify source languages.
- **Complexity Routing:** Computes text readability and complexity (1-100) before translation.
- **Machine Translation:** Powered by Hugging Face `MarianMT` (Helsinki-NLP) models.
- **Quality Estimation:** Scores every translation natively using cross-lingual semantic similarity (`sentence-transformers`).
- **Caching Layer:** Exact translations are automatically cached and retrieved from PostgreSQL to save compute.

---

## 🏗️ Architecture Pipeline

Once we receive an input text via the API, it passes through the following strict, step-by-step pipeline:

### 1. Verification Step
Before invoking any heavy translation models, the input is validated and verified:
- **IsTheInputTranslizable:** Checks if the input is actually translatable (Links, Emojis, Numbers, Currency Symbols, HTML tags, etc.). If it consists solely of untranslatable elements, we skip translation, return the original text, and save the attempt.
- **IsTheInputSourceTargetCompatible:** Automatically detects the input language using `langdetect` to verify it matches the requested source language.
- **IsTheInputInSupportedLanguages:** Validates that the requested source and target languages are within our supported pairs (e.g., `en <-> fr`, `en <-> ar`, `en <-> es`, `en <-> zh`).
- **IsTheInputHasTranslationCache:** Queries the PostgreSQL database. If this exact text and target language were successfully translated before, we return the cached result immediately, skipping the rest of the pipeline.

### 2. Complexity Step
- **IsTheInputTransibleUsingMT:** If the text is valid and not cached, we calculate a complexity score from 1-100. This is done using a mix of NLP heuristics (token length, vocabulary diversity, and Flesch reading ease). 

### 3. Translation Step
- **Simple Inputs (Score < 50):** The text is passed to our local, fast Machine Translation model (`MarianMT` / `Helsinki-NLP`).
- **Complex Inputs (Score >= 50):** If the input is deemed too complex, the pipeline will halt and throw a `"Not ready yet for translation"` error, preventing low-quality or hallucinated outputs from smaller models. *(Note: Support for Large MT models for complex text is planned for the future).*

### 4. Quality Estimation & Return Step
- **Quality Scoring:** The generated translation is scored alongside the source text using a reference-free, cross-lingual semantic similarity model. This gives us a confidence/quality score between 0.0 and 1.0.
- **Database Storage:** The original text, the translated text, detected languages, translation time, and the quality score are all stored in the database. This acts as both an analytics log and the cache layer for future requests.

---

## 🛠️ Configuration

You can control how the heavy machine learning models are loaded via the `.env` file:

- `IS_DYNAMIC_LOADING=true` (Default): Models are loaded into RAM *on-demand* the first time a specific language pair is requested. This allows the app to start up instantly.
- `IS_DYNAMIC_LOADING=false`: The application will download and load **all** supported language models during startup. *(Note: This can take several minutes and gigabytes of RAM during the first boot, but ensures zero latency on the first request).*
