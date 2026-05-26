"""
TranslationService — the single public interface for all Translation entity operations.

External modules (controllers, pipeline, endpoints) must use this service.
Never import TranslationRepository directly outside this module.
"""

import hashlib
import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from app.translations.models import Translation, ReusableUnit
from app.translations.repository import TranslationRepository
from app.pipeline.normalization import canonicalize_text, abstract_entities, semantic_fingerprint
from app.pipeline.embeddings import get_embedding

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Service layer for the Translation entity.

    Encapsulates all CRUD, caching, and reusable-unit operations.
    The repository is internal — only this service may call it.
    """

    def __init__(self, db: AsyncSession):
        self._repo = TranslationRepository(db)
        self._db = db

    # ------------------------------------------------------------------ #
    #  CRUD
    # ------------------------------------------------------------------ #

    async def create(self, **kwargs) -> Translation:
        """Create a new translation record."""
        return await self._repo.create_translation(**kwargs)

    async def get_by_id(self, translation_id: int) -> Translation | None:
        """Get a single translation by primary key."""
        return await self._repo.get_translation_by_id(translation_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Translation]:
        """Get a paginated list of translations."""
        return await self._repo.get_all_translations(skip=skip, limit=limit)

    async def update(self, translation_id: int, **kwargs) -> Translation | None:
        """Update an existing translation record."""
        return await self._repo.update_translation(translation_id, **kwargs)

    # ------------------------------------------------------------------ #
    #  Multi-tier Cache Lookup
    # ------------------------------------------------------------------ #

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
        norm_hash = semantic_fingerprint(normalized_text)

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
            norm_hash = semantic_fingerprint(normalized_text)

            try:
                emb = await asyncio.to_thread(get_embedding, normalized_text)
            except Exception:
                emb = None

            kwargs["text_hash"] = exact_hash
            kwargs["normalized_text"] = normalized_text
            kwargs["normalized_hash"] = norm_hash
            kwargs["embedding"] = emb

        return await self._repo.create_translation(**kwargs)



    async def create_reusable_unit(
        self,
        source_text: str,
        target_language: str,
        translation: str,
        unit_type: str,
    ) -> ReusableUnit:
        unit = ReusableUnit(
            source_text=source_text,
            target_language=target_language,
            translation=translation,
            unit_type=unit_type,
        )
        self._db.add(unit)
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def find_reusable_units(
        self,
        source_text: str,
        target_language: str,
    ) -> list[ReusableUnit]:

        query = select(ReusableUnit).where(
            ReusableUnit.target_language == target_language,
        )
        result = await self._db.execute(query)
        all_units = result.scalars().all()

        return [u for u in all_units if u.source_text.lower() in source_text.lower()]

    async def get_all_reusable_units(
        self,
        target_language: str | None = None,
    ) -> list[ReusableUnit]:
        query = select(ReusableUnit)
        if target_language:
            query = query.where(ReusableUnit.target_language == target_language)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def delete_reusable_unit(self, unit_id: int) -> bool:
        result = await self._db.execute(
            select(ReusableUnit).where(ReusableUnit.id == unit_id)
        )
        unit = result.scalars().first()
        if not unit:
            return False
        await self._db.delete(unit)
        await self._db.commit()
        return True

    async def build_glossary_from_units(
        self,
        source_text: str,
        target_language: str,
    ) -> dict[str, str]:

        units = await self.find_reusable_units(source_text, target_language)
        return {u.source_text: u.translation for u in units}

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
