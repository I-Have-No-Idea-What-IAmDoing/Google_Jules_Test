import unittest
from text_translator.translator_lib.data_processor import strip_thinking_tags

class TestDataProcessor(unittest.TestCase):

    def test_strip_thinking_tags(self):
        self.assertEqual(
            strip_thinking_tags("This is a test."),
            "This is a test."
        )
        self.assertEqual(
            strip_thinking_tags("<thinking>This should be removed.</thinking>This should remain."),
            "This should remain."
        )
        self.assertEqual(
            strip_thinking_tags("[think]This should be removed.[/think]This should remain."),
            "This should remain."
        )
        self.assertEqual(
            strip_thinking_tags("◁think▷This should be removed.◁/think▷This should remain."),
            "This should remain."
        )
        self.assertEqual(
            strip_thinking_tags("No tags here."),
            "No tags here."
        )
        self.assertEqual(
            strip_thinking_tags("Mixed tags <thinking>one</thinking> and [think]two[/think] and ◁think▷three◁/think▷."),
            "Mixed tags  and  and ."
        )
        self.assertEqual(
            strip_thinking_tags("Incomplete ◁think▷ tag."),
            "Incomplete ◁think▷ tag."
        )
        self.assertEqual(
            strip_thinking_tags("Text before <think>...</think> and after."),
            "Text before  and after."
        )