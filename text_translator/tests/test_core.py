import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import requests
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core
from translator_lib.options import TranslationOptions

class TestCoreWorkflow(unittest.TestCase):

    def setUp(self):
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

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    def test_direct_translation_workflow(self, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the end-to-end direct translation workflow."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        mock_get_translation.return_value = "translated"

        core.translate_file(self.base_options)

        mock_ensure_model.assert_called_once_with("test-model", "http://test.url", False, debug=False)
        mock_get_translation.assert_called_once()
        _, kwargs = mock_get_translation.call_args
        self.assertEqual(kwargs['model_config'], self.mock_model_config)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core._get_refined_translation')
    def test_refinement_workflow(self, mock_get_refined, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the end-to-end refinement translation workflow."""
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

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    def test_no_nodes_to_translate(self, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test that the function exits early if no text nodes are found."""
        mock_collect.side_effect = lambda data, lst: None

        core.translate_file(self.base_options)

        mock_ensure_model.assert_not_called()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.detect', return_value='ja')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    def test_line_by_line_preserves_trailing_newline(self, mock_get_translation, mock_ensure_model, mock_detect, mock_deserialize, mock_open, mock_exists):
        """Test that line-by-line translation preserves a trailing newline."""
        input_text = "line one\nline two\n"
        data_structure = {'root': {'#text': input_text}}
        mock_deserialize.return_value = data_structure
        mock_get_translation.side_effect = lambda text, **kwargs: f"{text.strip()} (translated)\n"

        options = self.base_options
        options.line_by_line = True

        with patch('translator_lib.core.parser.serialize') as mock_serialize:
            core.translate_file(options)
            final_data = mock_serialize.call_args[0][0]
            final_text = final_data['root']['#text']
            self.assertEqual(final_text, "line one (translated)\nline two (translated)\n")

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core._api_request')
    @patch('time.sleep')
    def test_refinement_fails_with_multiline_in_line_by_line_mode(self, mock_sleep, mock_api_request, mock_collect, mock_deserialize, mock_open, mock_exists):
        """
        Test that the fixed implementation raises a ValueError when the refined
        translation is invalid in line-by-line mode.
        """
        # 1. Setup
        input_text = "single line"
        data_structure = {'root': {'#text': input_text}}
        mock_deserialize.return_value = data_structure
        mock_collect.side_effect = lambda data, lst: lst.extend([data['root']])

        options = self.base_options
        options.refine_mode = True
        options.draft_model = "draft-model"
        options.num_drafts = 1
        options.line_by_line = True

        # 2. Mock API responses
        # This response is multi-line, which is invalid and should be rejected by the new logic.
        invalid_refined_response = {"choices": [{"text": "this is the\nrefined translation"}]}

        mock_api_request.side_effect = [
            {"model_name": "initial-model"},
            {"result": "success"},
            {"choices": [{"text": "a valid single-line draft"}]},
            {"model_name": "draft-model"},
            {"result": "success"},
            invalid_refined_response,
            invalid_refined_response,
            invalid_refined_response,
        ]

        # 3. Execute and Assert that the correct error is raised
        with self.assertRaisesRegex(ValueError, "Failed to get a valid refined translation"):
            core.translate_file(options)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    def test_direct_translation_with_reasoning(self, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the direct translation workflow with reasoning enabled."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        options = self.base_options
        options.reasoning_for = "main"

        core.translate_file(options)

        mock_get_translation.assert_called_once()
        _, kwargs = mock_get_translation.call_args
        self.assertTrue(kwargs.get('use_reasoning'))

    @patch('os.path.exists', return_value=True)
    def test_translate_file_skips_if_output_exists(self, mock_exists):
        """Test that the function skips if the output file already exists and overwrite is False."""
        options = self.base_options
        options.output_path = "out.txt"
        options.overwrite = False

        with patch('builtins.open') as mock_open:
            core.translate_file(options)
            mock_open.assert_not_called()

class TestGetTranslation(unittest.TestCase):
    def setUp(self):
        self.model_config = {
            "prompt_template": "Translate: {text}",
            "reasoning_prompt_template": "Reason and translate: {text}",
            "params": {"temperature": 0.1, "top_k": 10}
        }

    @patch('translator_lib.core.is_translation_valid', return_value=True)
    @patch('translator_lib.core._api_request')
    def test_get_translation_uses_model_config(self, mock_api_request, mock_is_valid):
        """Test get_translation uses prompt template and params from model_config."""
        mock_api_request.return_value = {"choices": [{"text": "translated"}]}
        core.get_translation("original", "test-model", "http://test.url", self.model_config)

        args, _ = mock_api_request.call_args
        payload = args[1]

        self.assertEqual(payload['prompt'], "Translate: original")
        self.assertEqual(payload['model'], "test-model")
        self.assertEqual(payload['temperature'], 0.1)
        self.assertEqual(payload['top_k'], 10)

    @patch('translator_lib.core.is_translation_valid', return_value=True)
    @patch('translator_lib.core._api_request')
    def test_get_translation_with_reasoning(self, mock_api_request, mock_is_valid):
        """Test get_translation with reasoning mode enabled."""
        mock_api_request.return_value = {
            "choices": [{"text": "Reasoning: ...\nTranslation: translated"}]
        }
        core.get_translation("original", "test-model", "http://test.url", self.model_config, use_reasoning=True)

        args, _ = mock_api_request.call_args
        payload = args[1]
        self.assertEqual(payload['prompt'], "Reason and translate: original")

    @patch('translator_lib.core.is_translation_valid', return_value=True)
    @patch('translator_lib.core._api_request')
    def test_get_translation_with_glossary(self, mock_api_request, mock_is_valid):
        """Test that a glossary is correctly added to the prompt."""
        mock_api_request.return_value = {"choices": [{"text": "translated"}]}
        core.get_translation("text", "model", "url", self.model_config, glossary_text="glossary")
        prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertIn("Please use this glossary", prompt)

    @patch('translator_lib.core.is_translation_valid', side_effect=[False, True])
    @patch('translator_lib.core._api_request')
    def test_get_translation_retry_on_invalid(self, mock_api, mock_valid):
        """Test that get_translation retries if the first result is invalid."""
        mock_api.return_value = {"choices": [{"text": "translated"}]}
        core.get_translation("text", "model", "url", self.model_config)
        self.assertEqual(mock_api.call_count, 2)

    @patch('translator_lib.core.is_translation_valid', return_value=False)
    @patch('translator_lib.core._api_request')
    def test_get_translation_raises_error_on_persistent_invalid(self, mock_api, mock_is_valid):
        """Test that get_translation raises ValueError if the translation is always invalid."""
        mock_api.return_value = {"choices": [{"text": "some invalid response"}]}
        with self.assertRaisesRegex(ValueError, "Failed to get a valid translation"):
            core.get_translation("original text", "model", "url", self.model_config)
        self.assertEqual(mock_api.call_count, 3)

class TestApiAndModelHelpers(unittest.TestCase):
    @patch('requests.post')
    def test_api_request_debug_printing(self, mock_post):
        mock_post.return_value.json.return_value = {"status": "ok"}
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            core._api_request("test/endpoint", {}, "http://test.url", debug=True)
            self.assertIn("DEBUG: API Request to endpoint", mock_stderr.getvalue())

    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_needs_loading(self, mock_api_request):
        mock_api_request.side_effect = [{"model_name": "other-model"}, {"result": "success"}]
        core.ensure_model_loaded("test-model", "http://test.url")
        self.assertEqual(mock_api_request.call_count, 2)

    @patch('translator_lib.core._api_request', side_effect=ConnectionError("Info error"))
    def test_ensure_model_loaded_connection_error_info(self, mock_api_request):
        with self.assertRaisesRegex(ConnectionError, "Error getting current model"):
            core.ensure_model_loaded("test-model", "http://test.url")

class TestTranslationValidation(unittest.TestCase):

    def test_validation_success(self):
        with patch('translator_lib.core.detect', return_value='en'):
            self.assertTrue(core.is_translation_valid("こんにちは", "Hello"))

    def test_validation_fails_if_empty_or_identical(self):
        self.assertFalse(core.is_translation_valid("original", ""))
        self.assertFalse(core.is_translation_valid("original", "  "))
        self.assertFalse(core.is_translation_valid("original", "original"))
        self.assertFalse(core.is_translation_valid("original", "ORIGINAL"))

    def test_validation_fails_for_refusal(self):
        self.assertFalse(core.is_translation_valid("original", "I'm sorry, I cannot do that."))

    def test_validation_fails_for_non_english(self):
        with patch('translator_lib.core.detect', return_value='ja'):
            self.assertFalse(core.is_translation_valid("original", "これは日本語です"))

    def test_validation_lang_detect_exception_is_valid(self):
        with patch('translator_lib.core.detect', side_effect=core.LangDetectException(0, "error")):
            self.assertTrue(core.is_translation_valid("original", "a valid translation"))

    def test_validation_fails_for_multiline_in_line_by_line_mode(self):
        self.assertFalse(core.is_translation_valid("original", "hello\nworld", line_by_line=True))
        self.assertTrue(core.is_translation_valid("original", "hello world", line_by_line=True))

    def test_validation_fails_for_japanese_chars(self):
        self.assertFalse(core.is_translation_valid("original", "This is a translation with こんにちは"))

    def test_validation_fails_for_excessive_repetition(self):
        repetitive_text = "word " * 11
        self.assertFalse(core.is_translation_valid("original", repetitive_text))

    def test_validation_fails_for_placeholder_text(self):
        self.assertFalse(core.is_translation_valid("original", "This is a [translation here]"))

    def test_validation_fails_for_length_ratio(self):
        long_original = "This is a very long original sentence that we are testing."
        short_original = "This is a test."
        self.assertFalse(core.is_translation_valid(long_original, "short")) # Too short
        self.assertFalse(core.is_translation_valid(short_original, long_original)) # Too long

    def test_validation_fails_for_new_xml_tags(self):
        self.assertFalse(core.is_translation_valid("original", "This is a <tag>translation</tag>"))
        self.assertTrue(core.is_translation_valid("<tag>original</tag>", "This is a <tag>translation</tag>"))

class TestDataProcessing(unittest.TestCase):
    def test_collect_text_nodes(self):
        """Test collecting various text nodes."""
        data = {
            "greeting": {"#text": "こんにちは"},
            "farewell": {"#text": "さようなら"},
            "nested": {"question": {"#text": "誰？"}},
            "english": {"#text": "Hello"},
            "processed": {"#text": "jp_text:::おはよう"}
        }
        with patch('translator_lib.core.detect') as mock_detect:
            mock_detect.side_effect = lambda t: 'ja' if t in ["こんにちは", "さようなら", "誰？"] else 'en'
            nodes = []
            core.collect_text_nodes(data, nodes)
            self.assertEqual(len(nodes), 3)
            texts = {n["#text"] for n in nodes}
            self.assertEqual(texts, {"こんにちは", "さようなら", "誰？"})

    def test_cleanup_markers(self):
        """Test cleaning up processing markers."""
        data = {
            "items": [
                {"item": {"#text": "jp_text:::one"}},
                {"item": {"#text": "two"}},
                {"item": {"#text": "jp_text:::three"}}
            ]
        }
        core.cleanup_markers(data)
        self.assertEqual(data["items"][0]["item"]["#text"], "one")
        self.assertEqual(data["items"][1]["item"]["#text"], "two")
        self.assertEqual(data["items"][2]["item"]["#text"], "three")

if __name__ == '__main__':
    unittest.main()
