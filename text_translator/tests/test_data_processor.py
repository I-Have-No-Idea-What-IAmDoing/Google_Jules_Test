import unittest
from text_translator.translator_lib.data_processor import (
    strip_thinking_tags,
    replace_tags_with_placeholders,
    restore_tags_from_placeholders
)

class TestDataProcessor(unittest.TestCase):

    def test_replace_and_restore_tags(self):
        # 1. Test with no tags
        text_no_tags = "This is a simple text."
        processed_text, tag_map = replace_tags_with_placeholders(text_no_tags)
        self.assertEqual(processed_text, text_no_tags)
        self.assertEqual(tag_map, {})
        self.assertEqual(restore_tags_from_placeholders(processed_text, tag_map), text_no_tags)

        # 2. Test with simple self-closing tags
        text_simple_tags = "Hello<br>World"
        processed_text, tag_map = replace_tags_with_placeholders(text_simple_tags)
        self.assertEqual(processed_text, "Hello__TAG_PLACEHOLDER_0__World")
        self.assertEqual(tag_map, {"__TAG_PLACEHOLDER_0__": "<br>"})
        self.assertEqual(restore_tags_from_placeholders(processed_text, tag_map), text_simple_tags)

        # 3. Test with paired tags
        text_paired_tags = "This is <b>bold</b> text."
        processed_text, tag_map = replace_tags_with_placeholders(text_paired_tags)
        self.assertEqual(processed_text, "This is __TAG_PLACEHOLDER_0__bold__TAG_PLACEHOLDER_1__ text.")
        self.assertEqual(tag_map, {"__TAG_PLACEHOLDER_0__": "<b>", "__TAG_PLACEHOLDER_1__": "</b>"})
        self.assertEqual(restore_tags_from_placeholders(processed_text, tag_map), text_paired_tags)

        # 4. Test with tags with attributes
        text_attr_tags = 'Check out <a href="http://example.com">this link</a>.'
        processed_text, tag_map = replace_tags_with_placeholders(text_attr_tags)
        self.assertEqual(processed_text, "Check out __TAG_PLACEHOLDER_0__this link__TAG_PLACEHOLDER_1__.")
        self.assertEqual(tag_map, {
            "__TAG_PLACEHOLDER_0__": '<a href="http://example.com">',
            "__TAG_PLACEHOLDER_1__": '</a>'
        })
        restored_text = restore_tags_from_placeholders(processed_text, tag_map)
        self.assertEqual(restored_text, text_attr_tags)

        # 5. Test with multiple, mixed tags
        text_multiple_tags = "Line one.<br/>Line two has <i>italic</i> and <b>bold</b>."
        processed_text, tag_map = replace_tags_with_placeholders(text_multiple_tags)
        self.assertEqual(
            processed_text,
            "Line one.__TAG_PLACEHOLDER_0__Line two has __TAG_PLACEHOLDER_1__italic__TAG_PLACEHOLDER_2__ and __TAG_PLACEHOLDER_3__bold__TAG_PLACEHOLDER_4__."
        )
        self.assertEqual(tag_map, {
            "__TAG_PLACEHOLDER_0__": "<br/>",
            "__TAG_PLACEHOLDER_1__": "<i>",
            "__TAG_PLACEHOLDER_2__": "</i>",
            "__TAG_PLACEHOLDER_3__": "<b>",
            "__TAG_PLACEHOLDER_4__": "</b>"
        })
        self.assertEqual(restore_tags_from_placeholders(processed_text, tag_map), text_multiple_tags)

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