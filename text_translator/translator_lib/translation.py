import time
import re
import sys
import json
from typing import Any, Dict, Optional

from .api_client import _api_request, ensure_model_loaded
from .validation import is_translation_valid

def _extract_translation_from_response(
    response: str,
    debug: bool = False,
    use_json_format: bool = False
) -> str:
    """
    Extracts the final translation from a model's response, supporting multiple formats.

    This function processes the raw text output from a language model. It attempts
    extraction in the following order:
    1.  If `use_json_format` is True, it tries to parse the response as JSON.
        It looks for a 'translation' key in the JSON object. It also handles
        cases where the JSON is wrapped in markdown code blocks.
    2.  It removes any 'thinking' blocks (e.g., <thinking>...</thinking>).
    3.  It looks for common markers (e.g., "Translation:", "Translated Text:")
        and extracts the text following them.
    4.  If no specific format is found, it returns the cleaned response as is.

    Args:
        response: The raw response text from the model.
        debug: If True, prints debugging information.
        use_json_format: If True, the function will first attempt to parse the
                         response as JSON.

    Returns:
        The extracted and cleaned translation.
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
    cleaned_response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL).strip()

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
    """
    Performs a single translation request with validation and retries.

    This function constructs the appropriate prompt using templates from the
    model configuration, sends it to the API, validates the response, and
    retries if validation fails.

    Args:
        text: The text to translate.
        model_name: The name of the model to use.
        api_base_url: The base URL of the translation API.
        model_config: The configuration dictionary for the specified model.
        glossary_text: Optional glossary to provide context.
        debug: If True, prints detailed debug information.
        use_reasoning: If True, instructs the model to provide its reasoning.
        line_by_line: If True, signals that the text is a single line.

    Returns:
        The validated translated text.

    Raises:
        ValueError: If a valid translation cannot be obtained after 3 attempts.
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

    endpoint = model_config.get("endpoint", "completions")
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
    """
    Implements the refinement process for translating a single piece of text.

    This process involves two main steps:
    1.  **Drafting**: Generates a specified number of initial translations using
        a 'draft' model.
    2.  **Refining**: Feeds the draft translations to a 'refine' model, which
        produces a final, higher-quality translation based on the drafts.

    Args:
        original_text: The text to translate.
        draft_model: The name of the model to use for generating drafts.
        refine_model: The name of the model to use for refining the drafts.
        draft_model_config: The configuration for the draft model.
        refine_model_config: The configuration for the refine model.
        num_drafts: The number of drafts to generate.
        api_base_url: The base URL of the translation API.
        glossary_text: Optional glossary to provide context.
        glossary_for: Specifies whether to use the glossary for 'draft', 'refine', or 'all'.
        reasoning_for: Specifies whether to request reasoning from the 'draft', 'refine', or 'all' models.
        verbose: If True, prints model loading messages.
        debug: If True, prints detailed debug information.
        line_by_line: If True, indicates that the text is a single line.

    Returns:
        The refined translation as a string.
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

    endpoint = refine_model_config.get("endpoint", "completions")
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
