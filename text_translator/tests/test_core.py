import unittest
from unittest.mock import patch, MagicMock, call
import os
import requests
from io import StringIO

from text_translator.translator_lib import core, translation, api_client, validation, data_processor
from text_translator.translator_lib.options import TranslationOptions
from text_translator.translator_lib.exceptions import APIConnectionError, ModelLoadError, TranslatorError
from langdetect import LangDetectException

class TestCoreWorkflow(unittest.TestCase):
    """Tests the high-level translation workflows in the `core` module."""

    def setUp(self):
        """Sets up common mock configurations and options for workflow tests."""
        self.mock_model_config = {
            "prompt_template": "Test prompt: {text}",
            "params": {"temperature": 0.5}
        }
        self.mock_draft_config = {
            "prompt_template": "Draft prompt: {text}",
            "params": {"temperature": 0.9}
        }
        self.base_options = TranslationOptions(
            input_path="input.txt",
            model_name="test-model",
            api_base_url="http://test.url",
            quiet=True,
            model_config=self.mock_model_config,
            draft_model_config=self.mock_draft_config
        )

    def test_direct_translation_workflow(self):
        """Test the end-to-end direct translation workflow."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize'), \
             patch('text_translator.translator_lib.core.collect_text_nodes') as mock_collect, \
             patch('text_translator.translator_lib.core.ensure_model_loaded') as mock_ensure_model, \
             patch('text_translator.translator_lib.core.get_translation') as mock_get_translation:

            mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
            mock_get_translation.return_value = "translated"

            core.translate_file(self.base_options)

            mock_ensure_model.assert_called_once_with(
                "test-model",
                "http://test.url",
                model_config=self.mock_model_config,
                verbose=False,
                debug=False
            )
            mock_get_translation.assert_called_once()
            _, kwargs = mock_get_translation.call_args
            self.assertEqual(kwargs['model_config'], self.mock_model_config)

    def test_refinement_workflow(self):
        """Test the end-to-end refinement translation workflow."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize'), \
             patch('text_translator.translator_lib.core.collect_text_nodes') as mock_collect, \
             patch('text_translator.translator_lib.core._get_refined_translation') as mock_get_refined:

            mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
            mock_get_refined.return_value = "refined"

            options = self.base_options
            options.refine_mode = True
            options.draft_model = "draft-model"

            core.translate_file(options)

            mock_get_refined.assert_called_once()
            _, kwargs = mock_get_refined.call_args
            self.assertEqual(kwargs['refine_model_config'], self.mock_model_config)
            self.assertEqual(kwargs['draft_model_config'], self.mock_draft_config)

    def test_no_nodes_to_translate(self):
        """Test that the function exits early if no text nodes are found."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize'), \
             patch('text_translator.translator_lib.core.collect_text_nodes') as mock_collect, \
             patch('text_translator.translator_lib.core.ensure_model_loaded') as mock_ensure_model:

            mock_collect.side_effect = lambda data, lst: None

            core.translate_file(self.base_options)

            mock_ensure_model.assert_not_called()

    def test_line_by_line_preserves_trailing_newline(self):
        """Test that line-by-line translation preserves a trailing newline."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize') as mock_deserialize, \
             patch('text_translator.translator_lib.data_processor.detect', return_value='ja'), \
             patch('text_translator.translator_lib.core.ensure_model_loaded'), \
             patch('text_translator.translator_lib.core.get_translation') as mock_get_translation, \
             patch('custom_xml_parser.parser.serialize') as mock_serialize:

            input_text = "line one\nline two\n"
            data_structure = {'root': {'#text': input_text}}
            mock_deserialize.return_value = data_structure
            mock_get_translation.side_effect = lambda text, **kwargs: f"{text.strip()} (translated)\n"

            options = self.base_options
            options.line_by_line = True

            core.translate_file(options)
            final_data = mock_serialize.call_args[0][0]
            final_text = final_data['root']['#text']
            self.assertEqual(final_text, "line one (translated)\nline two (translated)\n")

    def test_refinement_fails_with_multiline_in_line_by_line_mode(self):
        """Test that a refined translation failure is handled gracefully and a warning is logged."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize'), \
             patch('text_translator.translator_lib.core.collect_text_nodes') as mock_collect, \
             patch('text_translator.translator_lib.translation.ensure_model_loaded'), \
             patch('text_translator.translator_lib.translation.get_translation') as mock_get_translation, \
             patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr, \
             patch('time.sleep'):

            mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'single line'}])
            mock_get_translation.return_value = "A valid draft translation."
            # The refinement call gets an invalid (multiline) response
            mock_api_request.return_value = {"choices": [{"message": {"content": "this is the\nrefined translation"}}]}

            options = self.base_options
            options.refine_mode = True
            options.draft_model = "draft-model"
            options.line_by_line = True # Enable line-by-line validation

            # Act
            core.translate_file(options)

            # Assert that a warning was printed to stderr
            output = mock_stderr.getvalue()
            self.assertIn("Warning: Could not translate node 1", output)
            self.assertIn("Failed to get a valid refined translation", output)

    def test_direct_translation_with_reasoning(self):
        """Test the direct translation workflow with reasoning enabled."""
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize'), \
             patch('text_translator.translator_lib.core.collect_text_nodes') as mock_collect, \
             patch('text_translator.translator_lib.core.ensure_model_loaded'), \
             patch('text_translator.translator_lib.core.get_translation') as mock_get_translation:

            mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
            options = self.base_options
            options.reasoning_for = "main"

            core.translate_file(options)

            mock_get_translation.assert_called_once()
            _, kwargs = mock_get_translation.call_args
            self.assertTrue(kwargs.get('use_reasoning'))

    def test_translate_file_skips_if_output_exists(self):
        """Test that the function skips if the output file already exists and overwrite is False."""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open') as mock_open:

            options = self.base_options
            options.output_path = "out.txt"
            options.overwrite = False

            core.translate_file(options)
            mock_open.assert_not_called()

    def test_empty_translation_does_not_add_marker(self):
        """
        Test that if translation returns an empty string, the original text is preserved
        and the `jp_text:::` marker is NOT added. This test should FAIL before the fix.
        """
        with patch('os.path.exists', return_value=False), \
             patch('builtins.open'), \
             patch('custom_xml_parser.parser.deserialize') as mock_deserialize, \
             patch('text_translator.translator_lib.data_processor.detect', return_value='ja'), \
             patch('text_translator.translator_lib.core.ensure_model_loaded'), \
             patch('text_translator.translator_lib.core.get_translation') as mock_get_translation, \
             patch('text_translator.translator_lib.core.cleanup_markers'), \
             patch('custom_xml_parser.parser.serialize'):

            original_text = "こんにちは"
            data_structure = {'root': {'#text': original_text}}
            mock_deserialize.return_value = data_structure

            mock_get_translation.return_value = ""  # Simulate an empty translation

            # Act
            core.translate_file(self.base_options)

            # Assert: Check the state of the node *before* cleanup_markers would run.
            # With the bug, the text will be "jp_text:::こんにちは".
            # The desired state is just "こんにちは". This assertion should fail.
            final_text_in_node = data_structure['root']['#text']
            self.assertEqual(final_text_in_node, original_text)


class TestGetTranslation(unittest.TestCase):
    """Tests the `get_translation` function's logic and integrations."""
    def setUp(self):
        """Sets up a standard model configuration for translation tests."""
        self.model_config = {
            "prompt_template": "Translate: {text}",
            "reasoning_prompt_template": "Reason and translate: {text}",
            "params": {"temperature": 0.1, "top_k": 10}
        }

    def test_get_translation_uses_model_config(self):
        """Test get_translation uses prompt template and params from model_config."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True):

            mock_api_request.return_value = {"choices": [{"message": {"content": "translated"}}]}
            # This config has no endpoint, so it uses the default (chat)
            translation.get_translation("original", "test-model", "http://test.url", self.model_config)

            args, _ = mock_api_request.call_args
            payload = args[1]

            self.assertEqual(payload['messages'][0]['content'], "Translate: original")
            self.assertEqual(payload['model'], "test-model")
            self.assertEqual(payload['temperature'], 0.1)
            self.assertEqual(payload['top_k'], 10)

    def test_get_translation_with_reasoning(self):
        """Test get_translation with reasoning mode enabled."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True):

            mock_api_request.return_value = {
                "choices": [{"message": {"content": "Reasoning: ...\nTranslation: translated"}}]
            }
            translation.get_translation("original", "test-model", "http://test.url", self.model_config, use_reasoning=True)

            args, _ = mock_api_request.call_args
            payload = args[1]
            self.assertEqual(payload['messages'][0]['content'], "Reason and translate: original")

    def test_get_translation_with_glossary(self):
        """Test that a glossary is correctly added to the prompt."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True):

            mock_api_request.return_value = {"choices": [{"message": {"content": "translated"}}]}
            translation.get_translation("text", "model", "http://test.url", self.model_config, glossary_text="glossary")
            prompt = mock_api_request.call_args[0][1]['messages'][0]['content']
            self.assertIn("Please use this glossary", prompt)

    def test_get_translation_retry_on_invalid(self):
        """Test that get_translation retries if the first result is invalid."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.translation.is_translation_valid', side_effect=[False, True]):

            mock_api_request.return_value = {"choices": [{"text": "translated"}]}
            translation.get_translation("text", "model", "http://test.url", self.model_config)
            self.assertEqual(mock_api_request.call_count, 2)

    def test_get_translation_raises_error_on_persistent_invalid(self):
        """Test that get_translation raises TranslationError if the translation is always invalid."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.translation.is_translation_valid', return_value=False):

            mock_api_request.return_value = {"choices": [{"text": "some invalid response"}]}
            with self.assertRaises(TranslatorError):
                translation.get_translation("original text", "model", "http://test.url", self.model_config)
            self.assertEqual(mock_api_request.call_count, 3)

    def test_get_translation_default_chat_endpoint(self):
        """Test get_translation uses the chat endpoint by default."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True):

            mock_api_request.return_value = {"choices": [{"message": {"content": "translated"}}]}
            # model_config does not specify an endpoint, so it should use the new default
            translation.get_translation("original", "chat-model", "http://test.url", self.model_config)

            args, _ = mock_api_request.call_args
            endpoint, payload = args[0], args[1]

            self.assertEqual(endpoint, "chat/completions")
            self.assertIn("messages", payload)
            self.assertNotIn("prompt", payload)

    def test_get_translation_legacy_completions_endpoint(self):
        """Test get_translation uses the legacy completions endpoint when specified."""
        legacy_config = {
            "endpoint": "completions",
            "prompt_template": "Translate for legacy: {text}",
            "params": {"temperature": 0.3}
        }
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True):

            mock_api_request.return_value = {"choices": [{"text": "translated"}]}
            translation.get_translation("original", "legacy-model", "http://test.url", legacy_config)

            args, _ = mock_api_request.call_args
            endpoint, payload = args[0], args[1]

            self.assertEqual(endpoint, "completions")
            self.assertIn("prompt", payload)
            self.assertNotIn("messages", payload)

    def test_get_translation_with_debug(self):
        """Test that get_translation prints debug output."""
        with patch('text_translator.translator_lib.translation._api_request') as mock_api_request, \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True), \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            mock_api_request.return_value = {"choices": [{"message": {"content": "translated"}}]}
            translation.get_translation("original", "test-model", "http://test.url", self.model_config, debug=True)
            self.assertIn("Translation Prompt", mock_stderr.getvalue())
            self.assertIn("Translation Result", mock_stderr.getvalue())

    def test_get_translation_retry_on_connection_error(self):
        """Test that get_translation retries on APIConnectionError."""
        with patch('text_translator.translator_lib.translation._api_request', side_effect=[APIConnectionError, {"choices": [{"message": {"content": "translated"}}]}]), \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True), \
             patch('time.sleep'):
            # This should succeed because the second attempt works
            result = translation.get_translation("original", "test-model", "http://test.url", self.model_config)
            self.assertEqual(result, "translated")

    def test_get_translation_raises_translator_error_on_persistent_connection_error(self):
        """Test that get_translation raises TranslatorError after retries on ConnectionError."""
        with patch('text_translator.translator_lib.translation._api_request', side_effect=APIConnectionError("API is down")), \
             patch('text_translator.translator_lib.validation.is_translation_valid', return_value=True), \
             patch('time.sleep'):  # Mock sleep to avoid waiting
            with self.assertRaises(TranslatorError):
                translation.get_translation("original", "test-model", "http://test.url", self.model_config)


