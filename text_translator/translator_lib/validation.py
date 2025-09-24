import re
import sys
from collections import Counter
from langdetect import detect, LangDetectException
from .data_processor import strip_thinking_tags

import sys

def is_translation_valid(original_text: str, translated_text: str, debug: bool = False, line_by_line: bool = False) -> bool:
    """Validates a translation against a comprehensive set of heuristics.

    This function acts as a quality gate, checking for common failure modes in
    LLM-generated translations. Before validation, `<thinking>...</thinking>`
    blocks are automatically stripped from the translated text. A translation
    is considered invalid if it meets any of the following criteria:

    - Is empty or identical to the (case-insensitive) original.
    - Contains common refusal phrases (e.g., "I'm sorry, I cannot...").
    - Is not detected as English.
    - Contains Japanese characters.
    - Is multi-line when `line_by_line` mode is active.
    - Exhibits excessive word repetition.
    - Includes the original text within the translation.
    - Contains placeholder text like "[translation here]".
    - Has a character length ratio to the original outside the 0.3-3.5 range.
    - Introduces new URLs not present in the original.
    - Has a different set of XML/HTML tags than the original.

    Args:
        original_text: The source text that was translated.
        translated_text: The translated text to be validated.
        debug: If True, prints the specific reason for validation failure to
               stderr.
        line_by_line: If True, adds a check to ensure the output is a single
                      line.

    Returns:
        True if the translation passes all checks, False otherwise.
    """
    # --- Pre-processing ---
    # Strip thinking tags before any other validation
    translated_text = strip_thinking_tags(translated_text)
    original_text = strip_thinking_tags(original_text)

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
    placeholder_patterns = [
        r'\[\s*translation here\s*\]',
        r'\[\s*insert translation\s*\]',
        r'placeholder',
        r'\[\s*\.\.\.\s*\]',
        r'\(translation\)',
        r'your translation here'
    ]
    if any(re.search(p, cleaned_translation, re.IGNORECASE) for p in placeholder_patterns):
        if debug: print(f"--- DEBUG: Validation failed: Translation contains placeholder text.", file=sys.stderr)
        return False

    # Check length ratio, but only for reasonably long strings
    if len(cleaned_original) >= 15:
        ratio = len(cleaned_translation) / len(cleaned_original)
        if not (0.3 < ratio < 3.5):
            if debug: print(f"--- DEBUG: Validation failed: Translation length ratio ({ratio:.2f}) is outside the 0.3-3.5 range.", file=sys.stderr)
            return False

    # Check for new URLs introduced in the translation
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    original_urls = set(re.findall(url_pattern, cleaned_original))
    translated_urls = set(re.findall(url_pattern, cleaned_translation))
    if not translated_urls.issubset(original_urls):
        if debug: print(f"--- DEBUG: Validation failed: New URL detected in translation. New URLs: {translated_urls - original_urls}", file=sys.stderr)
        return False

    # Check for mismatched XML/HTML tags
    original_tags = set(re.findall(r'<[^>]+?>', cleaned_original))
    translated_tags = set(re.findall(r'<[^>]+?>', cleaned_translation))
    if original_tags != translated_tags:
        if debug: print(f"--- DEBUG: Validation failed: XML/HTML tags mismatch. Original: {original_tags}, Translated: {translated_tags}", file=sys.stderr)
        return False

    # Check for mismatched placeholders like %dummy or %name (case-sensitive)
    placeholder_pattern = r'%\w+'
    original_placeholders = set(re.findall(placeholder_pattern, cleaned_original))
    translated_placeholders = set(re.findall(placeholder_pattern, cleaned_translation))
    if original_placeholders != translated_placeholders:
        if debug: print(f"--- DEBUG: Validation failed: Placeholder mismatch. Original: {original_placeholders}, Translated: {translated_placeholders}", file=sys.stderr)
        return False

    return True
