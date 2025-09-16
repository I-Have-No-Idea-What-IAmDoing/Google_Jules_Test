import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import requests
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestCoreFunctionality(unittest.TestCase):

    def setUp(self):
        self.api_base_url = core.DEFAULT_API_BASE_URL
        self.sample_data = {'greeting': {'#text': 'hello'}, 'farewell': {'#text': 'goodbye'}}

    # === Test Group: Utilities ===
    def test_count_text_nodes(self):
        self.assertEqual(core.count_text_nodes(self.sample_data), 2)
        self.assertEqual(core.count_text_nodes({'key': 'jp_text:::processed'}), 0)

    # === Test Group: API Functions ===
    @patch('requests.post')
    def test_translate_text_success(self, mock_post):
        mock_post.return_value.json.return_value = {"choices": [{"text": "Success"}]}
        self.assertEqual(core.translate_text("text", "model", self.api_base_url), "Success")

    @patch('time.sleep', return_value=None)
    @patch('requests.post')
    def test_translate_text_retry_logic(self, mock_post, mock_sleep):
        mock_post.side_effect = [requests.exceptions.RequestException("Fail"), MagicMock(json=MagicMock(return_value={"choices": [{"text": "Success"}]}))]
        self.assertEqual(core.translate_text("text", "model", self.api_base_url), "Success")
        self.assertEqual(mock_post.call_count, 2)

    @patch('time.sleep', return_value=None)
    @patch('requests.post')
    @patch('translator_lib.core.MAX_BACKOFF_SECONDS', 3) # Set a low max backoff for this test
    def test_translate_text_max_backoff_error(self, mock_post, mock_sleep):
        """Test that retry stops if backoff exceeds max."""
        # The 3rd attempt would sleep for 2**2=4s, which is > 3.
        # So it should try twice and then raise the error on the 3rd attempt.
        mock_post.side_effect = requests.exceptions.RequestException("Fail")

        with self.assertRaises(TimeoutError):
            core.translate_text("text", "model", self.api_base_url)

        # It should fail on the 3rd attempt, so 3 calls should have been made
        self.assertEqual(mock_post.call_count, 3)

    @patch('requests.get')
    def test_get_current_model_success(self, mock_get):
        mock_get.return_value.json.return_value = {"data": [{"id": "model-a"}]}
        self.assertEqual(core.get_current_model(self.api_base_url), "model-a")

    @patch('requests.get')
    def test_list_available_models_success(self, mock_get):
        mock_get.return_value.json.return_value = {"model_names": ["model-a", "model-b"]}
        self.assertEqual(core.list_available_models(self.api_base_url), ["model-a", "model-b"])

    # === Test Group: End-to-End translate_file ===
    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={'#text': 'text'})
    @patch('translator_lib.core.get_current_model', return_value='test-model')
    @patch('translator_lib.core.list_available_models', return_value=['test-model'])
    @patch('translator_lib.core.load_model')
    @patch('translator_lib.core.process_data')
    def test_translate_file_happy_path(self, mock_process, mock_load, mock_list, mock_get, mock_deserialize, mock_open, mock_exists):
        """Test the main success path with no checkpoint and model already loaded."""
        core.translate_file("input.txt", "test-model", self.api_base_url, quiet=True)
        mock_load.assert_not_called()
        mock_process.assert_called_once()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={'#text': 'text'})
    @patch('translator_lib.core.get_current_model', return_value='wrong-model')
    @patch('translator_lib.core.list_available_models', return_value=['correct-model'])
    @patch('translator_lib.core.load_model', return_value=True)
    @patch('translator_lib.core.process_data')
    def test_translate_file_model_loading(self, mock_process, mock_load, mock_list, mock_get, mock_deserialize, mock_open, mock_exists):
        """Test that the correct model is loaded if not already active."""
        core.translate_file("input.txt", "correct-model", self.api_base_url, quiet=True)
        mock_load.assert_called_once_with("correct-model", self.api_base_url, False)
        mock_process.assert_called_once()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.get_current_model', return_value='wrong-model')
    @patch('translator_lib.core.list_available_models', return_value=['model-a'])
    def test_translate_file_invalid_model_name(self, mock_list, mock_get, mock_open, mock_exists):
        """Test that an error is raised for a model name that doesn't exist."""
        with self.assertRaisesRegex(ValueError, "Model 'invalid-model' not found on server"):
            core.translate_file("input.txt", "invalid-model", self.api_base_url, quiet=True)

    @patch('os.path.exists', side_effect=[False, True])
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={'#text': 'text'})
    @patch('translator_lib.core.get_current_model', return_value='test-model')
    @patch('translator_lib.core.list_available_models', return_value=['test-model'])
    @patch('translator_lib.core.translate_text', return_value='translated')
    @patch('os.remove')
    @patch('json.dump')
    def test_translate_file_checkpoint_cleanup(self, mock_json_dump, mock_os_remove, mock_translate, mock_list, mock_get, mock_deserialize, mock_open, mock_exists):
        """Test that the checkpoint file is created and then deleted on success."""
        core.translate_file("input.txt", "test-model", self.api_base_url, checkpoint_freq=1, quiet=True)
        mock_json_dump.assert_called()
        mock_os_remove.assert_called_once_with("input.txt.checkpoint.json")

if __name__ == '__main__':
    unittest.main()
