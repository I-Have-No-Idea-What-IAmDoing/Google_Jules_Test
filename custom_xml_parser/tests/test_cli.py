import unittest
import os
import shutil
import tempfile
import sys

from custom_xml_parser.cli import process_directories

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
        # A file to be copied
        with open(os.path.join(self.input_dir, 'copy_me.txt'), 'w', encoding='utf-8') as f:
            f.write('[Copy]\n<val>1</val>\n[/Copy]')
        # A non-txt file to be ignored
        with open(os.path.join(self.input_dir, 'ignore_me.dat'), 'w', encoding='utf-8') as f:
            f.write('some data')
        # A subdirectory with a file to be merged
        os.makedirs(os.path.join(self.input_dir, 'subdir'))
        with open(os.path.join(self.input_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write('# Input File\n[Merge]\n<input>\nyes\n</input>\n[/Merge]')

        # --- Output directory setup ---
        # Pre-existing file to test merge logic
        os.makedirs(os.path.join(self.output_dir, 'subdir'))
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'w', encoding='utf-8') as f:
            f.write('# Original Output\n[Merge]\n<output>\nyes\n</output>\n[/Merge]')

        # 2. Run the processor
        process_directories(self.input_dir, self.output_dir)

        # 3. Assert the results

        # Check that copy_me.txt was copied
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'copy_me.txt')))
        with open(os.path.join(self.output_dir, 'copy_me.txt'), 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('[Copy]', content)

        # Check that ignore_me.dat was ignored
        self.assertFalse(os.path.exists(os.path.join(self.output_dir, 'ignore_me.dat')))

        # Check that merge_me.txt was merged correctly
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, 'subdir', 'merge_me.txt')))
        with open(os.path.join(self.output_dir, 'subdir', 'merge_me.txt'), 'r', encoding='utf-8') as f:
            content = f.read()
            # Priority is given to input, so <input> should be present
            self.assertIn('<input>', content)
            # The value from the original output file should be present because the keys are different
            self.assertIn('<output>', content)
            # Comments from the input file should be present
            self.assertIn('# Input File', content)
            # Comments from the original output file should NOT be present (as d1 has priority)
            self.assertNotIn('# Original Output', content)


if __name__ == '__main__':
    unittest.main()
