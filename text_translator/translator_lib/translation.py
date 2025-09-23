import time
import re
import sys
import json
from typing import Any, Dict, Optional

from .api_client import _api_request, ensure_model_loaded
from .validation import is_translation_valid
from .data_processor import strip_thinking_tags

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


def get_translation(
    text: str,
    model_name: str,
    api_base_url: str,
    model_config: Dict[str, Any],
    glossary_text: Optional[str] = None,
    debug: bool = False,
    use_reasoning: bool = False,
    line_by_line: bool = False
) -> str:
    """Performs a translation request with validation and retries.

    This is the core function for direct (non-refined) translation. It:
    1.  Constructs a prompt using templates from the model's configuration.
    2.  Optionally adds a glossary and reasoning instructions.
    3.  Sends the request to the specified API endpoint.
    4.  Extracts the translation from the response.
    5.  Validates the translation using `is_translation_valid`.
    6.  Retries up to two times if the API call or validation fails.

    Args:
        text: The source text to translate.
        model_name: The name of the model to use for the translation.
        api_base_url: The base URL of the API server.
        model_config: The configuration dictionary for the specified model.
        glossary_text: Optional string containing glossary terms for context.
        debug: If True, enables extensive debug logging.
        use_reasoning: If True, uses a prompt template that asks the model to
                       provide its reasoning before the translation.
        line_by_line: If True, signals to the validation function that the
                      translation should be a single line.

    Returns:
        The validated translated text as a string.

    Raises:
        ConnectionError: If the API request fails after all retry attempts.
        ValueError: If a valid translation cannot be obtained after all
                    retry attempts.
    """
    if use_reasoning:
        template = model_config.get("reasoning_prompt_template", "{text}")
        prompt = template.format(text=text)
    else:
        template = model_config.get("prompt_template", "{text}")
        prompt = template.format(text=text)

    if glossary_text:
        prompt = f"Please use this glossary for context:\n{glossary_text}\n\n{prompt}"

    if debug:
        print(f"--- DEBUG: Translation Prompt ---\n{prompt}\n------------------------------------", file=sys.stderr)

    endpoint = model_config.get("endpoint", "chat/completions")
    payload = {"model": model_name, **model_config.get("params", {})}

    if endpoint == "chat/completions":
        payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        payload["prompt"] = prompt

    for attempt in range(3):
        try:
            response_data = _api_request(endpoint, payload, api_base_url, debug=debug)
            if endpoint == "chat/completions":
                raw_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                raw_response = response_data.get("choices", [{}])[0].get("text", "").strip()

            if use_reasoning:
                use_json = model_config.get("use_json_format", False)
                translated_text = _extract_translation_from_response(raw_response, debug=debug, use_json_format=use_json)
            else:
                translated_text = raw_response

            if is_translation_valid(text, translated_text, debug=debug, line_by_line=line_by_line):
                if debug:
                    print(f"--- DEBUG: Translation Result ---\n{translated_text}\n------------------------------------", file=sys.stderr)
                return translated_text

            if debug:
                print(f"--- DEBUG: Translation failed validation. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)

        except ConnectionError as e:
            if attempt < 2:
                print(f"--- DEBUG: Connection error. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
            else:
                raise e
    raise ValueError(f"Failed to get a valid translation for '{text[:50]}...' after 3 attempts")


def _get_refined_translation(
    original_text: str,
    draft_model: str,
    refine_model: str,
    draft_model_config: Dict[str, Any],
    refine_model_config: Dict[str, Any],
    num_drafts: int,
    api_base_url: str,
    glossary_text: Optional[str],
    glossary_for: str,
    reasoning_for: Optional[str],
    verbose: bool,
    debug: bool,
    line_by_line: bool = False
) -> str:
    """Orchestrates the two-step "refinement" translation process.

    This high-level function manages a sophisticated translation workflow:
    1.  **Load Draft Model**: Ensures the specified `draft_model` is loaded on
        the server.
    2.  **Generate Drafts**: Calls `get_translation` multiple times to create a
        set of initial, diverse translations of the `original_text`.
    3.  **Load Refine Model**: Ensures the `refine_model` is loaded.
    4.  **Refine**: Constructs a new prompt containing the original text and all
        the generated drafts, then calls the `refine_model` to produce a final,
        synthesized translation. This step also includes validation and retries.

    Args:
        original_text: The source text to translate.
        draft_model: Name of the model for generating initial drafts.
        refine_model: Name of the model for synthesizing the final translation.
        draft_model_config: Configuration for the draft model.
        refine_model_config: Configuration for the refine model.
        num_drafts: The number of drafts to generate.
        api_base_url: The base URL of the API server.
        glossary_text: Optional glossary to provide context.
        glossary_for: When to apply the glossary ('draft', 'refine', or 'all').
        reasoning_for: When to request reasoning ('draft', 'refine', or 'all').
        verbose: If True, prints status messages like model switching.
        debug: If True, enables extensive debug logging.
        line_by_line: If True, signals that the text is a single line.

    Returns:
        The final, refined translation as a string.

    Raises:
        ValueError: If a valid refined translation cannot be obtained after
                    all retry attempts.
"""
    use_draft_reasoning = reasoning_for in ['draft', 'all']
    use_refine_reasoning = reasoning_for in ['refine', 'all']

    # 1. Generate Drafts
    ensure_model_loaded(draft_model, api_base_url, verbose, debug=debug)
    draft_glossary = glossary_text if glossary_for in ['draft', 'all'] else None
    drafts = [
        get_translation(
            original_text,
            draft_model,
            api_base_url,
            draft_model_config,
            glossary_text=draft_glossary,
            debug=debug,
            use_reasoning=use_draft_reasoning,
            line_by_line=line_by_line
        ) for _ in range(num_drafts)
    ]

    # 2. Refine Drafts
    ensure_model_loaded(refine_model, api_base_url, verbose, debug=debug)
    draft_list = "\n".join(f"{i+1}. ```{d}```" for i, d in enumerate(drafts))

    if use_refine_reasoning:
        template = refine_model_config.get("refine_reasoning_prompt_template", "Refine: {draft_list}")
        prompt = template.format(original_text=original_text, draft_list=draft_list)
    else:
        template = refine_model_config.get("refine_prompt_template", "Refine: {draft_list}")
        prompt = template.format(original_text=original_text, draft_list=draft_list)

    if glossary_text and glossary_for in ['refine', 'all']:
        prompt = f"Please use this glossary for context:\n{glossary_text}\n\n{prompt}"

    endpoint = refine_model_config.get("endpoint", "chat/completions")
    payload = {"model": refine_model, **refine_model_config.get("params", {})}
    if endpoint == "chat/completions":
        payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        payload["prompt"] = prompt

    for attempt in range(3):
        try:
            response_data = _api_request(endpoint, payload, api_base_url, debug=debug)
            if endpoint == "chat/completions":
                full_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                full_response = response_data.get("choices", [{}])[0].get("text", "").strip()

            if use_refine_reasoning:
                use_json = refine_model_config.get("use_json_format", False)
                refined_text = _extract_translation_from_response(full_response, debug=debug, use_json_format=use_json)
            else:
                refined_text = full_response

            # After extraction, if the result is empty and we were expecting a result,
            # it means the extraction failed or the model returned an empty response.
            if use_refine_reasoning and not refined_text:
                if debug:
                    print(f"--- DEBUG: Refine reasoning mode enabled, but extraction resulted in empty string. Retrying...", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            if not is_translation_valid(original_text, refined_text, debug=debug, line_by_line=line_by_line):
                if debug:
                    print(f"--- DEBUG: Refined translation failed validation. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            return refined_text or original_text
        except ConnectionError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e

    raise ValueError(f"Failed to get a valid refined translation for '{original_text[:50]}...' after 3 attempts")
