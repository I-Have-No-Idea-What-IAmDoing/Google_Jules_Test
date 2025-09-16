import unittest
from unittest.mock import patch, mock_open
import sys
import os
from io import StringIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from text_translator import cli
from translator_lib import core

class TestCommandLineInterface(unittest.TestCase):

    @patch('text_translator.cli.translate_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_default_args(self, mock_stdout, mock_translate_file):
        """Test the CLI with default arguments."""
        test_args = ["cli.py", "input.txt", "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        # Check that the core function was called with correct default values
        mock_translate_file.assert_called_once_with(
            input_path="input.txt",
            model_name="test-model",
            api_base_url=core.DEFAULT_API_BASE_URL,
            checkpoint_freq=10,
            verbose=False,
            quiet=False
        )

    @patch('text_translator.cli.translate_file')
    @patch('os.environ.get', return_value="http://env.var.url/v1")
    def test_cli_url_from_env_var(self, mock_env, mock_translate_file):
        """Test that the API URL is taken from an environment variable."""
        test_args = ["cli.py", "input.txt", "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        # Check that the URL from the env var was used
        self.assertEqual(mock_translate_file.call_args[1]['api_base_url'], "http://env.var.url/v1")

    @patch('text_translator.cli.translate_file')
    def test_cli_url_from_arg(self, mock_translate_file):
        """Test that the API URL from the CLI argument takes precedence."""
        test_args = ["cli.py", "input.txt", "--model", "test-model", "--api-base-url", "http://cli.arg.url/v1"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertEqual(mock_translate_file.call_args[1]['api_base_url'], "http://cli.arg.url/v1")

    @patch('text_translator.cli.translate_file')
    def test_cli_verbose_flag(self, mock_translate_file):
        """Test the --verbose flag."""
        test_args = ["cli.py", "input.txt", "--model", "test-model", "--verbose"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertTrue(mock_translate_file.call_args[1]['verbose'])
        self.assertFalse(mock_translate_file.call_args[1]['quiet'])

    @patch('text_translator.cli.translate_file')
    def test_cli_quiet_flag(self, mock_translate_file):
        """Test the --quiet flag."""
        test_args = ["cli.py", "input.txt", "--model", "test-model", "--quiet"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertFalse(mock_translate_file.call_args[1]['verbose'])
        self.assertTrue(mock_translate_file.call_args[1]['quiet'])

    @patch('text_translator.cli.translate_file', side_effect=FileNotFoundError("File not found"))
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_file_not_found_error(self, mock_stderr, mock_translate_file):
        """Test that the CLI handles FileNotFoundError and exits with status 1."""
        test_args = ["cli.py", "nonexistent.txt", "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            self.assertEqual(cm.exception.code, 1)

        self.assertIn("Error: Input file not found", mock_stderr.getvalue())

if __name__ == '__main__':
    unittest.main()
