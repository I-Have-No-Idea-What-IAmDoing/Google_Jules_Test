import re
from typing import Any, Dict, List, Union
from langdetect import detect, LangDetectException

def strip_thinking_tags(text: str) -> str:
    """Removes various thinking blocks like <thinking>...</thinking>,
    <think>...</think>, or [think]...[/think] from a string.

    The matching is case-insensitive.

    Args:
        text: The input string.

    Returns:
        The string with all thinking blocks removed.
    """
    # Pattern for <thinking>...</thinking> or <think>...</think>
    text = re.sub(r'<(thinking|think)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Pattern for [think]...[/think]
    text = re.sub(r'\[think\].*?\[/think\]', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()

def collect_text_nodes(data: Union[Dict[str, Any], List[Any]], nodes_list: List[Dict[str, Any]]) -> None:
    """Recursively finds and collects all text nodes requiring translation.

    This function traverses a nested data structure (composed of dictionaries
    and lists) produced by the `custom_xml_parser`. It identifies nodes that
    are candidates for translation based on a set of criteria:
    - The node's key must be `'#text'`.
    - The text value must not be empty or just whitespace.
    - The text must not be a placeholder variable (e.g., '%dummy%').
    - The value must be a non-English string (as determined by `langdetect`).
    - The value must not start with the `jp_text:::` marker, which indicates
      it has already been processed.

    The function modifies `nodes_list` in place, appending the parent
    dictionary of each qualifying text node.

    Args:
        data: The nested dictionary or list to traverse.
        nodes_list: A list that will be populated with the dictionaries
                    containing text nodes that need to be translated.
    """
    # Regex to detect if a string is just a placeholder variable
    # It matches strings like '%dummy%', '%%dummy%%', '%dummy', '%%dummy'
    placeholder_pattern = re.compile(r'^%+\w+%*$')

    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str):
                # 1. Skip if empty or just whitespace
                if not value.strip():
                    continue

                # 2. Skip if it's a placeholder
                if placeholder_pattern.match(value):
                    continue

                # 3. Skip if it's already marked as processed
                if value.startswith("jp_text:::"):
                    continue

                # 4. Check for language
                try:
                    if detect(value) != 'en':
                        nodes_list.append(data)
                except LangDetectException:
                    # If language detection fails, assume it needs translation
                    nodes_list.append(data)
            else:
                collect_text_nodes(value, nodes_list)
    elif isinstance(data, list):
        for item in data:
            collect_text_nodes(item, nodes_list)

def cleanup_markers(data: Union[Dict[str, Any], List[Any]]) -> None:
    """Recursively removes processing markers from all text nodes in the data.

    After the translation process, text nodes are temporarily prefixed with
    `jp_text:::` to mark them as complete. This function traverses the entire
    nested data structure and removes this prefix from any `'#text'` value
    where it is found, cleaning the data for final serialization.

    The function modifies the data structure in place.

    Args:
        data: The nested dictionary or list to be cleaned.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str) and value.startswith("jp_text:::"):
                data[key] = value.replace("jp_text:::", "", 1)
            else:
                cleanup_markers(value)
    elif isinstance(data, list):
        for item in data:
            cleanup_markers(item)
def _extract_translation_from_response(
    response: str,
    debug: bool = False,
    use_json_format: bool = False
) -> str:
    """Extracts a translation from a model's potentially complex response.

    Models may return not just the translation but also explanatory text,
    reasoning, or markdown formatting. This function isolates the core
    translation using a series of prioritized strategies:

    1.  **JSON Parsing**: If `use_json_format` is True, it first tries to parse
        the response as JSON (handling markdown wrappers) and extract the value
        from a 'translation' key.
    2.  **Block Removal**: It strips out reasoning blocks like `<thinking>...</thinking>`.
    3.  **Marker-based Extraction**: It looks for common headers like "Translation:"
        and returns the text that follows.
    4.  **Fallback**: If none of the above succeed, it returns the entire
        cleaned response string.

    Args:
        response: The raw string response from the language model.
        debug: If True, enables printing of debug information to stderr.
        use_json_format: If True, specifies that the primary extraction method
                         should be JSON parsing.

    Returns:
        The extracted translation string, or an empty string if extraction fails.
    """
    if use_json_format:
        try:
            # Handle cases where the JSON is wrapped in markdown ```json ... ```
            if response.startswith("```json"):
                response = response[7:-4].strip() # Remove ```json\n and \n```
            elif response.startswith("```"):
                 response = response[3:-3].strip()


            data = json.loads(response)
            if 'translation' in data and isinstance(data['translation'], str):
                if debug:
                    print(f"--- DEBUG: Extracted translation from JSON ---\n{data['translation']}\n------------------------------------", file=sys.stderr)
                return data['translation']
        except json.JSONDecodeError:
            if debug:
                print(f"--- DEBUG: JSON parsing failed, falling back to text extraction ---\n{response}\n------------------------------------", file=sys.stderr)

    # Fallback to text-based extraction
    # Remove <thinking>...</thinking> blocks
    cleaned_response = strip_thinking_tags(response)

    # Look for a marker and extract the text after it.
    # The pattern looks for various common markers, case-insensitively.
    marker_pattern = re.compile(r'(?:translation|translated text)\s*:\s*', re.IGNORECASE)
    marker_match = marker_pattern.search(cleaned_response)

    if marker_match:
        if debug:
            print(f"--- DEBUG: Extracting translation from response using marker ---\n{cleaned_response}\n------------------------------------", file=sys.stderr)
        # Extract the text following the marker
        translation = cleaned_response[marker_match.end():].strip()
        return translation
    else:
        if debug:
            print(f"--- DEBUG: No marker found, returning cleaned response ---\n{cleaned_response}\n------------------------------------", file=sys.stderr)
        return cleaned_response
