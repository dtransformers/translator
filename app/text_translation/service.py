import hashlib
import asyncio
import logging
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from app.text_translation.models import Translation, ReusableUnit
from app.text_translation.repository import TranslationRepository, ReusableUnitRepository
from app.pipeline.normalization import canonicalize_text, abstract_entities
from app.pipeline.embeddings import get_embedding

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self, db: AsyncSession):
        self._repo = TranslationRepository(db)
        self._db = db

    async def create(self, **kwargs) -> Translation:
        return await self._repo.create(**kwargs)

    async def get_by_id(self, translation_id: int) -> Translation | None:
        return await self._repo.get_by_id(translation_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Translation]:
        return await self._repo.get_all(skip=skip, limit=limit)

    async def update(self, translation_id: int, **kwargs) -> Translation | None:
        return await self._repo.update(translation_id, **kwargs)

    async def find_cached(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Translation | None:
        """
        Multi-tier cache lookup:
          L1 — exact text / SHA-256 hash match
          L2 — normalized + entity-abstracted hash match
          L3 — semantic vector similarity (pgvector cosine distance)

        Returns the best matching approved Translation, or None.
        """
        if not text:
            return None

        # --- L1: Exact match ---
        exact_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        l1_query = (
            select(Translation)
            .where(
                or_(Translation.value == text, Translation.text_hash == exact_hash),
                Translation.language == source_lang,
                Translation.translation_language == target_lang,
                Translation.is_successed == True,  # noqa: E712
            )
            .order_by(Translation.is_approved.desc())
        )
        l1_result = await self._db.execute(l1_query)
        l1_hit = l1_result.scalars().first()
        if l1_hit:
            logger.info("L1 Cache Hit (exact) for: %s", text[:30])
            return l1_hit

        # --- L2: Normalized hash ---
        abstracted_text, entities = await abstract_entities(text, language=source_lang)
        normalized_text = canonicalize_text(abstracted_text)
        norm_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

        l2_query = (
            select(Translation)
            .where(
                Translation.normalized_hash == norm_hash,
                Translation.language == source_lang,
                Translation.translation_language == target_lang,
                Translation.is_successed == True,  # noqa: E712
            )
            .order_by(Translation.is_approved.desc())
        )
        l2_result = await self._db.execute(l2_query)
        l2_hit = l2_result.scalars().first()
        if l2_hit:
            if not entities:
                logger.info("L2 Cache Hit (normalized) for: %s", text[:30])
                return l2_hit
            else:
                logger.info(
                    "L2 normalized match found but %d entities present — "
                    "cannot reuse cached translation, re-translating",
                    len(entities),
                )
        SEMANTIC_DISTANCE_THRESHOLD = 0.08
        try:
            query_embedding = await asyncio.to_thread(get_embedding, normalized_text)
            l3_query = (
                select(
                    Translation,
                    Translation.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(
                    Translation.language == source_lang,
                    Translation.translation_language == target_lang,
                    Translation.is_successed == True,  
                    Translation.embedding != None, 
                )
                .order_by("distance")
                .limit(1)
            )
            l3_result = await self._db.execute(l3_query)
            l3_row = l3_result.first()

            if l3_row is not None:
                l3_hit, distance = l3_row[0], l3_row[1]
                similarity = 1.0 - distance
                logger.info(
                    "L3 Semantic candidate for '%s': distance=%.4f, similarity=%.4f",
                    text[:30], distance, similarity,
                )
                if distance <= SEMANTIC_DISTANCE_THRESHOLD:
                    if entities:
                        logger.info(
                            "L3 semantic match (sim=%.4f) but %d entities "
                            "present — cannot reuse, re-translating",
                            similarity, len(entities),
                        )
                    else:
                        logger.info(
                            "L3 Cache Hit (semantic, sim=%.4f) for: %s",
                            similarity, text[:30],
                        )
                        return l3_hit
                else:
                    logger.info(
                        "L3 below threshold (sim=%.4f < 0.92), skipping cache",
                        similarity,
                    )
        except Exception as e:
            logger.warning("L3 Semantic cache failed: %s", e)

        return None

    async def save_with_cache_fields(self, **kwargs) -> Translation:
        text = kwargs.get("value")
        source_lang = kwargs.get("language")

        if text and source_lang:
            exact_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            abstracted_text, _ = await abstract_entities(text, language=source_lang)
            normalized_text = canonicalize_text(abstracted_text)
            norm_hash = hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

            try:
                emb = await asyncio.to_thread(get_embedding, normalized_text)
            except Exception:
                emb = None

            kwargs["text_hash"] = exact_hash
            kwargs["normalized_text"] = normalized_text
            kwargs["normalized_hash"] = norm_hash
            kwargs["embedding"] = emb

        return await self._repo.create(**kwargs)

    async def retrieve_similar_translations(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        limit: int = 3,
        max_distance: float = 0.4,
    ) -> list[Translation]:
        """
        Retrieve up to `limit` successful translations that are semantically
        similar to the normalized input text (cosine distance <= max_distance).
        """
        if not text:
            return []

        abstracted_text, _ = await abstract_entities(text, language=source_lang)
        normalized_text = canonicalize_text(abstracted_text)

        try:
            query_embedding = await asyncio.to_thread(get_embedding, normalized_text)
            query = (
                select(
                    Translation,
                    Translation.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .where(
                    Translation.language == source_lang,
                    Translation.translation_language == target_lang,
                    Translation.is_successed == True,
                    Translation.embedding != None,
                )
                .order_by("distance")
                .limit(limit)
            )
            result = await self._db.execute(query)
            rows = result.all()

            similar_examples = []
            for row in rows:
                translation_record, distance = row[0], row[1]
                if distance <= max_distance:
                    similar_examples.append(translation_record)

            return similar_examples
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)
            return []


class ReusableUnitService:
    def __init__(self, db: AsyncSession):
        self._repo = ReusableUnitRepository(db)
        self._db = db

    async def create(
        self,
        source_text: str,
        target_language: str,
        translation: str,
        unit_type: str,
    ) -> ReusableUnit:
        return await self._repo.create(
            source_text=source_text,
            target_language=target_language,
            translation=translation,
            unit_type=unit_type
        )

    async def find_reusable_units(
        self,
        source_text: str,
        target_language: str,
    ) -> list[ReusableUnit]:
        all_units = await self._repo.list_by_target_language(target_language)
        return [u for u in all_units if u.source_text.lower() in source_text.lower()]

    async def get_all_reusable_units(
        self,
        target_language: str | None = None,
    ) -> list[ReusableUnit]:
        return await self._repo.list_by_target_language(target_language)

    async def delete_reusable_unit(self, unit_id: int) -> bool:
        unit = await self._repo.get_by_id(unit_id)
        if not unit:
            return False
        await self._repo.delete(unit)
        return True

    async def build_glossary_from_units(
        self,
        source_text: str,
        target_language: str,
    ) -> dict[str, str]:
        units = await self.find_reusable_units(source_text, target_language)
        return {cast(str, u.source_text): cast(str, u.translation) for u in units}
