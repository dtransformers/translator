import asyncio
import csv
import hashlib
import json
import logging
import os
import sys
from typing import Any

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.future import select
from app.db.session import async_session, init_db
from app.domains.models import Domain
from app.brands.models import Brand
from app.translations.models import Translation, ReusableUnit
from app.pipeline.normalization import abstract_entities, canonicalize_text, semantic_fingerprint
from app.pipeline.embeddings import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_domains(session):
    logger.info("Starting domains seeding...")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    json_path = os.path.join(base_dir, "pipelines", "data", "domains", "domains.json")
    
    if not os.path.exists(json_path):
        logger.warning(f"Domains JSON file not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both object formats: dict of dicts or list of dicts (with name inside)
    # The current domains.json is a list of dicts now after user modification!
    # Let's inspect the format dynamically.
    if isinstance(data, list):
        items = {}
        for item in data:
            name = item.get("name")
            if name:
                items[name] = item
    else:
        items = data

    for name, info in items.items():
        if name == "brand_voice" or "rules" not in info:
            continue
        
        # Check if exists
        result = await session.execute(select(Domain).where(Domain.name == name))
        db_domain = result.scalars().first()
        
        if db_domain:
            db_domain.description = info.get("description")
            db_domain.content_types = info.get("content_types")
            db_domain.rules = info.get("rules", {})
            logger.info(f"Updated domain: {name}")
        else:
            db_domain = Domain(
                name=name,
                description=info.get("description"),
                content_types=info.get("content_types"),
                rules=info.get("rules", {})
            )
            session.add(db_domain)
            logger.info(f"Created domain: {name}")

    await session.commit()
    logger.info("Domains seeding completed.")

async def seed_brands(session):
    logger.info("Starting brands seeding...")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    json_path = os.path.join(base_dir, "pipelines", "data", "brands", "brands.json")
    
    if not os.path.exists(json_path):
        logger.warning(f"Brands JSON file not found at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        brand_data = json.load(f)

    name = brand_data.get("name")
    if not name:
        logger.error("Brand name not found in JSON.")
        return

    # Check if brand exists
    result = await session.execute(select(Brand).where(Brand.name == name))
    db_brand = result.scalars().first()

    industry = brand_data.get("industry")
    audience = brand_data.get("audience")
    tone = brand_data.get("tone")
    summary = brand_data.get("description")
    keywords = brand_data.get("domain_focus", [])
    
    # Map glossary source terms as entities
    glossary = brand_data.get("glossary", [])
    entities = [item.get("en") for item in glossary if item.get("en")]

    if db_brand:
        db_brand.industry = industry
        db_brand.audience = audience
        db_brand.tone = tone
        db_brand.summary = summary
        db_brand.keywords = keywords
        db_brand.entities = entities
        logger.info(f"Updated brand: {name} (UUID: {db_brand.uuid})")
    else:
        db_brand = Brand(
            name=name,
            industry=industry,
            audience=audience,
            tone=tone,
            summary=summary,
            keywords=keywords,
            entities=entities
        )
        session.add(db_brand)
        logger.info(f"Created brand: {name}")

    await session.commit()
    
    # Seed glossary items as ReusableUnits
    logger.info("Seeding brand glossary as ReusableUnits...")
    for item in glossary:
        source_text = item.get("en")
        translation = item.get("ar") # Or target language from the glossary keys
        if not source_text or not translation:
            continue
        
        # Check if reusable unit already exists
        result = await session.execute(
            select(ReusableUnit).where(
                ReusableUnit.source_text == source_text,
                ReusableUnit.target_language == "ar", # Defaulting to Arabic target for this guide
                ReusableUnit.unit_type == "entity"
            )
        )
        unit = result.scalars().first()
        if not unit:
            unit = ReusableUnit(
                source_text=source_text,
                target_language="ar",
                translation=translation,
                unit_type="entity"
            )
            session.add(unit)
            logger.info(f"Created ReusableUnit: {source_text} -> {translation}")
            
    await session.commit()
    logger.info("Brands seeding completed.")

async def seed_translations(session):
    logger.info("Starting translations seeding...")
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    csv_path = os.path.join(base_dir, "pipelines", "data", "translations", "translation_operations_202605251552.csv")
    
    if not os.path.exists(csv_path):
        logger.warning(f"Translations CSV file not found at {csv_path}")
        return

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Found {len(rows)} translation rows to import.")
    
    # Helper parser for boolean values
    def parse_bool(val: str) -> bool:
        return val.lower() in ("true", "1", "yes")

    # Helper parser for float/int values
    def parse_float(val: str) -> float | None:
        try:
            return float(val) if val else None
        except ValueError:
            return None

    def parse_int(val: str) -> int | None:
        try:
            return int(val) if val else None
        except ValueError:
            return None

    from datetime import datetime
    def parse_datetime(val: str) -> datetime | None:
        if not val:
            return None
        try:
            cleaned = val.strip()
            if " +" in cleaned:
                cleaned = cleaned.replace(" +", "+")
            elif " -" in cleaned:
                cleaned = cleaned.replace(" -", "-")
            return datetime.fromisoformat(cleaned)
        except Exception:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val.strip(), fmt)
                except Exception:
                    continue
            return None

    # Load sentence-transformers model eagerly to avoid threads issue
    get_embedding("warmup")

    batch_size = 50
    for idx in range(0, len(rows), batch_size):
        batch = rows[idx : idx + batch_size]
        logger.info(f"Processing translations batch {idx//batch_size + 1}...")
        
        for row in batch:
            val = row.get("value")
            lang = row.get("language")
            trans_lang = row.get("translation_language")
            
            if not val or not lang or not trans_lang:
                continue

            # Check if this translation already exists in DB (to prevent duplicates)
            result = await session.execute(
                select(Translation).where(
                    Translation.value == val,
                    Translation.language == lang,
                    Translation.translation_language == trans_lang
                )
            )
            existing = result.scalars().first()
            if existing:
                continue

            # Parse success
            is_successed = parse_bool(row.get("is_successed", "false"))
            
            # Compute cache fields
            exact_hash = hashlib.sha256(val.encode("utf-8")).hexdigest()
            
            # Since entity abstraction makes HTTP calls to Duckling, let's wrap it in try/except 
            # and default to the value itself if Duckling is not responding or fails.
            try:
                abstracted_text, _ = await abstract_entities(val, language=lang)
            except Exception:
                abstracted_text = val
                
            normalized_text = canonicalize_text(abstracted_text)
            norm_hash = semantic_fingerprint(normalized_text)
            
            try:
                emb = get_embedding(normalized_text)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for row: {e}")
                emb = None

            # Map date/time strings if present
            # SQL Alchemy handles timezone-aware timestamps, but let's parse strings safely
            # or let SQLAlchemy set defaults if format mismatches.
            db_trans = Translation(
                filename=row.get("filename"),
                property=row.get("property"),
                value=val,
                language=lang,
                translation=row.get("translation"),
                translation_language=trans_lang,
                detected_input_lang=row.get("detected_input_lang"),
                detected_output_lang=row.get("detected_output_lang"),
                is_successed=is_successed,
                score=parse_float(row.get("score")),
                is_approved=parse_bool(row.get("is_approved", "false")),
                is_verified=parse_bool(row.get("is_verified", "false")),
                verified_at=parse_datetime(row.get("verified_at")),
                notes=row.get("notes"),
                translation_time=parse_float(row.get("translation_time")),
                input_size=parse_int(row.get("input_size")),
                output_size=parse_int(row.get("output_size")),
                size_difference=parse_float(row.get("size_difference")),
                text_hash=exact_hash,
                normalized_text=normalized_text,
                normalized_hash=norm_hash,
                embedding=emb,
                segment_type="Sentence Unit" if len(val.split()) > 3 else "Atomic Element",
                created_at=parse_datetime(row.get("created_at")),
                updated_at=parse_datetime(row.get("updated_at"))
            )
            session.add(db_trans)
            
        await session.commit()

    logger.info("Translations seeding completed.")

async def main():
    await init_db()
    async with async_session() as session:
        await seed_domains(session)
        await seed_brands(session)
        await seed_translations(session)

if __name__ == "__main__":
    asyncio.run(main())
