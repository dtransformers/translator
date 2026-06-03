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
)

logger = logging.getLogger(__name__)

class DocumentTranslationController:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.text_ctl = TextTranslationController(db)

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

        try:
            parsed_url = urlparse(document_url)
            filename = os.path.basename(parsed_url.path) or "document.json"
        except Exception:
            filename = "document.json"

        try:
            doc_data = await DocumentService.download_json(document_url)
        except Exception as e:
            return {"error": f"Failed to fetch document: {str(e)}"}

        try:
            root_node = json_to_ast(doc_data)
            doc_node = DocumentNode(root_node, "json")
        except Exception as e:
            return {"error": f"Failed to parse document to AST: {str(e)}"}

        translatable_nodes = collect_translatable_nodes(doc_node)
        
        for node in translatable_nodes:
            seg_payload = TranslationRequest(
                text=node.value,
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
                    logger.warning("Failed to translate segment '%s' in path %s: %s", node.value[:30], node.path, res["error"])
                    node.translated_value = node.value
                else:
                    node.translated_value = res.get("translation", node.value)
            except Exception:
                logger.exception("Error translating segment '%s'", node.value[:30])
                node.translated_value = node.value

        # Reconstitute the document from AST
        translated_document = doc_node.to_dict()

        return {
            "message": "Document translation completed successfully",
            "data": {
                "document_url": document_url,
                "source_lang": source_lang,
                "target_lang": target_lang,
            },
            "translated_document": translated_document,
        }

async def translate_document_controller(
    payload: DocumentTranslationRequest,
    db: AsyncSession,
    brand_uuid: str | None = None,
    domain_name: str | None = None,
) -> dict:
    ctl = DocumentTranslationController(db)
    return await ctl.translate_document(payload, brand_uuid, domain_name)

