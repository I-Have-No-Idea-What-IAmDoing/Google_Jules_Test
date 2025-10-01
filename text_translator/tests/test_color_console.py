import unittest
from unittest.mock import patch, MagicMock
import sys

# Temporarily add the parent directory to the path to allow direct execution of the test
if __name__ == '__main__':
    sys.path.insert(0, '..')
    from color_console import (
        print_success, print_warning, print_error, print_info, print_translation,
        COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO, COLOR_RESET
    )
else:
    from text_translator.color_console import (
        print_success, print_warning, print_error, print_info, print_translation,
        COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO, COLOR_RESET
    )

class TestColorConsole(unittest.TestCase):

    @patch('text_translator.color_console.IS_TTY', True)
    @patch('builtins.print')
    def test_print_success_color(self, mock_print):
        """Test that print_success uses the correct color code."""
        print_success("Success message")
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args[0][0], f"{COLOR_SUCCESS}Success message{COLOR_RESET}")

    @patch('text_translator.color_console.IS_TTY', True)
    @patch('builtins.print')
    def test_print_warning_color(self, mock_print):
        """Test that print_warning uses the correct color code."""
        print_warning("Warning message")
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args[0][0], f"{COLOR_WARNING}Warning message{COLOR_RESET}")

    @patch('text_translator.color_console.IS_TTY', True)
    @patch('builtins.print')
    def test_print_error_color(self, mock_print):
        """Test that print_error uses the correct color code and stderr."""
        print_error("Error message")
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args[0][0], f"{COLOR_ERROR}Error message{COLOR_RESET}")
        self.assertEqual(mock_print.call_args[1]['file'], sys.stderr)

    @patch('text_translator.color_console.IS_TTY', True)
    @patch('builtins.print')
    def test_print_info_color(self, mock_print):
        """Test that print_info uses the correct color code."""
        print_info("Info message")
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args[0][0], f"{COLOR_INFO}Info message{COLOR_RESET}")

    @patch('text_translator.color_console.IS_TTY', False)
    @patch('builtins.print')
    def test_no_color_when_not_tty(self, mock_print):
        """Test that no color codes are used when not in a TTY."""
        print_success("Plain message")
        mock_print.assert_called_once()
        self.assertEqual(mock_print.call_args[0][0], "Plain message")

    @patch('builtins.print')
    def test_quiet_mode_suppresses_output(self, mock_print):
        """Test that no output is generated when quiet is True."""
        print_success("Should not be printed", quiet=True)
        print_warning("Should not be printed", quiet=True)
        print_error("Should not be printed", quiet=True)
        print_info("Should not be printed", quiet=True)
        mock_print.assert_not_called()

    @patch('text_translator.color_console.IS_TTY', True)
    @patch('builtins.print')
    def test_print_translation_with_color(self, mock_print):
        """Test print_translation with color."""
        print_translation("Translated text")
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call(f"\n{COLOR_INFO}--- Translated Content ---{COLOR_RESET}")
        mock_print.assert_any_call("Translated text")
        mock_print.assert_any_call(f"{COLOR_INFO}--------------------------{COLOR_RESET}")

    @patch('text_translator.color_console.IS_TTY', False)
    @patch('builtins.print')
    def test_print_translation_no_color(self, mock_print):
        """Test print_translation without color."""
        print_translation("Translated text")
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("\n--- Translated Content ---")
        mock_print.assert_any_call("Translated text")
        mock_print.assert_any_call("--------------------------")

    @patch('builtins.print')
    def test_print_translation_quiet(self, mock_print):
        """Test print_translation in quiet mode."""
        print_translation("Translated text", quiet=True)
        mock_print.assert_called_once_with("Translated text")

if __name__ == '__main__':
    unittest.main()