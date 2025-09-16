import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from translator_lib import core

class TestCoreBatchWorkflow(unittest.TestCase):

    def setUp(self):
        self.api_base_url = core.DEFAULT_API_BASE_URL
        self.sample_data = {
            'greeting': {'#text': 'こんにちは'},
            'farewell': {'#text': 'さようなら'}
        }
        self.nodes_to_translate = [
            self.sample_data['greeting'],
            self.sample_data['farewell']
        ]

    @patch('translator_lib.core.detect', return_value='ja')
    def test_collect_text_nodes(self, mock_detect):
        nodes = []
        core.collect_text_nodes(self.sample_data, nodes)
        self.assertEqual(len(nodes), 2)
        self.assertIs(nodes[0], self.sample_data['greeting'])

    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core._api_request')
    def test_direct_translation_batch(self, mock_api_request, mock_ensure_model):
        mock_api_request.return_value = {"choices": [{"text": "translated"}]}
        pbar = MagicMock()
        pbar.update = MagicMock()
        core.get_direct_translation_batch(self.nodes_to_translate, "model", self.api_base_url, pbar)
        self.assertEqual(mock_api_request.call_count, 2)
        self.assertEqual(pbar.update.call_count, 2)

    @patch('translator_lib.core.ensure_model_loaded')
    @patch('translator_lib.core._api_request')
    def test_refinement_translation_batch(self, mock_api_request, mock_ensure_model):
        mock_api_request.return_value = {"choices": [{"text": "text"}]}
        pbar = MagicMock()
        pbar.update = MagicMock()
        core.get_refinement_translation_batch(self.nodes_to_translate, "d", "r", self.api_base_url, pbar)
        self.assertEqual(mock_ensure_model.call_count, 2)
        self.assertEqual(mock_api_request.call_count, 14)
        # pbar.update(0.5) is called twice per node. 2 nodes * 2 = 4 calls.
        self.assertEqual(pbar.update.call_count, 4)

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.get_direct_translation_batch')
    def test_translate_file_dispatches_to_direct(self, mock_direct_batch, mock_collect, mock_deserialize, mock_open, mock_exists):
        # Configure the mock to populate the list
        mock_collect.side_effect = lambda data, lst: lst.append("a node")
        args = {"refine_mode": False, "model_name": "m", "api_base_url": "url", "input_path": "path"}
        core.translate_file(**args)
        mock_direct_batch.assert_called_once()

    @patch('os.path.exists', return_value=False)
    @patch('builtins.open')
    @patch('translator_lib.core.parser.deserialize')
    @patch('translator_lib.core.collect_text_nodes')
    @patch('translator_lib.core.get_refinement_translation_batch')
    def test_translate_file_dispatches_to_refine(self, mock_refine_batch, mock_collect, mock_deserialize, mock_open, mock_exists):
        # Configure the mock to populate the list
        mock_collect.side_effect = lambda data, lst: lst.append("a node")
        args = {"refine_mode": True, "model_name": "m", "draft_model": "d", "api_base_url": "url", "input_path": "path"}
        core.translate_file(**args)
        mock_refine_batch.assert_called_once()

if __name__ == '__main__':
    unittest.main()