class TestTranslationExtraction(unittest.TestCase):
    """Tests the `_extract_translation_from_response` helper function."""
    def test_extract_with_translation_marker(self):
        """Test extraction when 'Translation:' marker is present."""
        response = "Thinking about it...\nTranslation: This is the final text."
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "This is the final text.")

    def test_extract_with_thinking_tags(self):
        """Test that <thinking> tags are correctly removed."""
        response = "<thinking>This is my thought process.</thinking>Translation: This is the translation."
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "This is the translation.")

    def test_extract_no_marker(self):
        """Test extraction when no 'Translation:' marker is present."""
        response = "This is just a direct translation."
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "This is just a direct translation.")

    def test_extract_empty_response(self):
        """Test extraction with an empty response."""
        response = ""
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "")

    def test_extract_with_only_thinking_tags(self):
        """Test extraction with only thinking tags."""
        response = "<thinking>I am thinking.</thinking>"
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "")

    def test_extract_marker_inside_thinking_tag(self):
        """Test that the marker is ignored if inside a thinking tag."""
        response = "<thinking>Translation: this should be ignored</thinking>"
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "")

class TestAdvancedTranslationExtraction(unittest.TestCase):
    """Tests advanced scenarios for translation extraction, including JSON."""
    def test_extract_with_debug(self):
        """Test that debug information is printed."""
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            translation._extract_translation_from_response('{"translation": "a"}', debug=True, use_json_format=True)
            self.assertIn("Extracted translation from JSON", mock_stderr.getvalue())

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            translation._extract_translation_from_response("Translation: b", debug=True)
            self.assertIn("Extracting translation from response using marker", mock_stderr.getvalue())

        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            translation._extract_translation_from_response("c", debug=True)
            self.assertIn("No marker found", mock_stderr.getvalue())

    def test_extract_json_format(self):
        """Test extraction with JSON format."""
        response = '{"translation": "This is a JSON translation."}'
        result = translation._extract_translation_from_response(response, use_json_format=True)
        self.assertEqual(result, "This is a JSON translation.")

    def test_extract_json_in_code_block(self):
        """Test extraction with JSON format wrapped in markdown."""
        response = '```json\n{"translation": "This is a JSON translation."}\n```'
        result = translation._extract_translation_from_response(response, use_json_format=True)
        self.assertEqual(result, "This is a JSON translation.")

    def test_extract_json_in_code_block_no_json_identifier(self):
        """Test extraction with JSON format wrapped in markdown without identifier."""
        response = '```\n{"translation": "This is a JSON translation."}\n```'
        result = translation._extract_translation_from_response(response, use_json_format=True)
        self.assertEqual(result, "This is a JSON translation.")

    def test_extract_malformed_json_fallback(self):
        """Test fallback when JSON is malformed."""
        response = '{"translation": "This is a malformed JSON" '
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            result = translation._extract_translation_from_response(response, use_json_format=True, debug=True)
            self.assertEqual(result, '{"translation": "This is a malformed JSON"')
            self.assertIn("JSON parsing failed", mock_stderr.getvalue())

    def test_extract_with_alternative_marker(self):
        """Test extraction with 'Translated Text:' marker."""
        response = "Thinking...\nTranslated Text: This is the final text."
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "This is the final text.")

    def test_extract_with_case_insensitive_marker(self):
        """Test extraction with a case-insensitive marker."""
        response = "thinking...\ntranslation: This is the final text."
        result = translation._extract_translation_from_response(response)
        self.assertEqual(result, "This is the final text.")

    def test_extract_with_no_marker_and_use_json_false(self):
        """Test extraction returns full response when no marker and not using JSON."""
        response = "This is a direct translation."
        result = translation._extract_translation_from_response(response, use_json_format=False)
        self.assertEqual(result, "This is a direct translation.")


