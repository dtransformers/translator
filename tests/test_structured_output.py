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
