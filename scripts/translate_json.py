"""
Translation CLI — translate JSON files via the core pipeline.

Usage:
    translator init                    # warm up models & DB
    translator translate -i in.json -o out.json -t ar
    translator --help
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import typer

# ---------------------------------------------------------------------------
# Path bootstrap — ensure `app` package is importable from the scripts dir
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import async_session, init_db, engine
from app.pipeline import json_to_ast, collect_translatable_nodes, DocumentNode, is_ast_compatible
from app.text_translation.controller import TextTranslationController
from app.text_translation.schemas import TranslationRequest

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="translator",
    help=(
        "Translation CLI — translate JSON objects natively using the "
        "core translation pipeline (NLLB / LLM, caching, quality scoring).\n\n"
        "Run 'translator init' first to warm up models and avoid cold-start "
        "latency on the first translation."
    ),
    add_completion=False,
)


# ===================================================================== #
#  init command — warm up DB, models, and LLM so translate is instant
# ===================================================================== #

async def _async_init():
    """Pre-load every heavy resource the pipeline needs."""
    from sqlalchemy import text as sa_text

    steps = [
        "Database",
        "Duckling",
        "LLM",
        "NLLB models",
        "Embedding model",
        "Quality model",
        "NLTK tokenizer",
    ]

    with typer.progressbar(length=len(steps), label="Warming up") as progress:
        # 1. Database ---------------------------------------------------
        try:
            await init_db()
            async with engine.begin() as conn:
                await conn.execute(sa_text("SELECT 1"))
            typer.echo("  ✓ Database connected")
        except Exception as e:
            typer.secho(f"  ✗ Database: {e}", fg=typer.colors.RED)
        progress.update(1)

        # 2. Duckling ---------------------------------------------------
        try:
            import httpx
            from app.core.config import settings

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    settings.DUCKLING_URL,
                    data={"text": "hello", "locale": "en_XX"},
                )
                resp.raise_for_status()
            typer.echo("  ✓ Duckling reachable")
        except Exception as e:
            typer.secho(f"  ✗ Duckling: {e}", fg=typer.colors.YELLOW)
        progress.update(1)

        # 3. LLM -------------------------------------------------------
        try:
            from app.llms.model import get_llm

            llm = get_llm()
            await llm.ainvoke("ping")
            typer.echo("  ✓ LLM ready")
        except Exception as e:
            typer.secho(f"  ✗ LLM: {e}", fg=typer.colors.YELLOW)
        progress.update(1)

        # 4. NLLB models -----------------------------------------------
        try:
            from app.machine_translation import nllb_service

            await asyncio.to_thread(nllb_service.preload_models)
            typer.echo("  ✓ NLLB models loaded")
        except Exception as e:
            typer.secho(f"  ✗ NLLB models: {e}", fg=typer.colors.YELLOW)
        progress.update(1)

        # 5. Embedding model -------------------------------------------
        try:
            from app.pipeline.embeddings import get_embedding_model

            await asyncio.to_thread(get_embedding_model)
            typer.echo("  ✓ Embedding model loaded")
        except Exception as e:
            typer.secho(f"  ✗ Embedding model: {e}", fg=typer.colors.YELLOW)
        progress.update(1)

        # 6. Quality model ---------------------------------------------
        try:
            from app.pipeline.quality import _get_model

            await asyncio.to_thread(_get_model)
            typer.echo("  ✓ Quality model loaded")
        except Exception as e:
            typer.secho(f"  ✗ Quality model: {e}", fg=typer.colors.YELLOW)
        progress.update(1)

        # 7. NLTK tokenizer --------------------------------------------
        try:
            import nltk

            try:
                await asyncio.to_thread(nltk.data.find, "tokenizers/punkt")
            except LookupError:
                await asyncio.to_thread(nltk.download, "punkt", quiet=True)
            typer.echo("  ✓ NLTK tokenizer ready")
        except Exception as e:
            typer.secho(f"  ✗ NLTK tokenizer: {e}", fg=typer.colors.YELLOW)
        progress.update(1)


@app.command()
def init():
    """
    Warm up the translation pipeline (DB, models, LLM).

    Run this once after starting your environment to eliminate cold-start
    latency on the first 'translate' call.
    """
    typer.secho("⏳ Initialising Translator CLI …", fg=typer.colors.CYAN, bold=True)
    start = time.time()
    asyncio.run(_async_init())
    elapsed = time.time() - start
    typer.secho(
        f"\n✅ Init complete in {elapsed:.1f}s — ready to translate.",
        fg=typer.colors.GREEN,
        bold=True,
    )


# ===================================================================== #
#  translate command — the core JSON translation workflow
# ===================================================================== #

async def _async_translate(
    input_file: Path,
    output_file: Path,
    target_lang: str,
    source_lang: Optional[str] = None,
    brand_uuid: Optional[str] = None,
    domain_name: Optional[str] = None,
):
    try:
        # Ensure DB tables exist
        await init_db()

        # Load source JSON
        with open(input_file, "r", encoding="utf-8") as f:
            doc_data = json.load(f)

        # Parse AST
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
        translatable_nodes = collect_translatable_nodes(doc_node)

        typer.echo(
            f"Found {len(translatable_nodes)} translatable segment(s) "
            f"in {input_file.name}."
        )

        # Translate each segment
        async with async_session() as db:
            text_ctl = TextTranslationController(db)

            with typer.progressbar(
                translatable_nodes, label="Translating segments"
            ) as progress:
                for node in progress:
                    payload = TranslationRequest(
                        text=node.value,
                        target_lang=target_lang,
                        source_lang=source_lang,
                    )

                    try:
                        res = await text_ctl.translate_text(
                            payload=payload,
                            brand_uuid=brand_uuid,
                            domain_name=domain_name,
                            filename=input_file.name,
                            property_name=node.path,
                        )
                        if "error" in res:
                            logger.warning(
                                "Error translating segment '%s…': %s",
                                node.value[:30],
                                res["error"],
                            )
                            node.translated_value = node.value
                        else:
                            node.translated_value = res.get(
                                "translation", node.value
                            )
                    except Exception as e:
                        logger.exception(
                            "Exception translating segment '%s…': %s",
                            node.value[:30],
                            e,
                        )
                        node.translated_value = node.value

        # Reconstruct translated JSON
        translated_document = doc_node.to_dict()

        # AST compatibility check
        translated_ast_root = json_to_ast(translated_document)
        translated_doc_node = DocumentNode(translated_ast_root, "json")
        if not is_ast_compatible(doc_node, translated_doc_node):
            typer.secho(
                "WARNING: Translated document AST is not compatible "
                "with the original document AST.",
                fg=typer.colors.RED,
            )
            raise ValueError("Incompatible AST detected.")

        # Write output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(translated_document, f, ensure_ascii=False, indent=2)

        typer.secho(
            f"✅ Successfully translated → {output_file}",
            fg=typer.colors.GREEN,
        )

    except Exception as e:
        typer.secho(f"Failed to translate document: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def translate(
    input_file: Path = typer.Option(
        ..., "--input", "-i", help="Path to the source JSON file."
    ),
    output_file: Path = typer.Option(
        ..., "--output", "-o", help="Destination path for the translated JSON file."
    ),
    target_lang: str = typer.Option(
        ..., "--target-lang", "-t", help="Target language ISO code (e.g. 'fr', 'ar')."
    ),
    source_lang: Optional[str] = typer.Option(
        None,
        "--source-lang",
        "-s",
        help="Source language ISO code (e.g. 'en'). Omit for auto-detection.",
    ),
    brand_uuid: Optional[str] = typer.Option(
        None,
        "--brand-uuid",
        "-b",
        help="Brand UUID for context injection (tone, glossary, audience).",
    ),
    domain_name: Optional[str] = typer.Option(
        None,
        "--domain-name",
        "-d",
        help="Domain name to apply domain-specific translation rules.",
    ),
):
    """
    Translate a JSON file while preserving its structural integrity (AST).

    Examples:

        translator translate -i en.json -o ar.json -t ar

        translator translate -i menu.json -o menu_fr.json -s en -t fr --brand-uuid abc123
    """
    if not input_file.exists():
        typer.secho(
            f"Input file {input_file} does not exist.", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    asyncio.run(
        _async_translate(
            input_file=input_file,
            output_file=output_file,
            target_lang=target_lang,
            source_lang=source_lang,
            brand_uuid=brand_uuid,
            domain_name=domain_name,
        )
    )


# ===================================================================== #
#  Entry point
# ===================================================================== #

if __name__ == "__main__":
    app()
