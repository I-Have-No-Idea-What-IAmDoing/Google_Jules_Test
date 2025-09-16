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

    @patch('text_translator.cli.process_single_file')
    def test_cli_single_file(self, mock_process_single_file):
        """Test the CLI with a single file input."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        mock_process_single_file.assert_called_once()
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 0)

    @patch('text_translator.cli.process_single_file')
    def test_cli_directory_recursive_by_default(self, mock_process_single_file):
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

    @patch('text_translator.cli.process_single_file')
    def test_cli_directory_non_recursive(self, mock_process_single_file):
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

        # Check if process_single_file was called only for the top-level file
        self.assertEqual(mock_process_single_file.call_count, 1)
        mock_process_single_file.assert_called_once_with(
            file1, os.path.join(output_dir, "file1.txt"), unittest.mock.ANY, unittest.mock.ANY, unittest.mock.ANY
        )

    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_refine_without_draft_model_exits(self, mock_stderr):
        """Test that the CLI exits if --refine is used without --draft-model."""
        test_args = ["cli.py", "input.txt", "--model", "r", "--refine"]
        with patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                with patch('os.path.exists', return_value=True): # Mock path existence
                    cli.main()
            self.assertEqual(cm.exception.code, 2)

        self.assertIn("--draft-model is required when using --refine", mock_stderr.getvalue())

    @patch('text_translator.cli.translate_file', side_effect=Exception("Core error"))
    @patch('sys.stderr', new_callable=StringIO)
    def test_cli_generic_error_handling(self, mock_stderr, mock_translate_file):
        """Test that the CLI handles exceptions in file processing."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertIn(f"Error processing file {input_file}: Core error", mock_stderr.getvalue())

    @patch('text_translator.cli.process_single_file')
    def test_cli_debug_flag_default(self, mock_process_single_file):
        """Test the CLI with --debug flag without a value, defaulting to 3."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--debug"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 3)

    @patch('text_translator.cli.process_single_file')
    def test_cli_debug_flag_with_level(self, mock_process_single_file):
        """Test the CLI with --debug flag with a specific level."""
        input_file = os.path.join(self.test_dir, "input.txt")
        with open(input_file, "w") as f:
            f.write("test")

        test_args = ["cli.py", input_file, "--model", "test-model", "--debug", "2"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=StringIO):
                cli.main()

        self.assertTrue(mock_process_single_file.called)
        call_args, _ = mock_process_single_file.call_args
        passed_args_obj = call_args[2]
        self.assertEqual(passed_args_obj.debug, 2)

if __name__ == '__main__':
    unittest.main()
