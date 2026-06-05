import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import async_session, init_db
from app.pipeline import json_to_ast, collect_translatable_nodes, DocumentNode, is_ast_compatible
from app.text_translation.controller import TextTranslationController
from app.text_translation.schemas import TranslationRequest

logger = logging.getLogger(__name__)

app = typer.Typer(help="CLI tool for JSON object translation natively via the core pipeline.")

async def async_translate(
    input_file: Path,
    output_file: Path,
    target_lang: str,
    source_lang: Optional[str] = None,
    brand_uuid: Optional[str] = None,
    domain_name: Optional[str] = None,
):
    try:
        await init_db()
        
        with open(input_file, 'r', encoding='utf-8') as f:
            doc_data = json.load(f)

        # Parse AST
        root_node = json_to_ast(doc_data)
        doc_node = DocumentNode(root_node, "json")
        translatable_nodes = collect_translatable_nodes(doc_node)

        typer.echo(f"Found {len(translatable_nodes)} translatable segments in {input_file.name}.")

        # Translate using the TextTranslationController
        async with async_session() as db:
            text_ctl = TextTranslationController(db)
            
            with typer.progressbar(translatable_nodes, label="Translating segments") as progress:
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
                            logger.warning(f"Error translating segment '{node.value[:30]}...': {res['error']}")
                            node.translated_value = node.value
                        else:
                            node.translated_value = res.get("translation", node.value)
                    except Exception as e:
                        logger.exception(f"Exception translating segment '{node.value[:30]}...': {e}")
                        node.translated_value = node.value

        # Reconstruct translated JSON
        translated_document = doc_node.to_dict()

        # AST Compatibility Check
        translated_ast_root = json_to_ast(translated_document)
        translated_doc_node = DocumentNode(translated_ast_root, "json")
        if not is_ast_compatible(doc_node, translated_doc_node):
            typer.secho("WARNING: Translated document AST is not compatible with the original document AST.", fg=typer.colors.RED)
            raise ValueError("Incompatible AST detected.")

        # Save to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(translated_document, f, ensure_ascii=False, indent=2)
            
        typer.secho(f"Successfully translated {input_file.name} to {output_file.name}.", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Failed to translate document: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

@app.command()
def translate(
    input_file: Path = typer.Option(..., "--input", "-i", help="Path to the source JSON file."),
    output_file: Path = typer.Option(..., "--output", "-o", help="Destination path to save the translated JSON file."),
    target_lang: str = typer.Option(..., "--target-lang", "-t", help="Target language ISO code (e.g., 'fr', 'ar')."),
    source_lang: Optional[str] = typer.Option(None, "--source-lang", "-s", help="Source language ISO code (e.g., 'en'). If omitted, language detection is used."),
    brand_uuid: Optional[str] = typer.Option(None, "--brand-uuid", help="Optional Brand UUID for context injection (tone, glossary)."),
    domain_name: Optional[str] = typer.Option(None, "--domain-name", help="Optional Domain name to apply domain-specific rules."),
):
    """
    Translates a JSON file from a source language to a target language.
    Preserves the structural integrity (AST) of the JSON document.
    """
    if not input_file.exists():
        typer.secho(f"Input file {input_file} does not exist.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    asyncio.run(async_translate(
        input_file=input_file,
        output_file=output_file,
        target_lang=target_lang,
        source_lang=source_lang,
        brand_uuid=brand_uuid,
        domain_name=domain_name
    ))

if __name__ == "__main__":
    app()
