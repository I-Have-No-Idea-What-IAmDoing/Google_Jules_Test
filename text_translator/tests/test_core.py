import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestCoreBugfix(unittest.TestCase):

    def setUp(self):
        self.api_base_url = core.DEFAULT_API_BASE_URL
        self.direct_args = {
            "input_path": "input.txt", "model_name": "direct-model",
            "api_base_url": self.api_base_url, "quiet": True, "verbose": False
        }

    @patch('requests.get')
    def test_get_current_model_logic(self, mock_get):
        """Test the logic inside get_current_model."""
        mock_get.return_value.json.return_value = {"data": [{"id": "model-a"}]}
        mock_get.return_value.raise_for_status = MagicMock()

        core.get_current_model(self.api_base_url)
        # Check the underlying request call without being too specific about timeout
        mock_get.assert_called_once()
        self.assertTrue(mock_get.call_args[0][0].endswith("/models"))

    @patch('requests.get')
    @patch('requests.post')
    @patch('time.sleep', return_value=None)
    def test_ensure_model_loaded_switches_model(self, mock_sleep, mock_post, mock_get):
        """Test that ensure_model_loaded calls the load API when models differ."""
        mock_get.return_value.json.return_value = {"data": [{"id": "wrong-model"}]}
        mock_get.return_value.raise_for_status = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        core.ensure_model_loaded("correct-model", self.api_base_url, verbose=True)

        mock_get.assert_called_once()
        mock_post.assert_called_once_with(
            f"{self.api_base_url}/internal/model/load",
            json={"model_name": "correct-model"},
            headers=unittest.mock.ANY,
            timeout=300
        )

    @patch('requests.get')
    @patch('requests.post')
    def test_ensure_model_loaded_does_nothing_if_correct(self, mock_post, mock_get):
        """Test that ensure_model_loaded does nothing if the correct model is loaded."""
        mock_get.return_value.json.return_value = {"data": [{"id": "correct-model"}]}
        mock_get.return_value.raise_for_status = MagicMock()

        core.ensure_model_loaded("correct-model", self.api_base_url)

        mock_get.assert_called_once()
        mock_post.assert_not_called()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize', return_value={'#text': 'こんにちは'})
    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core.get_direct_translation')
    def test_translate_file_calls_ensure_model(self, mock_get_translation, mock_ensure_model, mock_deserialize, mock_open, mock_exists):
        """Test that the main orchestrator calls the model loading logic."""
        core.translate_file(**self.direct_args)
        mock_ensure_model.assert_called_once_with("direct-model", self.api_base_url, False)
        mock_get_translation.assert_called_once()


if __name__ == '__main__':
    unittest.main()
