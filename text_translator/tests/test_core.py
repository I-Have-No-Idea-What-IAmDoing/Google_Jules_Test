import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import requests
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestFinalCoreWorkflow(unittest.TestCase):

    def setUp(self):
        self.base_args = {
            "input_path": "input.txt", "api_base_url": "http://test.url",
            "quiet": True, "verbose": False, "output_file": None, "debug": 0,
            "glossary_text": None, "reasoning_for": None
        }

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
        args = {**self.base_args, "refine_mode": False, "model_name": "direct-model"}

        core.translate_file(**args)

        mock_ensure_model.assert_called_once_with("direct-model", "http://test.url", False, debug=0)
        mock_get_translation.assert_called_once()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core._api_request') # Mock the lowest level
    @patch('time.sleep') # Mock time.sleep to speed up tests
    def test_refinement_workflow(self, mock_sleep, mock_api_request, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the end-to-end refinement translation workflow."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])

        mock_api_request.side_effect = [
            {"model_name": "initial-model"},
            {"result": "success"},
            {"choices": [{"text": "This is a valid draft translation."}]},
            {"choices": [{"text": "This is another valid draft."}]},
            {"model_name": "draft-model"},
            {"result": "success"},
            {"choices": [{"text": "This is the final refined output."}]}
        ]

        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "num_drafts": 2, "glossary_for": "all"
        }

        core.translate_file(**args)

        self.assertEqual(mock_api_request.call_count, 7)
        final_call_prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertIn("Refine these translations", final_call_prompt)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={})
    @patch('translator_lib.core.collect_text_nodes')
    def test_no_nodes_to_translate(self, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test that the function exits early if no text nodes are found."""
        mock_collect.side_effect = lambda data, lst: None
        with patch('translator_lib.core.ensure_model_loaded') as mock_ensure_model:
            args = {**self.base_args, "refine_mode": False, "model_name": "direct-model"}
            core.translate_file(**args)
            mock_ensure_model.assert_not_called()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    def test_debug_flag_propagation_direct(self, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test that the debug flag is propagated in direct mode."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        args = {**self.base_args, "refine_mode": False, "model_name": "direct-model", "debug": 2}

        core.translate_file(**args)

        mock_ensure_model.assert_called_once_with("direct-model", "http://test.url", False, debug=2)
        mock_get_translation.assert_called_once()
        _, kwargs = mock_get_translation.call_args
        self.assertEqual(kwargs.get('debug'), 2)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    def test_direct_translation_with_reasoning(self, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the direct translation workflow with reasoning enabled."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        args = {**self.base_args, "refine_mode": False, "model_name": "direct-model", "reasoning_for": "main"}

        core.translate_file(**args)

        mock_get_translation.assert_called_once()
        _, kwargs = mock_get_translation.call_args
        self.assertTrue(kwargs.get('use_reasoning'))

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core._get_refined_translation')
    def test_refinement_translation_line_by_line(self, mock_get_refined_translation, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the refinement translation workflow with line-by-line mode enabled."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'line one\nline two'}])
        mock_get_refined_translation.side_effect = lambda original_text, **kwargs: original_text

        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "line_by_line": True, "num_drafts": 6,
            "glossary_for": "all"
        }

        core.translate_file(**args)

        self.assertEqual(mock_get_refined_translation.call_count, 2)
        self.assertEqual(mock_get_refined_translation.call_args_list[0][1]['original_text'], 'line one')
        self.assertEqual(mock_get_refined_translation.call_args_list[1][1]['original_text'], 'line two')

    @patch('os.path.exists', return_value=True)
    def test_translate_file_output_exists(self, mock_exists):
        """Test that the function skips if the output file already exists."""
        with patch('builtins.open') as mock_open:
            args = {**self.base_args, "output_file": "out.txt"}
            core.translate_file(**args)
            mock_open.assert_not_called()

class TestGetTranslation(unittest.TestCase):
    @patch('translator_lib.core.is_translation_valid', return_value=True)
    @patch('translator_lib.core._api_request')
    def test_get_translation_with_glossary(self, mock_api_request, mock_is_valid):
        """Test that a glossary is correctly added to the prompt."""
        mock_api_request.return_value = {"choices": [{"text": "translated"}]}
        core.get_translation("text", "model", "url", glossary_text="glossary")
        prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertIn("Please use this glossary", prompt)

    @patch('translator_lib.core.is_translation_valid', side_effect=[False, True])
    @patch('translator_lib.core._api_request')
    def test_get_translation_retry_on_invalid(self, mock_api, mock_valid):
        """Test that get_translation retries if the first result is invalid."""
        mock_api.return_value = {"choices": [{"text": "translated"}]}
        core.get_translation("text", "model", "url")
        self.assertEqual(mock_api.call_count, 2)

    @patch('translator_lib.core._api_request', side_effect=ConnectionError)
    def test_get_translation_connection_error(self, mock_api):
        """Test that get_translation raises the final ConnectionError after retries."""
        with self.assertRaises(ConnectionError):
            core.get_translation("text", "model", "url")
        self.assertEqual(mock_api.call_count, 3)

    @patch('translator_lib.core._api_request')
    def test_get_translation_with_reasoning(self, mock_api_request):
        """Test get_translation with reasoning mode enabled."""
        with patch('translator_lib.core.is_translation_valid', return_value=True):
            mock_api_request.return_value = {
                "choices": [{"text": "Reasoning: This is my reasoning.\nTranslation: This is the translation."}]
            }
            result = core.get_translation("original", "test-model", "http://test.url", use_reasoning=True)
            self.assertEqual(result, "This is the translation.")

    @patch('translator_lib.core._api_request')
    def test_get_translation_with_reasoning_no_marker(self, mock_api_request):
        """Test get_translation with reasoning mode when the marker is missing."""
        with patch('translator_lib.core.is_translation_valid', return_value=True):
            mock_api_request.return_value = {"choices": [{"text": "This is just the translation."}]}
            result = core.get_translation("original", "test-model", "http://test.url", use_reasoning=True)
            self.assertEqual(result, "original")
            self.assertEqual(mock_api_request.call_count, 3)

class TestApiRequest(unittest.TestCase):
    @patch('requests.post')
    def test_api_request_debug_printing(self, mock_post):
        mock_post.return_value.json.return_value = {"status": "ok"}
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            core._api_request("test/endpoint", {}, "http://test.url", debug=1)
            self.assertIn("DEBUG (L1)", mock_stderr.getvalue())
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            core._api_request("test/endpoint", {}, "http://test.url", debug=3)
            self.assertIn("DEBUG (L3)", mock_stderr.getvalue())

    @patch('requests.get')
    def test_api_request_get_method(self, mock_get):
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"data": "test"}
        core._api_request("test/endpoint", {}, "http://test.url", is_get=True)
        mock_get.assert_called_once()

    @patch('requests.post', side_effect=requests.exceptions.RequestException("Test error"))
    def test_api_request_connection_error(self, mock_post):
        with self.assertRaises(ConnectionError):
            core._api_request("test/endpoint", {}, "http://test.url")

class TestModelLoading(unittest.TestCase):
    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_already_loaded(self, mock_api_request):
        mock_api_request.return_value = {"model_name": "test-model"}
        core.ensure_model_loaded("test-model", "http://test.url")
        mock_api_request.assert_called_once_with("internal/model/info", {}, "http://test.url", is_get=True, debug=0)

    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_needs_loading(self, mock_api_request):
        mock_api_request.side_effect = [{"model_name": "other-model"}, {"result": "success"}]
        core.ensure_model_loaded("test-model", "http://test.url")
        self.assertEqual(mock_api_request.call_count, 2)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_verbose(self, mock_api_request, mock_stdout):
        mock_api_request.side_effect = [{"model_name": "other"}, {"result": "ok"}]
        core.ensure_model_loaded("test-model", "http://test.url", verbose=True)
        self.assertIn("Switching model", mock_stdout.getvalue())
        self.assertIn("Model loaded", mock_stdout.getvalue())

    @patch('translator_lib.core._api_request', side_effect=ConnectionError("Info error"))
    def test_ensure_model_loaded_connection_error_info(self, mock_api_request):
        with self.assertRaisesRegex(ConnectionError, "Error getting current model"):
            core.ensure_model_loaded("test-model", "http://test.url")

    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_connection_error_load(self, mock_api_request):
        mock_api_request.side_effect = [{"model_name": "other"}, ConnectionError("Load error")]
        with self.assertRaisesRegex(ConnectionError, "Failed to load model"):
            core.ensure_model_loaded("test-model", "http://test.url")

class TestTranslationValidation(unittest.TestCase):
    def test_validation_empty_string(self):
        self.assertFalse(core.is_translation_valid("original", ""))

    def test_validation_identical(self):
        self.assertFalse(core.is_translation_valid("original", "original"))

    def test_validation_refusal(self):
        self.assertFalse(core.is_translation_valid("original", "I'm sorry, I cannot do that."))

    def test_validation_not_english(self):
        with patch('translator_lib.core.detect', return_value='ja'):
            self.assertFalse(core.is_translation_valid("original", "これは日本語です"))

    def test_validation_contains_original(self):
        self.assertFalse(core.is_translation_valid("this is a long original text", "this is a long original text repeated"))

    def test_validation_lang_detect_exception(self):
        with patch('translator_lib.core.detect', side_effect=core.LangDetectException(0, "error")):
            self.assertTrue(core.is_translation_valid("original", "a valid translation"))

    def test_validation_valid(self):
        with patch('translator_lib.core.detect', return_value='en'):
            self.assertTrue(core.is_translation_valid("original", "a valid translation"))

class TestDataProcessing(unittest.TestCase):
    def test_collect_text_nodes_with_list(self):
        data = [{"key": [{"#text": "one"}]}, {"#text": "two"}]
        nodes = []
        core.collect_text_nodes(data, nodes)
        self.assertEqual(len(nodes), 2)

    @patch('translator_lib.core.detect', side_effect=['en', 'ja'])
    def test_collect_text_nodes_skips_english_and_processed(self, mock_detect):
        data = {"english_node": {"#text": "Hello"}, "jp_node": {"#text": "こんにちは"}, "processed_node": {"#text": "jp_text:::"}}
        nodes = []
        core.collect_text_nodes(data, nodes)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0], data['jp_node'])

    def test_cleanup_markers_with_list(self):
        data = [{"key": [{"#text": "jp_text:::one"}]}, {"#text": "jp_text:::two"}]
        core.cleanup_markers(data)
        self.assertEqual(data[0]['key'][0]['#text'], 'one')
        self.assertEqual(data[1]['#text'], 'two')

if __name__ == '__main__':
    unittest.main()
