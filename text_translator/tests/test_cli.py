import unittest
from unittest.mock import patch
import sys
import os
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from text_translator import cli
from translator_lib import core

class TestCommandLineInterface(unittest.TestCase):

    @patch('text_translator.cli.translate_file')
    def test_cli_default_args(self, mock_translate_file):
        """Test the CLI with default arguments passes correct kwargs."""
        test_args = ["cli.py", "input.txt", "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        expected_args = {
            "input_path": "input.txt", "model_name": "test-model",
            "api_base_url": core.DEFAULT_API_BASE_URL, "checkpoint_freq": 10,
            "verbose": False, "quiet": False,
            "refine_mode": False, "draft_model": None
        }
        mock_translate_file.assert_called_once_with(**expected_args)

    @patch('text_translator.cli.translate_file')
    def test_cli_refine_mode_args(self, mock_translate_file):
        """Test that --refine and --draft-model are passed correctly."""
        test_args = [
            "cli.py", "input.txt",
            "--model", "refiner-model",
            "--refine",
            "--draft-model", "drafter-model"
        ]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertTrue(mock_translate_file.call_args[1]['refine_mode'])
        self.assertEqual(mock_translate_file.call_args[1]['draft_model'], "drafter-model")
        self.assertEqual(mock_translate_file.call_args[1]['model_name'], "refiner-model")

    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_refine_without_draft_model_exits(self, mock_stderr):
        """Test that the CLI exits if --refine is used without --draft-model."""
        test_args = [
            "cli.py", "input.txt",
            "--model", "refiner-model",
            "--refine"
        ]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            self.assertEqual(cm.exception.code, 2) # Argparse error exit code

        self.assertIn("--draft-model is required when using --refine", mock_stderr.getvalue())

    @patch('text_translator.cli.translate_file', side_effect=Exception("Core library error"))
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_generic_error_handling(self, mock_stderr, mock_translate_file):
        """Test that the CLI handles generic exceptions and exits with status 1."""
        test_args = ["cli.py", "input.txt", "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 1)

        self.assertIn("A critical error occurred: Core library error", mock_stderr.getvalue())

if __name__ == '__main__':
    unittest.main()
