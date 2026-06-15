import os
import logging
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession

from app.document_translation.service import DocumentService
from app.text_translation.controller import TextTranslationController
from app.text_translation.schemas import TranslationRequest
from app.document_translation.schemas import DocumentTranslationRequest
from app.pipeline import (
    is_in_supported_languages,
    json_to_ast,
    collect_translatable_nodes,
    DocumentNode,
    is_ast_compatible,
)
from app.pipeline.translation import translate_json_with_llm
from app.pipeline.complexity import calculate_complexity_score
from app.core.config import settings
from app.brands.service import BrandService

logger = logging.getLogger(__name__)

class DocumentTranslationController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.text_ctl = TextTranslationController(db)

    async def _fetch_and_parse_document(self, document_url: str) -> tuple[DocumentNode | None, str, str | None]:
        try:
            parsed_url = urlparse(document_url)
            filename = os.path.basename(parsed_url.path) or "document.json"
        except Exception:
            filename = "document.json"

        try:
            doc_data = await DocumentService.download_json(document_url)
        except Exception as e:
            return None, filename, f"Failed to fetch document: {str(e)}"

        try:
            root_node = json_to_ast(doc_data)
            doc_node = DocumentNode(root_node, "json")
            return doc_node, filename, None
        except Exception as e:
            return None, filename, f"Failed to parse document to AST: {str(e)}"

    async def _process_local_node(
        self, node, text: str, source_lang: str, target_lang: str, 
        brand_uuid: str | None, domain_name: str | None, filename: str
    ):
        seg_payload = TranslationRequest(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        try:
            res = await self.text_ctl.translate_text(
                payload=seg_payload,
                brand_uuid=brand_uuid,
                domain_name=domain_name,
                filename=filename,
                property_name=node.path,
            )
            if "error" in res:
                logger.warning("Failed to translate segment '%s' in path %s: %s", text[:30], node.path, res["error"])
                node.translated_value = text
            else:
                node.translated_value = res.get("translation", text)
        except Exception:
            logger.exception("Error translating segment '%s'", text[:30])
            node.translated_value = text

    async def _process_llm_batch(
        self, llm_batch: dict, translatable_nodes: list, source_lang: str, target_lang: str, brand_context: dict
    ):
        if not llm_batch:
            return
            
        try:
            translated_batch = await translate_json_with_llm(
                llm_batch, source_lang, target_lang, brand_context=brand_context
            )
            for node in translatable_nodes:
                if node.path in translated_batch:
                    node.translated_value = translated_batch[node.path]
        except Exception:
            logger.exception("Failed to batch translate JSON with LLM")
            for node in translatable_nodes:
                if node.path in llm_batch:
                    node.translated_value = node.value

    async def translate_document(
        self,
        payload: DocumentTranslationRequest,
        brand_uuid: str | None = None,
        domain_name: str | None = None,
    ) -> dict:
        """
        Document translation: fetches document from URL, converts to AST,
        translates each segment, and reconstitutes the document.
        """
        source_lang = payload.source_lang
        target_lang = payload.target_lang
        document_url = payload.document_url

        if not is_in_supported_languages(source_lang, target_lang):
            return {"error": f"Language pair {source_lang}->{target_lang} is not supported"}

        doc_node, filename, err = await self._fetch_and_parse_document(document_url)
        if err:
            return {"error": err}

        translatable_nodes = collect_translatable_nodes(doc_node)
        
        brand_service = BrandService(self.db)
        brand_context = await brand_service.get_brand_context(brand_uuid) if brand_uuid else {}
        glossary = brand_context.get("glossary", {}) if brand_context else {}
        keywords = brand_context.get("keywords", []) if brand_context else []

        llm_batch: dict[str, str] = {}
        for node in translatable_nodes:
            text = node.value
            text_lower = text.lower()

            # Flattened complexity checks to reduce nesting
            requires_llm = (
                any(term.lower() in text_lower for term in glossary.keys()) or
                any(kw.lower() in text_lower for kw in keywords) or
                await calculate_complexity_score(text, brand_context) >= settings.COMPLEXITY_THRESHOLD
            )

            if requires_llm:
                llm_batch[node.path] = text
            else:
                await self._process_local_node(
                    node, text, source_lang, target_lang, brand_uuid, domain_name, filename
                )

        await self._process_llm_batch(llm_batch, translatable_nodes, source_lang, target_lang, brand_context)

        translated_document = doc_node.to_dict()
        translated_ast_root = json_to_ast(translated_document)
        translated_doc_node = DocumentNode(translated_ast_root, "json")
        
        if not is_ast_compatible(doc_node, translated_doc_node):
            return {"error": "Translated document AST is not compatible with the original document AST"}

        return {
            "message": "Document translation completed successfully",
            "data": {
                "document_url": document_url,
                "source_lang": source_lang,
                "target_lang": target_lang,
            },
            "translated_document": translated_document,
        }


