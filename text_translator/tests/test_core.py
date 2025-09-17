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
    @patch('translator_lib.core._api_request') # Mock the lowest level
    @patch('time.sleep') # Mock time.sleep to speed up tests
    def test_refinement_workflow(self, mock_sleep, mock_api_request, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the end-to-end refinement translation workflow."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])

        mock_api_request.side_effect = [
            # ensure_model_loaded for draft-model
            {"model_name": "initial-model"}, # get current model
            {"result": "success"},          # load draft-model
            # get_translation calls for drafts
            {"choices": [{"text": "d1"}]}, {"choices": [{"text": "d2"}]},
            # ensure_model_loaded for refine-model
            {"model_name": "draft-model"},   # get current model
            {"result": "success"},          # load refine-model
            # refinement call
            {"choices": [{"text": "final_refined"}]}
        ]

        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "num_drafts": 2
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




    @patch('translator_lib.core._api_request')
    def test_get_translation_with_reasoning(self, mock_api_request):
        """Test get_translation with reasoning mode enabled."""
        mock_api_request.return_value = {
            "choices": [{"text": "Reasoning: This is my reasoning.\nTranslation: This is the translation."}]
        }

        result = core.get_translation(
            text="original",
            model_name="test-model",
            api_base_url="http://test.url",
            use_reasoning=True
        )

        self.assertEqual(result, "This is the translation.")
        prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertIn("First, provide a step-by-step reasoning", prompt)
        self.assertIn("Original text: original", prompt)

    @patch('translator_lib.core._api_request')
    def test_get_translation_with_reasoning_no_marker(self, mock_api_request):
        """Test get_translation with reasoning mode when the marker is missing."""
        mock_api_request.return_value = {
            "choices": [{"text": "This is just the translation."}]
        }

        result = core.get_translation(
            text="original",
            model_name="test-model",
            api_base_url="http://test.url",
            use_reasoning=True
        )

        self.assertEqual(result, "This is just the translation.")

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
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    @patch('translator_lib.core._api_request')
    def test_refinement_workflow_with_draft_reasoning(self, mock_api_request, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the refinement workflow with reasoning for drafts."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        mock_api_request.return_value = {"choices": [{"text": "final_refined"}]}
        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "num_drafts": 2, "reasoning_for": "draft"
        }

        core.translate_file(**args)

        self.assertEqual(mock_get_translation.call_count, 2)
        _, kwargs = mock_get_translation.call_args
        self.assertTrue(kwargs.get('use_reasoning'))

        final_call_prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertNotIn("First, provide a step-by-step reasoning", final_call_prompt)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_translation')
    @patch('translator_lib.core._api_request')
    def test_refinement_workflow_with_refine_reasoning(self, mock_api_request, mock_get_translation, mock_ensure_model, mock_collect, mock_deserialize, mock_open, mock_exists):
        """Test the refinement workflow with reasoning for refinement."""
        mock_collect.side_effect = lambda data, lst: lst.extend([{'#text': 'one'}])
        mock_api_request.return_value = {"choices": [{"text": "Translation: final_refined"}]}
        args = {
            **self.base_args, "refine_mode": True, "model_name": "refine-model",
            "draft_model": "draft-model", "num_drafts": 1, "reasoning_for": "refine"
        }

        core.translate_file(**args)

        mock_get_translation.assert_called_once()
        _, kwargs = mock_get_translation.call_args
        self.assertFalse(kwargs.get('use_reasoning'))

        final_call_prompt = mock_api_request.call_args[0][1]['prompt']
        self.assertIn("First, provide a step-by-step reasoning", final_call_prompt)

class TestModelLoading(unittest.TestCase):

    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_already_loaded(self, mock_api_request):
        """Test ensure_model_loaded when the model is already loaded."""
        mock_api_request.return_value = {"model_name": "test-model"}

        core.ensure_model_loaded("test-model", "http://test.url")

        mock_api_request.assert_called_once_with("internal/model/info", {}, "http://test.url", is_get=True, debug=0)

    @patch('translator_lib.core._api_request')
    def test_ensure_model_loaded_needs_loading(self, mock_api_request):
        """Test ensure_model_loaded when a different model is loaded."""
        mock_api_request.side_effect = [
            {"model_name": "other-model"},  # First call for info
            {"result": "success"}          # Second call for load
        ]

        core.ensure_model_loaded("test-model", "http://test.url")

        self.assertEqual(mock_api_request.call_count, 2)
        mock_api_request.assert_has_calls([
            call("internal/model/info", {}, "http://test.url", is_get=True, debug=0),
            call("internal/model/load", {"model_name": "test-model"}, "http://test.url", timeout=300, debug=0)
        ])

if __name__ == '__main__':
    unittest.main()
