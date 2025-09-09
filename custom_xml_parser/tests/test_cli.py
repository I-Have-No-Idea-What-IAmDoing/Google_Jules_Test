import unittest
import os
import shutil
import tempfile
import sys

from custom_xml_parser.cli import process_directories
from io import StringIO

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


if __name__ == '__main__':
    unittest.main()
