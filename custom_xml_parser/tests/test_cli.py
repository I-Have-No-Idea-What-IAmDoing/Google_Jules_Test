import unittest
import os
import shutil
import tempfile
import sys

from custom_xml_parser.cli import process_directories, main
from io import StringIO
import unittest.mock as mock

class TestCli(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, 'input')
        self.output_dir = os.path.join(self.test_dir, 'output')
        os.makedirs(self.input_dir)
        os.makedirs(self.output_dir)

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_copy_and_merge(self):
        # 1. Setup initial directory structures and files

        # --- Input directory setup ---
        with open(os.path.join(self.input_dir, 'copy_me.txt'), 'w', encoding='utf-8') as f:
            f.write('[Copy]\n<val>1</val>\n[/Copy]')
        with open(os.path.join(self.input_dir, 'ignore_me.dat'), 'w', encoding='utf-8') as f:
            f.write('some data')
        os.makedirs(os.path.join(self.input_dir, 'subdir'))
        with open(os.path.join(self.input_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write('# Input File\n[Merge]\n<input>\nyes\n</input>\n[/Merge]')

        # --- Output directory setup ---
        os.makedirs(os.path.join(self.output_dir, 'subdir'))
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write('# Original Output\n[Merge]\n<output>\nyes\n</output>\n[/Merge]')

        # 2. Run the processor
        process_directories(self.input_dir, self.output_dir, quiet=True)

        # 3. Assert the results
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'copy_me.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, 'ignore_me.dat')))
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<input>', content)
            self.assertIn('<output>', content)
            self.assertIn('# Input File', content)
            self.assertNotIn('# Original Output', content)

    def test_no_overwrite(self):
        # Setup files
        os.makedirs(os.path.join(self.input_dir, 'subdir'))
        with open(os.path.join(self.input_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write('# Input File\n[Merge]\n<input>yes</input>\n[/Merge]')
        os.makedirs(os.path.join(self.output_dir, 'subdir'))
        original_content = '# Original Output\n[Merge]\n<output>yes</output>\n[/Merge]'
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write(original_content)

        # Run the processor with no_overwrite=True
        process_directories(self.input_dir, self.output_dir, no_overwrite=True, quiet=True)

        # Assert that the output file was NOT changed
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'r', encoding='utf-8') as f:
            final_content = f.read()
        self.assertEqual(final_content, original_content)

    def test_quiet_flag(self):
        # Redirect stdout to check output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        # Run processor with quiet=True
        process_directories(self.input_dir, self.output_dir, quiet=True)

        sys.stdout = old_stdout # Restore stdout
        self.assertEqual(captured_output.getvalue(), "")

    def test_dry_run_flag(self):
        # Setup input file
        with open(os.path.join(self.input_dir, 'copy_me.txt'), 'w', encoding='utf-8') as f:
            f.write('[Copy]\n<val>1</val>\n[/Copy]')

        # Run processor with dry_run=True
        process_directories(self.input_dir, self.output_dir, dry_run=True)

        # Assert that no files or directories were created in the output
        self.assertEqual(len(os.listdir(self.output_dir)), 0)


    def test_process_directories_creates_output_subdir(self):
        """Tests that a non-existent subdirectory in the output is created."""
        input_subdir = os.path.join(self.input_dir, 'subdir')
        os.makedirs(input_subdir)
        with open(os.path.join(input_subdir, 'test.txt'), 'w') as f:
            f.write('[Test]')

        # Ensure the output subdir doesn't exist
        output_subdir = os.path.join(self.output_dir, 'subdir')
        if os.path.exists(output_subdir):
            shutil.rmtree(output_subdir)

        process_directories(self.input_dir, self.output_dir, quiet=True)

        self.assertTrue(os.path.exists(output_subdir))
        self.assertTrue(os.path.exists(os.path.join(output_subdir, 'test.txt')))

    def test_merge_error_handling(self):
        """Tests that an error during file merging is caught and reported."""
        with open(os.path.join(self.input_dir, 'bad_file.txt'), 'w') as f:
            f.write('[Bad') # Malformed content
        with open(os.path.join(self.output_dir, 'bad_file.txt'), 'w') as f:
            f.write('[Good]')

        old_stderr = sys.stderr
        sys.stderr = captured_stderr = StringIO()

        process_directories(self.input_dir, self.output_dir, quiet=True)

        sys.stderr = old_stderr # Restore stderr
        self.assertIn("Error merging file bad_file.txt", captured_stderr.getvalue())

    def test_main_function(self):
        """Tests the main function with command-line arguments."""
        with open(os.path.join(self.input_dir, 'test.txt'), 'w') as f:
            f.write('[Test]')

        test_args = ["prog_name", self.input_dir, self.output_dir]
        with mock.patch.object(sys, 'argv', test_args):
            main()

        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'test.txt')))

    def test_main_function_input_dir_not_found(self):
        """Tests the main function with a non-existent input directory."""

        # Redirect stderr to check for error message
        old_stderr = sys.stderr
        sys.stderr = captured_stderr = StringIO()

        test_args = ["prog_name", "non_existent_dir", self.output_dir]
        with mock.patch.object(sys, 'argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)

        sys.stderr = old_stderr # Restore stderr
        self.assertIn("Error: Input directory not found", captured_stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
