"""
This module defines custom exceptions for the text_translator application.

Having specific exceptions allows for more targeted error handling and clearer
error messages, making the application more robust and easier to debug.
"""

class TranslatorError(Exception):
    """Base class for all custom exceptions in the translator application."""
    pass

class APIConnectionError(TranslatorError):
    """Raised when there is a problem connecting to the translation API server.

    This could be due to a network issue, a DNS failure, or the server being
    down.
    """
    pass

class APIStatusError(TranslatorError):
    """Raised when the API server returns an HTTP error status (e.g., 4xx, 5xx).

    Attributes:
        status_code (int): The HTTP status code returned by the server.
        message (str): The error message from the server response.
    """
    def __init__(self, message: str, status_code: int):
        super().__init__(f"API returned error {status_code}: {message}")
        self.status_code = status_code
        self.message = message

class ModelLoadError(TranslatorError):
    """Raised when the requested model fails to load on the API server."""
    pass

class TranslationError(TranslatorError):
    """Raised when the translation process for a specific piece of text fails."""
    pass
