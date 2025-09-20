import unittest
from unittest.mock import patch, call
import sys
import os
from io import StringIO
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from text_translator import cli
from translator_lib import core

class TestCommandLineInterface(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for tests."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_single_file(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with a single file input."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        mock_process_single_file.assert_called_once()
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 0)

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_directory_recursive_by_default(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with a directory input is recursive by default."""
        # Create a dummy directory structure
        dir1 = os.path.join(self.test_dir, "dir1")
        os.makedirs(dir1)
        file1 = os.path.join(self.test_dir, "file1.txt")
        file2 = os.path.join(dir1, "file2.txt")
        with open(file1, "w") as f:
            f.write("test1")
        with open(file2, "w") as f:
            f.write("test2")

        output_dir = os.path.join(self.test_dir, "output")
        test_args = ["cli.py", self.test_dir, "--model", "test-model", "--output", output_dir, "--quiet"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        # Check if process_single_file was called for each file (recursive)
        self.assertEqual(mock_process_single_file.call_count, 2)

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_directory_non_recursive(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with --no-recursive flag."""
        # Create a dummy directory structure
        dir1 = os.path.join(self.test_dir, "dir1")
        os.makedirs(dir1)
        file1 = os.path.join(self.test_dir, "file1.txt")
        file2 = os.path.join(dir1, "file2.txt")
        with open(file1, "w") as f:
            f.write("test1")
        with open(file2, "w") as f:
            f.write("test2")

        output_dir = os.path.join(self.test_dir, "output")
        test_args = ["cli.py", self.test_dir, "--model", "test-model", "--output", output_dir, "--no-recursive", "--quiet"]
        with patch.object(sys, 'argv', test_args):
            cli.main()

        mock_check_server_status.assert_called_once()
        # Check if process_single_file was called only for the top-level file
        self.assertEqual(mock_process_single_file.call_count, 1)
        mock_process_single_file.assert_called_once_with(
            file1, os.path.join(output_dir, "file1.txt"), unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY
        )

    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_refine_without_draft_model_exits(self, mock_stderr, mock_check_server_status):
        """Test that the CLI exits if --refine is used without --draft-model."""
        test_args = ["cli.py", "input.txt", "--model", "r", "--refine"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                with patch('os.path.exists', return_value=True): # Mock path existence
                    cli.main()
            self.assertEqual(cm.exception.code, 2)

        self.assertIn("--draft-model is required when using --refine", mock_stderr.getvalue())

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.translate_file', side_effect=Exception("Core error"))
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_generic_error_handling(self, mock_stderr, mock_translate_file, mock_check_server_status):
        """Test that the CLI handles exceptions in file processing."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        self.assertIn(f"Error processing file {input_file}: Core error", mock_stderr.getvalue())

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_debug_flag_default(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with --debug flag without a value, defaulting to 3."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--debug"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 3)

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_debug_flag_with_level(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with --debug flag with a specific level."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--debug", "2"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 2)

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_reasoning_for_argument(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with the --reasoning-for argument."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--reasoning-for", "main"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.reasoning_for, "main")

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_cli_line_by_line_flag(self, mock_process_single_file, mock_check_server_status):
        """Test the CLI with the --line-by-line flag."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--line-by-line"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_check_server_status.assert_called_once()
        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertTrue(passed_args_obj.line_by_line)


    @patch('text_translator.cli.translate_file', return_value="translated content")
    def test_process_single_file_prints_to_stdout(self, mock_translate_file):
        """Test that process_single_file prints to stdout if no output_file is given."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f: f.write("test")

        args = unittest.mock.Mock(quiet=False)

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cli.process_single_file(input_file, None, args, "url", None)
            self.assertIn("translated content", mock_stdout.getvalue())

    @patch('text_translator.cli.translate_file', return_value="translated content")
    def test_process_single_file_refine_mode_verbose(self, mock_translate_file):
        """Test the verbose output for refine mode."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f: f.write("test")

        args = unittest.mock.Mock(quiet=False, refine=True, draft_model="d", model="r")

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cli.process_single_file(input_file, "output.txt", args, "url", None)
            self.assertIn("Using refinement mode", mock_stdout.getvalue())

    @patch('text_translator.cli.process_single_file')
    def test_process_directory_creates_default_output(self, mock_process):
        """Test that process_directory creates a default output directory if none is specified."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f: f.write("test")

        args = unittest.mock.Mock(input_path=self.test_dir, output=None, recursive=False)

        cli.process_directory(args, "url", None)

        expected_output_dir = f"{os.path.basename(self.test_dir)}_translated"
        self.assertTrue(os.path.exists(expected_output_dir))
        shutil.rmtree(expected_output_dir)

    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_main_input_path_not_found(self, mock_stderr, mock_check_server_status):
        """Test that main exits if the input path does not exist."""
        test_args = ["cli.py", "nonexistent.txt", "--model", "m"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit):
                cli.main()
        self.assertIn("Input path does not exist", mock_stderr.getvalue())

    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_main_glossary_file_not_found(self, mock_stderr, mock_check_server_status):
        """Test that main exits if the glossary file does not exist."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f: f.write("test")
        test_args = ["cli.py", input_file, "--model", "m", "--glossary-file", "nonexistent.txt"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit):
                cli.main()
        self.assertIn("Glossary file not found", mock_stderr.getvalue())

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_main_api_url_from_env(self, mock_process, mock_check_server_status):
        """Test that the API URL is taken from the environment variable."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f: f.write("test")
        test_args = ["cli.py", input_file, "--model", "m"]
        with patch.dict(os.environ, {'OOBABOOGA_API_BASE_URL': 'http://env.url'}):
            with patch.object(sys, 'argv', test_args):
                cli.main()

        mock_check_server_status.assert_called_once()
        mock_process.assert_called_once()
        # The api_url is the 4th argument to process_single_file
        self.assertEqual(mock_process.call_args[0][3], 'http://env.url')

    @patch('text_translator.cli.check_server_status')
    @patch('sys.stderr', new_callable=StringIO)
    def test_main_invalid_input_path(self, mock_stderr, mock_check_server_status):
        """Test that main exits if the input path is not a file or directory."""
        input_path = "some_invalid_path"
        test_args = ["cli.py", input_path, "--model", "m"]
        with patch.object(sys, 'argv', test_args):
            with patch('os.path.exists', return_value=True):
                with patch('os.path.isdir', return_value=False):
                    with patch('os.path.isfile', return_value=False):
                        with self.assertRaises(SystemExit):
                            cli.main()
        self.assertIn("Input path is not a valid file or directory", mock_stderr.getvalue())

    @patch('text_translator.cli.check_server_status')
    @patch('text_translator.cli.process_single_file')
    def test_main_single_file_output_to_directory(self, mock_process, mock_check_server_status):
        """Test that providing an output directory for a single file works correctly."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        output_dir = os.path.join(self.test_dir, "output_dir")
        os.makedirs(output_dir)

        test_args = ["cli.py", input_file, "--model", "m", "--output", output_dir]

        with patch.object(sys, 'argv', test_args):
            cli.main()

        mock_check_server_status.assert_called_once()
        mock_process.assert_called_once()
        # The output file path is the 2nd argument to process_single_file
        expected_output_path = os.path.join(output_dir, "input.txt")
        self.assertEqual(mock_process.call_args[0][1], expected_output_path)

if __name__ == '__main__':
    unittest.main()
