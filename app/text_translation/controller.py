import time
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession

from app.text_translation.service import TranslationService, ReusableUnitService
from app.brands.service import BrandService
from app.domains.service import DomainService
from app.pipeline import (
    is_translatable,
    is_source_target_compatible,
    is_in_supported_languages,
    calculate_complexity_score,
    translate,
    score_translation,
)
from app.text_translation.schemas import TranslationRequest, DetectionRequest
from app.llms import retrieve_rag_examples
from app.core.config import settings
from app.pipeline.reviewer import review_translations_batch

logger = logging.getLogger(__name__)

class TextTranslationController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.translation_svc = TranslationService(db)
        self.reusable_unit_svc = ReusableUnitService(db)
        self.brand_svc = BrandService(db)
        self.domain_svc = DomainService(db)

    async def _compile_context(
        self, brand_uuid: str | None, domain_name: str | None, text: str, target_lang: str
    ) -> tuple[dict, dict]:
        brand_context = await self.brand_svc.get_brand_context(brand_uuid)
        unit_glossary = await self.reusable_unit_svc.build_glossary_from_units(text, target_lang)
        if unit_glossary:
            existing_glossary = brand_context.get("glossary", {})
            existing_glossary.update(unit_glossary)
            brand_context["glossary"] = existing_glossary

        domain_rules = {}
        if domain_name:
            domain = await self.domain_svc.get_by_name(domain_name)
            if domain and domain.rules:
                domain_rules = domain.rules
        return brand_context, domain_rules

    async def _execute_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        complexity_score: int,
        brand_context: dict,
        domain_rules: dict,
        similar_examples: list,
    ) -> tuple[str | None, bool, str | None]:
        brand_name = brand_context.get("name") if brand_context else None
        placeholder = "{{BRAND_NAME}}"
        
        if brand_name:
            pattern = re.compile(rf"\b{re.escape(brand_name)}\b", re.IGNORECASE)
            text = pattern.sub(placeholder, text)

        try:
            translation_text = await translate(
                text,
                source_lang,
                target_lang,
                complexity_score,
                brand_context,
                domain_rules,
                similar_examples=similar_examples,
            )
            if brand_name and translation_text:
                translation_text = translation_text.replace(placeholder, brand_name)
            return translation_text, True, None
        except NotImplementedError as e:
            raise e
        except Exception as e:
            return None, False, str(e)

    def _get_quality_score(self, text: str, translation_text: str | None, is_successed: bool) -> float | None:
        if not (is_successed and translation_text):
            return None
        try:
            return score_translation(text, translation_text)
        except Exception as e:
            logger.warning("Quality scoring failed: %s", e)
            return None

    async def translate_text(
        self,
        payload: TranslationRequest,
        brand_uuid: str | None = None,
        domain_name: str | None = None,
        filename: str | None = None,
        property_name: str | None = None,
    ) -> dict:

        source_lang = payload.source_lang
        target_lang = payload.target_lang
        text = payload.text

        start_time = time.time()

        if not is_translatable(text):
            translation_time = time.time() - start_time
            await self.translation_svc.create(
                value=text,
                language=source_lang,
                translation=text,
                translation_language=target_lang,
                is_successed=True,
                notes="Skipped: Input is not translatable (emoji/link/number/HTML)",
                translation_time=translation_time,
                input_size=len(text),
                output_size=len(text),
                filename=filename,
                property=property_name,
            )
            return {
                "message": "Translation skipped: Input is not translatable (emoji/link/number/HTML)",
                "translation": text,
                "skipped": True,
                "reason": "not_translatable",
            }

        compat = is_source_target_compatible(text, source_lang)
        detected_input_lang = compat["detected_lang"]

        if not is_in_supported_languages(source_lang, target_lang):
            return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

        cached = await self.translation_svc.find_cached(text, source_lang, target_lang)
        if cached and cached.trust_score is not None and cached.trust_score >= 0.85:
            complexity_score = calculate_complexity_score(text)
            return {
                "message": "Translation retrieved from cache",
                "translation": cached.translation,
                "cached": True,
                "score": cached.score,
                "complexity_score": complexity_score,
                "detected_input_lang": detected_input_lang or cached.detected_input_lang,
            }

        brand_context, domain_rules = await self._compile_context(brand_uuid, domain_name, text, target_lang)

        complexity_score = calculate_complexity_score(text)

        similar_examples = []
        if complexity_score >= settings.COMPLEXITY_THRESHOLD:
            similar_examples = await retrieve_rag_examples(
                translation_svc=self.translation_svc,
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                limit=3,
            )

        try:
            translation_text, is_successed, notes = await self._execute_translation(
                text, source_lang, target_lang, complexity_score, brand_context, domain_rules, similar_examples
            )
        except NotImplementedError as e:
            translation_time = time.time() - start_time
            await self.translation_svc.create(
                value=text,
                language=source_lang,
                translation=None,
                translation_language=target_lang,
                detected_input_lang=detected_input_lang,
                is_successed=False,
                notes=str(e),
                translation_time=translation_time,
                input_size=len(text),
                output_size=0,
                filename=filename,
                property=property_name,
            )
            return {"error": str(e), "complexity_score": complexity_score}

        translation_time_elapsed = time.time() - start_time
        comet_score = self._get_quality_score(text, translation_text, is_successed)

        await self.translation_svc.save_with_cache_fields(
            value=text,
            language=source_lang,
            translation=translation_text,
            translation_language=target_lang,
            detected_input_lang=detected_input_lang,
            detected_output_lang=target_lang,
            is_successed=is_successed,
            score=comet_score,
            notes=notes,
            translation_time=translation_time_elapsed,
            input_size=len(text),
            output_size=len(translation_text) if translation_text else 0,
            size_difference=(
                (len(translation_text) - len(text)) / len(text) * 100
                if translation_text
                else None
            ),
            filename=filename,
            property=property_name,
        )

        return {
            "message": "Translation completed" if is_successed else f"Translation failed: {notes}",
            "translation": translation_text,
            "score": comet_score,
            "complexity_score": complexity_score,
            "detected_input_lang": detected_input_lang,
        }

    def detect_language(self, payload: DetectionRequest) -> dict:
        compat = is_source_target_compatible(payload.text, "")
        return {"detected_language": compat["detected_lang"]}

    async def run_review(self) -> None:
        await review_translations_batch(self.db)



