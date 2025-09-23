import unittest
from unittest.mock import patch, call, ANY
import os
from io import StringIO
import tempfile
import shutil
import sys

from text_translator import cli
from text_translator.translator_lib.options import TranslationOptions

class TestCommandLineInterface(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for tests."""
        self.test_dir = tempfile.mkdtemp()
        self.input_file = os.path.join(self.test_dir, "input.txt")
        with open(self.input_file, "w") as f:
            f.write("test")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_single_file(self, mock_process_single_file, mock_check_server_status, mock_model_loader):
        """Test the CLI with a single file input."""
        # Setup mock for model_loader
        mock_model_loader.load_model_configs.return_value = {"test-model": {"params": {}}}
        mock_model_loader.get_model_config.return_value = {"params": {"temp": 0.5}}

        test_args = ["cli.py", self.input_file, "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        mock_check_server_status.assert_called_once()
        mock_process_single_file.assert_called_once_with(self.input_file, None, ANY)

        # Check that the third argument is a TranslationOptions object
        passed_options = mock_process_single_file.call_args[0][2]
        self.assertIsInstance(passed_options, TranslationOptions)
        self.assertEqual(passed_options.model_name, "test-model")
        self.assertEqual(passed_options.model_config, {"params": {"temp": 0.5}})

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_directory')
    def test_cli_directory_processing(self, mock_process_directory, mock_check_server_status, mock_model_loader):
        """Test the CLI with a directory input."""
        mock_model_loader.load_model_configs.return_value = {"test-model": {}}
        mock_model_loader.get_model_config.return_value = {}

        test_args = ["cli.py", self.test_dir, "--model", "test-model", "--quiet"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        mock_check_server_status.assert_called_once()
        mock_process_directory.assert_called_once_with(ANY, ANY)

        # Check that the second argument is a TranslationOptions object
        passed_options = mock_process_directory.call_args[0][1]
        self.assertIsInstance(passed_options, TranslationOptions)

    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_version_flag(self, mock_stdout):
        """Test the --version flag."""
        test_args = ["cli.py", "--version"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit):
                cli.main()

        self.assertIn(cli.__version__, mock_stdout.getvalue())

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_argument_validation_errors(self, mock_stderr, mock_check_server_status, mock_model_loader):
        """Test that the CLI exits on various argument validation errors."""
        mock_model_loader.load_model_configs.return_value = {"r": {}, "m": {}}
        mock_model_loader.get_model_config.return_value = {}

        # Refine without draft model
        test_args = ["cli.py", self.input_file, "--model", "r", "--refine"]
        with patch.object(sys, 'argv', test_args), self.assertRaises(SystemExit):
            cli.main()
        self.assertIn("--draft-model is required", mock_stderr.getvalue())

        # Non-existent input path
        test_args = ["cli.py", "nonexistent.txt", "--model", "m"]
        with patch.object(sys, 'argv', test_args), self.assertRaises(SystemExit):
            cli.main()
        self.assertIn("Input path does not exist", mock_stderr.getvalue())

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_glossary_validation_error(self, mock_stderr, mock_check_server_status, mock_model_loader):
        """Test that the CLI exits if --glossary-for is used without a glossary."""
        mock_model_loader.load_model_configs.return_value = {"m": {}}
        mock_model_loader.get_model_config.return_value = {}

        test_args = ["cli.py", self.input_file, "--model", "m", "--glossary-for", "all"]
        with patch.object(sys, 'argv', test_args), self.assertRaises(SystemExit):
            cli.main()
        self.assertIn("--glossary-for requires a glossary", mock_stderr.getvalue())

    @patch('text_translator.cli.translate_file', side_effect=Exception("Core error"))
    @patch('sys.stderr', new_callable=StringIO)
    def test_process_single_file_error_handling(self, mock_stderr, mock_translate_file):
        """Test that process_single_file handles exceptions gracefully."""
        options = TranslationOptions(input_path=self.input_file, model_name="test")
        cli.process_single_file(self.input_file, None, options)
        self.assertIn("Error processing file", mock_stderr.getvalue())

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_debug_flag(self, mock_process_single_file, mock_check_server_status, mock_model_loader):
        """Test the CLI with the --debug flag."""
        mock_model_loader.load_model_configs.return_value = {"test-model": {}}
        mock_model_loader.get_model_config.return_value = {}

        test_args = ["cli.py", self.input_file, "--model", "test-model", "--debug"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        passed_options = mock_process_single_file.call_args[0][2]
        self.assertTrue(passed_options.debug)

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_reasoning_for_argument(self, mock_process_single_file, mock_check_server_status, mock_model_loader):
        """Test the CLI with the --reasoning-for argument."""
        mock_model_loader.load_model_configs.return_value = {"test-model": {}}
        mock_model_loader.get_model_config.return_value = {}

        test_args = ["cli.py", self.input_file, "--model", "test-model", "--reasoning-for", "main"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        self.assertTrue(mock_process_single_file.called)
        passed_options = mock_process_single_file.call_args[0][2]
        self.assertEqual(passed_options.reasoning_for, "main")

    @patch('text_translator.cli.model_loader')
    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_directory')
    def test_main_api_url_from_env(self, mock_process, mock_check_server_status, mock_model_loader):
        """Test that the API URL is taken from the environment variable."""
        mock_model_loader.load_model_configs.return_value = {"m": {}}
        mock_model_loader.get_model_config.return_value = {}

        test_args = ["cli.py", self.test_dir, "--model", "m"]
        with patch.dict(os.environ, {'OOBABOOGA_API_BASE_URL': 'http://env.url'}):
            with patch.object(sys, 'argv', test_args):
                cli.main()

        mock_check_server_status.assert_called_once_with('http://env.url', False)
        passed_options = mock_process.call_args[0][1]
        self.assertEqual(passed_options.api_base_url, 'http://env.url')

class TestDirectoryProcessing(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")
        self.base_options = TranslationOptions(input_path=self.test_dir, model_name="test")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('text_translator.cli.process_single_file')
    def test_process_directory_recursive(self, mock_process_single_file):
        """Test recursive directory processing."""
        dir1 = os.path.join(self.test_dir, "dir1")
        os.makedirs(dir1)
        file1 = os.path.join(self.test_dir, "file1.txt")
        file2 = os.path.join(dir1, "file2.txt")
        open(file1, 'w').close()
        open(file2, 'w').close()

        args = unittest.mock.Mock(input_path=self.test_dir, output=self.output_dir, recursive=True)

        cli.process_directory(args, self.base_options)

        self.assertEqual(mock_process_single_file.call_count, 2)

    @patch('text_translator.cli.process_single_file')
    def test_process_directory_non_recursive(self, mock_process_single_file):
        """Test non-recursive directory processing."""
        dir1 = os.path.join(self.test_dir, "dir1")
        os.makedirs(dir1)
        file1 = os.path.join(self.test_dir, "file1.txt")
        file2 = os.path.join(dir1, "file2.txt")
        open(file1, 'w').close()
        open(file2, 'w').close()

        args = unittest.mock.Mock(input_path=self.test_dir, output=self.output_dir, recursive=False)

        cli.process_directory(args, self.base_options)

        self.assertEqual(mock_process_single_file.call_count, 1)
        mock_process_single_file.assert_called_once_with(file1, os.path.join(self.output_dir, "file1.txt"), self.base_options)

if __name__ == '__main__':
    unittest.main()
