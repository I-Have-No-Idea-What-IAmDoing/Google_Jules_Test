import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
from langdetect import LangDetectException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestCoreFunctionality(unittest.TestCase):

    def setUp(self):
        self.api_base_url = core.DEFAULT_API_BASE_URL
        self.direct_args = {
            "model_name": "direct-model", "api_base_url": self.api_base_url,
            "refine_mode": False, "verbose": False
        }
        self.refine_args = {
            "model_name": "refine-model", "draft_model": "draft-model",
            "api_base_url": self.api_base_url, "refine_mode": True, "verbose": False
        }

    # === Test Group: Translation Logic ===

    @patch('translator_lib.core._api_request')
    @patch('translator_lib.core.ensure_model_loaded')
    def test_get_translation_direct_mode(self, mock_ensure_model, mock_api_call):
        """Test the direct translation path."""
        mock_api_call.return_value = "Direct Translation"
        result = core.get_translation("text", **self.direct_args)

        mock_ensure_model.assert_called_once_with("direct-model", self.api_base_url, False)
        mock_api_call.assert_called_once()
        self.assertEqual(result, "Direct Translation")

    @patch('translator_lib.core._api_request')
    @patch('translator_lib.core.ensure_model_loaded')
    def test_get_translation_refine_mode(self, mock_ensure_model, mock_api_call):
        """Test the full refinement workflow."""
        # Simulate 6 draft calls and 1 refine call
        mock_api_call.side_effect = ["d1", "d2", "d3", "d4", "d5", "d6", "Final Refined Text"]

        result = core.get_translation("text", **self.refine_args)

        # Check that model loading was handled correctly
        self.assertEqual(mock_ensure_model.call_count, 2)
        mock_ensure_model.assert_has_calls([
            call("draft-model", self.api_base_url, False),
            call("refine-model", self.api_base_url, False)
        ], any_order=True) # The order of loading might vary

        # Check that the API was called 7 times (6 drafts + 1 refine)
        self.assertEqual(mock_api_call.call_count, 7)

        # Check the final result
        self.assertEqual(result, "Final Refined Text")

        # Check that the final call used the refinement prompt
        final_call_prompt = mock_api_call.call_args[0][1]['prompt']
        self.assertIn("Analyze the following multiple", final_call_prompt)
        self.assertIn("d6", final_call_prompt)


    # === Test Group: Language Detection ===

    @patch('translator_lib.core.detect')
    @patch('translator_lib.core.get_translation')
    def test_process_data_skips_english(self, mock_get_translation, mock_detect):
        """Test that English text is skipped."""
        mock_detect.return_value = 'en'
        pbar = MagicMock()
        data = {'#text': 'hello world'}

        core.process_data(data, pbar, self.direct_args)

        mock_get_translation.assert_not_called()

    # === Test Group: Main Orchestrator ===

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={'#text': 'こんにちは'})
    @patch('translator_lib.core.process_data')
    def test_translate_file_happy_path(self, mock_process, mock_deserialize, mock_open, mock_exists):
        """Test the main success path of the orchestrator."""
        core.translate_file(**self.direct_args, input_path="input.txt")
        mock_process.assert_called_once()


if __name__ == '__main__':
    unittest.main()
