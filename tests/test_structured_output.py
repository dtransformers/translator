"""Schema regression tests; runnable without the API/database test fixtures."""
import unittest

from pydantic import ValidationError

from app.llms.schemas import TranslationResult, translation_batch_schema


class StructuredOutputTests(unittest.TestCase):
    def test_single_translation_requires_exact_string_field(self):
        self.assertEqual(TranslationResult(translation='Bonjour').translation, 'Bonjour')
        for payload in ({}, {'translation': 42}, {'translation': 'ok', 'extra': 'bad'}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                TranslationResult.model_validate(payload)

    def test_batch_preserves_arbitrary_keys(self):
        payload = {'a.b[0]': 'Bonjour', '_private': 'Salut', 'model_dump': 'Texte'}
        schema = translation_batch_schema(payload)
        self.assertEqual(schema.model_validate(payload).model_dump(by_alias=True), payload)
        native_schema = schema.model_json_schema()
        self.assertEqual(set(native_schema['required']), set(payload))
        self.assertFalse(native_schema['additionalProperties'])

    def test_batch_rejects_missing_extra_and_non_string_values(self):
        schema = translation_batch_schema({'title': 'Hello'})
        for payload in ({}, {'title': None}, {'title': 1}, {'title': ['hello']},
                        {'title': 'ok', 'extra': 'bad'}, ['hello']):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                schema.model_validate(payload)


class ProviderSchemaTests(unittest.TestCase):
    def test_adapters_bind_native_schema_and_validate_responses(self):
        from unittest.mock import patch
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.exceptions import OutputParserException
        from langchain_ollama import ChatOllama
        from langchain_google_genai import ChatGoogleGenerativeAI

        providers = (
            (ChatOllama(model='test'), 'format'),
            (ChatGoogleGenerativeAI(model='gemini-2.5-flash', google_api_key='test'),
             'response_json_schema'),
        )
        for model, schema_parameter in providers:
            for schema, valid in (
                (TranslationResult, {'translation': 'Bonjour'}),
                (translation_batch_schema({'a.b[0]': 'Hello'}), {'a.b[0]': 'Bonjour'}),
            ):
                with self.subTest(provider=type(model).__name__, schema=schema.__name__):
                    chain = model.with_structured_output(schema, method='json_schema')
                    self.assertEqual(chain.first.kwargs[schema_parameter], schema.model_json_schema())
                    import json
                    for payload in (valid, {}, {'unexpected': 'text'}):
                        reply = ChatResult(generations=[ChatGeneration(
                            message=AIMessage(content=json.dumps(payload))
                        )])
                        with patch.object(type(model), '_generate', return_value=reply):
                            if payload == valid:
                                self.assertEqual(chain.invoke('Translate').model_dump(by_alias=True), valid)
                            else:
                                with self.assertRaises(OutputParserException):
                                    chain.invoke('Translate')

    def test_openrouter_sends_strict_schema_and_validates_responses(self):
        import json
        from unittest.mock import patch
        import httpx
        from pydantic import ValidationError
        from app.llms.model import _get_openrouter_model

        for schema, valid in (
            (TranslationResult, {'translation': 'Bonjour'}),
            (translation_batch_schema({'a.b[0]': 'Hello'}), {'a.b[0]': 'Bonjour'}),
        ):
            for payload in (valid, {}, {'unexpected': 'text'}):
                requests = []

                def handler(request):
                    requests.append(request)
                    return httpx.Response(200, json={
                        'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test',
                        'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                            'role': 'assistant', 'content': json.dumps(payload)}}],
                    })

                with self.subTest(schema=schema.__name__, payload=payload), \
                        patch('app.llms.model.settings.OPENROUTER_API_KEY', 'test'):
                    model = _get_openrouter_model()
                    model.root_client._client = httpx.Client(transport=httpx.MockTransport(handler))
                    chain = model.with_structured_output(schema, method='json_schema')
                    if payload == valid:
                        self.assertEqual(chain.invoke('Translate').model_dump(by_alias=True), valid)
                    else:
                        with self.assertRaises(ValidationError):
                            chain.invoke('Translate')

                    body = json.loads(requests[0].content)
                    self.assertEqual(str(requests[0].url), 'https://openrouter.ai/api/v1/chat/completions')
                    self.assertEqual(body['provider'], {'require_parameters': True})
                    self.assertTrue(body['response_format']['json_schema']['strict'])
                    self.assertEqual(body['response_format']['json_schema']['schema'], schema.model_json_schema())


class PromptSchemaTests(unittest.TestCase):
    """Every prompt renders with its inputs and pairs with a strict native schema."""

    def _pairs(self):
        from app.llms import prompts
        from app.llms import schemas
        return (
            (prompts.get_summary_prompt(), schemas.FileSummary,
             {'target_language': 'fr', 'filename': 'a.json', 'content': 'Hello'}),
            (prompts.get_context_prompt(), schemas.TranslationContext,
             {'target_language': 'fr', 'filename': 'a.json', 'base_context': '{}', 'content': 'Hello'}),
            (prompts.get_global_context_prompt(), schemas.GlobalTranslationContext,
             {'target_language': 'fr', 'compact_files': '[]'}),
            (prompts.get_translation_draft_prompt(), schemas.TranslationResult,
             {'source_language': 'en', 'target_language': 'fr', 'industry': 'x', 'summary': 'x',
              'glossary': '{}', 'domain_rules': '{}', 'rag_examples': 'None', 'texts': '["Hi"]',
              'output_instructions': 'x'}),
            (prompts.get_translation_refine_prompt(), schemas.RefinedTranslations,
             {'target_language': 'fr', 'tone': 'x', 'audience': 'x', 'draft_translations': '["Salut"]'}),
            (prompts.get_validation_prompt(), schemas.TranslationValidation,
             {'source_lang': 'en', 'target_lang': 'fr', 'source_text': 'Hi', 'translated_text': 'Salut'}),
            (prompts.get_fix_translation_prompt(), schemas.FixedTranslation,
             {'target_language': 'fr', 'source_text': 'Hi', 'bad_translation': 'Bonjour'}),
            (prompts.get_complexity_rating_prompt(), schemas.ComplexityRating, {'text': 'Hi'}),
        )

    def test_prompts_render_and_no_longer_describe_json_by_hand(self):
        for prompt, schema, inputs in self._pairs():
            with self.subTest(schema=schema.__name__):
                self.assertEqual(set(prompt.input_variables), set(inputs))
                rendered = '\n'.join(m.content for m in prompt.format_messages(**inputs))
                self.assertNotIn('JSON SCHEMA', rendered.upper())
                self.assertNotIn('ONLY VALID JSON', rendered.upper())

    def test_schemas_are_strict_for_native_decoding(self):
        def walk(node):
            if isinstance(node, dict):
                if node.get('type') == 'object':
                    # Strict providers reject open-ended objects, e.g. dict[str, str]
                    self.assertIs(node.get('additionalProperties'), False)
                    self.assertEqual(set(node.get('required', [])), set(node.get('properties', {})))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        for _, schema, _ in self._pairs():
            with self.subTest(schema=schema.__name__):
                walk(schema.model_json_schema())

    def test_reviewer_and_complexity_use_structured_output(self):
        import asyncio
        from unittest.mock import MagicMock, patch
        from langchain_core.runnables import RunnableLambda
        from app.llms.schemas import ComplexityRating, FixedTranslation
        from app.pipeline import complexity, reviewer

        bound = {}

        def fake_llm(result):
            llm = MagicMock()
            def with_structured_output(schema, method):
                bound['schema'], bound['method'] = schema, method
                return RunnableLambda(lambda _: result)
            llm.with_structured_output.side_effect = with_structured_output
            return llm

        with patch('app.pipeline.reviewer.get_llm',
                   return_value=fake_llm(FixedTranslation(corrected_translation=' Bonjour '))):
            fixed = asyncio.run(reviewer.fix_translation_with_llm('Hello', 'Salut', 'fr'))
        self.assertEqual((fixed, bound['schema'], bound['method']), ('Bonjour', FixedTranslation, 'json_schema'))

        with patch('app.llms.model.get_llm', return_value=fake_llm(ComplexityRating(score=80))), \
                patch('app.core.config.settings.COMPLEXITY_THRESHOLD', 50):
            score = asyncio.run(complexity._get_llm_fallback_score('Hello', 50))
        self.assertEqual((score, bound['schema'], bound['method']), (65, ComplexityRating, 'json_schema'))