class TestApiAndModelHelpers(unittest.TestCase):
    """Tests helper functions in `api_client` related to model management."""
    def test_api_request_debug_printing(self):
        with patch('requests.post') as mock_post, \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            mock_post.return_value.json.return_value = {"status": "ok"}
            # The retry decorator will call the function multiple times on failure,
            # so we give it a success case here.
            with patch('text_translator.translator_lib.api_client.retry_with_backoff', lambda: lambda f: f):
                api_client._api_request("test/endpoint", {}, "http://test.url", debug=True)
            self.assertIn("DEBUG: API Request to endpoint", mock_stderr.getvalue())

    def test_ensure_model_loaded_needs_loading(self):
        with patch('text_translator.translator_lib.api_client._api_request') as mock_api_request:
            mock_api_request.side_effect = [{"model_name": "other-model"}, {"result": "success"}]
            api_client.ensure_model_loaded("test-model", "http://test.url")
            self.assertEqual(mock_api_request.call_count, 2)

    def test_ensure_model_loaded_connection_error_info(self):
        """Test that ensure_model_loaded raises ModelLoadError on info failure."""
        with patch('text_translator.translator_lib.api_client._api_request', side_effect=APIConnectionError("Info error")):
            with self.assertRaisesRegex(ModelLoadError, "Error getting current model"):
                api_client.ensure_model_loaded("test-model", "http://test.url")

    def test_api_request_get(self):
        """Test that _api_request can make a GET request."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = {"status": "ok"}
            with patch('text_translator.translator_lib.api_client.retry_with_backoff', lambda: lambda f: f):
                api_client._api_request("test/endpoint", {}, "http://test.url", is_get=True)
            mock_get.assert_called_once()

    def test_check_server_status_connection_error(self):
        """Test that check_server_status raises APIConnectionError on failure."""
        with patch('text_translator.translator_lib.api_client._api_request', side_effect=APIConnectionError("Server down")):
            with self.assertRaisesRegex(APIConnectionError, "Could not connect"):
                api_client.check_server_status("http://test.url")

    def test_ensure_model_loaded_verbose(self):
        """Test that ensure_model_loaded prints verbose output."""
        with patch('text_translator.translator_lib.api_client._api_request') as mock_api_request, \
             patch('builtins.print') as mock_print:
            mock_api_request.side_effect = [{"model_name": "other-model"}, {"result": "success"}]
            with patch('time.sleep'): # Patch sleep to speed up test
                 api_client.ensure_model_loaded("test-model", "http://test.url", verbose=True)

            # Check that verbose messages were printed
            self.assertIn(call("Switching model to 'test-model' with new configuration..."), mock_print.call_args_list)
            self.assertIn(call("Model loaded successfully."), mock_print.call_args_list)

    def test_ensure_model_loaded_connection_error_load(self):
        """Test that ensure_model_loaded raises ModelLoadError on model load failure."""
        with patch('text_translator.translator_lib.api_client._api_request') as mock_api_request:
            # First call for info succeeds, second for loading fails
            mock_api_request.side_effect = [
                {"model_name": "other-model"},
                APIConnectionError("Load error")
            ]
            with self.assertRaisesRegex(ModelLoadError, "Failed to load model"):
                api_client.ensure_model_loaded("test-model", "http://test.url")

if __name__ == '__main__':
    unittest.main()

if __name__ == '__main__':
    unittest.main()
