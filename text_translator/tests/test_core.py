import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestFinalCoreWorkflow(unittest.TestCase):

    def setUp(self):
        self.base_args = {
            "input_path": "input.txt", "api_base_url": "http://test.url",
            "quiet": True, "verbose": False, "output_file": None
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
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core._api_request') # Mock the lowest level
    def test_refinement_workflow(self, mock_api_request, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the end-to-end refinement translation workflow."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        # 6 drafts + 1 refinement call
        mock_api_request.side_effect = [
            # Drafts
            {"choices": [{"text": "d1"}]}, {"choices": [{"text": "d2"}]},
            {"choices": [{"text": "d3"}]}, {"choices": [{"text": "d4"}]},
            {"choices": [{"text": "d5"}]}, {"choices": [{"text": "d6"}]},
            # Refinement
            {"choices": [{"text": "final_refined"}]}
        ]

        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "num_drafts": 6
        }

        core.translate_file(**args)

        self.assertEqual(mock_ensure_model.call_count, 2)
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

if __name__ == '__main__':
    unittest.main()
