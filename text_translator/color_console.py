import sys
from typing import Optional

try:
    import colorama
    colorama.init()

    # Define color constants
    COLOR_SUCCESS = colorama.Fore.GREEN
    COLOR_WARNING = colorama.Fore.YELLOW
    COLOR_ERROR = colorama.Fore.RED
    COLOR_INFO = colorama.Fore.CYAN
    COLOR_RESET = colorama.Style.RESET_ALL

    IS_TTY = sys.stdout.isatty()

except ImportError:
    # If colorama is not installed, create dummy constants
    COLOR_SUCCESS = ''
    COLOR_WARNING = ''
    COLOR_ERROR = ''
    COLOR_INFO = ''
    COLOR_RESET = ''
    IS_TTY = False


def _is_quiet(quiet_arg: Optional[bool]) -> bool:
    """Helper to determine if output should be suppressed."""
    return quiet_arg is True


def _print_colored(message: str, color: str, file=sys.stdout, quiet: Optional[bool] = False):
    """Internal function to print a message with a specified color."""
    if _is_quiet(quiet):
        return

    if IS_TTY:
        print(f"{color}{message}{COLOR_RESET}", file=file)
    else:
        print(message, file=file)


def print_success(message: str, quiet: Optional[bool] = False):
    """Prints a message in the 'success' color (green)."""
    _print_colored(message, COLOR_SUCCESS, quiet=quiet)


def print_warning(message: str, quiet: Optional[bool] = False):
    """Prints a message in the 'warning' color (yellow)."""
    _print_colored(message, COLOR_WARNING, quiet=quiet)


def print_error(message: str, quiet: Optional[bool] = False):
    """Prints a message in the 'error' color (red) to stderr."""
    _print_colored(message, COLOR_ERROR, file=sys.stderr, quiet=quiet)


def print_info(message: str, quiet: Optional[bool] = False):
    """Prints a message in the 'info' color (cyan)."""
    _print_colored(message, COLOR_INFO, quiet=quiet)


def print_translation(content: str, quiet: Optional[bool] = False):
    """Prints the translated content, either plainly or with a header."""
    if _is_quiet(quiet):
        print(content)
        return

    if IS_TTY:
        print(f"\n{COLOR_INFO}--- Translated Content ---{COLOR_RESET}")
        print(content)
        print(f"{COLOR_INFO}--------------------------{COLOR_RESET}")
    else:
        print("\n--- Translated Content ---")
        print(content)
        print("--------------------------")