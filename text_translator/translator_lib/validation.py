import re
import sys
from collections import Counter
from langdetect import detect, LangDetectException

def is_translation_valid(original_text: str, translated_text: str, debug: bool = False, line_by_line: bool = False) -> bool:
    """
    Validates a translation using a collection of heuristics.

    This function checks for common failure modes of translation models, such as:
    - Empty or identical translations.
    - Refusal phrases (e.g., "I'm sorry, I cannot...").
    - Non-English text or leftover Japanese characters.
    - Excessive repetition or inclusion of the original text.
    - Unreasonable length ratios between original and translated text.

    Args:
        original_text: The source text.
        translated_text: The translated text to validate.
        debug: If True, prints the reason for validation failure.
        line_by_line: If True, enforces a single-line output check.

    Returns:
        True if the translation is deemed valid, False otherwise.
    """
    cleaned_translation = translated_text.strip()
    cleaned_original = original_text.strip()

    # --- Basic Checks ---
    if not cleaned_translation or cleaned_translation.lower() == cleaned_original.lower():
        if debug: print(f"--- DEBUG: Validation failed: Translation is empty or identical to original.", file=sys.stderr)
        return False

    # --- Content-based Checks ---
    refusal_phrases = ["i'm sorry", "i cannot", "i am unable", "as an ai"]
    if any(phrase in cleaned_translation.lower() for phrase in refusal_phrases):
        if debug: print(f"--- DEBUG: Validation failed: Translation contains a refusal phrase.", file=sys.stderr)
        return False

    # --- Language and Character Checks ---
    try:
        if detect(cleaned_translation) != 'en':
            if debug: print(f"--- DEBUG: Validation failed: Translation is not in English.", file=sys.stderr)
            return False
    except LangDetectException:
        if debug: print(f"--- DEBUG: Language detection failed, assuming valid.", file=sys.stderr)

    if re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]', cleaned_translation):
        if debug: print(f"--- DEBUG: Validation failed: Translation contains Japanese characters.", file=sys.stderr)
        return False

    # --- Structural and Repetition Checks ---
    if line_by_line and len(cleaned_translation.splitlines()) > 1:
        if debug: print(f"--- DEBUG: Validation failed: Translation contains multiple lines in line-by-line mode.", file=sys.stderr)
        return False

    words = cleaned_translation.lower().split()
    if len(words) > 10:
        word_counts = Counter(words)
        if (word_counts.most_common(1)[0][1] / len(words)) > 0.4:
            if debug: print(f"--- DEBUG: Validation failed: Translation may be excessively repetitive.", file=sys.stderr)
            return False

    # --- Advanced Heuristics ---
    # Check if the translation contains the original text (for longer strings)
    if len(cleaned_original) > 20 and cleaned_original.lower() in cleaned_translation.lower():
        if debug: print(f"--- DEBUG: Validation failed: Translation contains the original text.", file=sys.stderr)
        return False

    # Check for placeholder text
    if any(re.search(p, cleaned_translation, re.IGNORECASE) for p in [r'\[translation here\]', r'placeholder', r'\[\.\.\.\]']):
        if debug: print(f"--- DEBUG: Validation failed: Translation contains placeholder text.", file=sys.stderr)
        return False

    # Check length ratio, but only for reasonably long strings
    if len(cleaned_original) >= 15:
        ratio = len(cleaned_translation) / len(cleaned_original)
        if not (0.3 < ratio < 3.5):
            if debug: print(f"--- DEBUG: Validation failed: Translation length ratio ({ratio:.2f}) is outside the 0.3-3.5 range.", file=sys.stderr)
            return False

    # Check for leftover XML/HTML tags that aren't part of the original
    if re.search(r'<[^>]+>', cleaned_translation) and not re.search(r'<[^>]+>', cleaned_original):
        if debug: print(f"--- DEBUG: Validation failed: Translation contains new XML/HTML tags.", file=sys.stderr)
        return False

    return True
