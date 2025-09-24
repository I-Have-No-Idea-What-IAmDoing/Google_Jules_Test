import unittest
from unittest.mock import patch
from langdetect import LangDetectException

from text_translator.translator_lib import validation

class TestTranslationValidation(unittest.TestCase):
    """Tests the `is_translation_valid` function's validation heuristics."""

    def test_validation_success(self):
        """Tests that a simple, valid translation passes."""
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertTrue(validation.is_translation_valid("こんにちは", "Hello"))

    def test_validation_extracts_translation_from_response(self):
        """Test that validation logic extracts the translation from the response."""
        original = "こんにちは"
        translated_with_thinking = "Translation: Hello"
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertTrue(validation.is_translation_valid(original, translated_with_thinking))

    def test_validation_fails_if_empty_or_identical(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertFalse(validation.is_translation_valid("original", ""))
            self.assertFalse(validation.is_translation_valid("original", "  "))
            self.assertFalse(validation.is_translation_valid("original", "original"))
            self.assertFalse(validation.is_translation_valid("original", "ORIGINAL"))

    def test_validation_fails_for_refusal(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertFalse(validation.is_translation_valid("original", "I'm sorry, I cannot do that."))

    def test_validation_fails_for_non_english(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='ja'):
            self.assertFalse(validation.is_translation_valid("original", "これは日本語です"))

    def test_validation_lang_detect_exception_is_valid(self):
        with patch('text_translator.translator_lib.validation.detect', side_effect=LangDetectException(0, "error")):
            self.assertTrue(validation.is_translation_valid("original", "a valid translation"))

    def test_validation_fails_for_multiline_in_line_by_line_mode(self):
        self.assertFalse(validation.is_translation_valid("original", "hello\nworld", line_by_line=True))
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertTrue(validation.is_translation_valid("original", "hello world", line_by_line=True))

    def test_validation_fails_for_japanese_chars(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertFalse(validation.is_translation_valid("original", "This is a translation with こんにちは"))

    def test_validation_fails_for_excessive_repetition(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            repetitive_text = "word " * 11
            self.assertFalse(validation.is_translation_valid("original", repetitive_text))

    def test_validation_fails_for_placeholder_text(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertFalse(validation.is_translation_valid("original", "This is a [translation here]"))
            self.assertFalse(validation.is_translation_valid("original", "This is a [ insert translation ]"))
            self.assertFalse(validation.is_translation_valid("original", "This is a (translation)"))
            self.assertFalse(validation.is_translation_valid("original", "This is a placeholder"))
            self.assertFalse(validation.is_translation_valid("original", "your translation here"))

    def test_validation_fails_for_length_ratio(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            long_original = "This is a very long original sentence that we are testing."
            short_original = "This is a test."
            self.assertFalse(validation.is_translation_valid(long_original, "short")) # Too short
            self.assertFalse(validation.is_translation_valid(short_original, long_original)) # Too long

    def test_validation_for_xml_tags(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            # Fails if new tags are introduced
            self.assertFalse(validation.is_translation_valid("original", "This is a <tag>translation</tag>"))
            # Fails if tags are removed
            self.assertFalse(validation.is_translation_valid("<tag>original</tag>", "This is a translation"))
            # Fails if tags are different
            self.assertFalse(validation.is_translation_valid("<tag>original</tag>", "This is a <p>translation</p>"))
            # Succeeds if tags are the same
            self.assertTrue(validation.is_translation_valid("<tag>original</tag>", "This is a <tag>translation</tag>"))

    def test_validation_for_urls(self):
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            # Fails if a new URL is introduced
            self.assertFalse(validation.is_translation_valid("original", "This is a translation with a link: http://example.com"))
            # Succeeds if the URL is the same
            self.assertTrue(validation.is_translation_valid("original url is http://example.com", "translated url is http://example.com"))
            # Succeeds if there are no URLs
            self.assertTrue(validation.is_translation_valid("original", "translation"))

    def test_validation_for_placeholders(self):
        """Test the validation of placeholders like %dummy and %name."""
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            # Succeeds if placeholders are identical and text is different
            self.assertTrue(validation.is_translation_valid("Original with %name and %value", "Translated with %name and %value"))
            # Fails if a placeholder is missing
            self.assertFalse(validation.is_translation_valid("Original with %name and %value", "Translated with only %name"))
            # Fails if a new placeholder is introduced
            self.assertFalse(validation.is_translation_valid("Original with %name", "Translated with %name and %extra"))
            # Fails if a placeholder casing is different (case-sensitive check)
            self.assertFalse(validation.is_translation_valid("Original with %Name", "Translated with %name"))
            # Succeeds if there are no variables and text is different
            self.assertTrue(validation.is_translation_valid("Original with no variables", "Translated with no variables"))
            # Succeeds with multiple identical placeholders and different text
            self.assertTrue(validation.is_translation_valid("User %id, Action %id", "A different sentence with User %id, Action %id"))
            # Fails if one of multiple placeholders is different
            self.assertFalse(validation.is_translation_valid("User %id, Action %id", "A different sentence with User %id, Action %ID"))
            # Fails if text is identical, even if placeholders match
            self.assertFalse(validation.is_translation_valid("User %id, Action %id", "User %id, Action %id"))

    def test_validation_handles_thinking_tags_in_original(self):
        """Test that validation handles <thinking> tags in the original text."""
        original_with_thinking = "<thinking>This is a thought.</thinking>Hello"
        translated = "This is a valid translation"
        with patch('text_translator.translator_lib.validation.detect', return_value='en'):
            self.assertTrue(validation.is_translation_valid(original_with_thinking, translated))