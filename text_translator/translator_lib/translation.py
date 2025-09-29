import time
import re
import sys
import json
from typing import Any, Dict, Optional

from .api_client import _api_request, ensure_model_loaded
from .validation import is_translation_valid
from .data_processor import _extract_translation_from_response
from .exceptions import TranslationError, APIConnectionError, APIStatusError


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
    1.  Constructs a prompt using templates from the model's configuration,
        including system prompts and glossary injection.
    2.  Sends the request to the specified API endpoint.
    3.  Extracts the translation from the response.
    4.  Validates the translation using `is_translation_valid`.
    5.  Retries up to two times if the API call or validation fails.

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
        TranslationError: If the API request or validation fails after all
                          retry attempts.
    """
    # 1. Prepare glossary section
    glossary_section = ""
    if glossary_text:
        glossary_template = model_config.get("glossary_prompt_template", "{glossary_text}")
        glossary_section = glossary_template.format(glossary_text=glossary_text)

    # 2. Prepare main prompt
    template_key = "reasoning_prompt_template" if use_reasoning else "prompt_template"
    template = model_config.get(template_key, "{text}")
    prompt = template.format(text=text, glossary_section=glossary_section)

    if debug:
        print(f"--- DEBUG: Translation Prompt ---\n{prompt}\n------------------------------------", file=sys.stderr)

    # 3. Prepare payload with system prompt if available
    endpoint = model_config.get("endpoint", "chat/completions")
    payload = {"model": model_name, **model_config.get("params", {})}
    system_prompt = model_config.get("system_prompt_template")

    if endpoint == "chat/completions":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload["messages"] = messages
    else:  # Legacy "completions" endpoint
        # For older models, we combine the system prompt and user prompt.
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload["prompt"] = full_prompt

    # 4. Execute API call with retries
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

        except (APIConnectionError, APIStatusError) as e:
            if attempt < 2:
                print(f"--- DEBUG: API error. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
            else:
                raise TranslationError(f"API request failed after multiple retries: {e}") from e
    raise TranslationError(f"Failed to get a valid translation for '{text[:50]}...' after 3 attempts")


def _get_refined_translation(
    original_text: str,
    draft_model: str,
    refine_model: str,
    draft_model_config: Dict[str, Any],
    refine_model_config: Dict[str, Any],
    num_drafts: int,
    api_base_url: str,
    glossary_text: Optional[str],
    glossary_for: Optional[str],
    reasoning_for: Optional[str],
    verbose: bool,
    debug: bool,
    line_by_line: bool = False
) -> str:
    """Orchestrates the two-step "refinement" translation process."""
    use_draft_reasoning = reasoning_for in ['draft', 'all']
    use_refine_reasoning = reasoning_for in ['refine', 'all']
    effective_glossary_for = glossary_for or 'all'

    # 1. Generate Drafts
    ensure_model_loaded(draft_model, api_base_url, model_config=draft_model_config, verbose=verbose, debug=debug)
    draft_glossary = glossary_text if effective_glossary_for in ['draft', 'all'] else None
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
    ensure_model_loaded(refine_model, api_base_url, model_config=refine_model_config, verbose=verbose, debug=debug)
    draft_list = "\n".join(f"{i+1}. ```{d}```" for i, d in enumerate(drafts))

    # Prepare glossary for the refinement prompt
    refine_glossary_section = ""
    if glossary_text and effective_glossary_for in ['refine', 'all']:
        glossary_template = refine_model_config.get("glossary_prompt_template", "{glossary_text}")
        refine_glossary_section = glossary_template.format(glossary_text=glossary_text)

    # Prepare the main refinement prompt
    template_key = "refine_reasoning_prompt_template" if use_refine_reasoning else "refine_prompt_template"
    template = refine_model_config.get(template_key, "Refine: {draft_list}")
    prompt = template.format(
        original_text=original_text,
        draft_list=draft_list,
        glossary_section=refine_glossary_section
    )

    if debug:
        print(f"--- DEBUG: Refine Prompt ---\n{prompt}\n------------------------------------", file=sys.stderr)

    # Prepare payload for the refinement API call
    endpoint = refine_model_config.get("endpoint", "chat/completions")
    payload = {"model": refine_model, **refine_model_config.get("params", {})}
    system_prompt = refine_model_config.get("system_prompt_template")

    if endpoint == "chat/completions":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload["messages"] = messages
    else: # Legacy "completions" endpoint
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload["prompt"] = full_prompt

    # Execute API call with retries
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

            if use_refine_reasoning and not refined_text:
                if debug:
                    print(f"--- DEBUG: Refine reasoning resulted in empty string. Retrying...", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            if not is_translation_valid(original_text, refined_text, debug=debug, line_by_line=line_by_line):
                if debug:
                    print(f"--- DEBUG: Refined translation failed validation. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            return refined_text or original_text
        except (APIConnectionError, APIStatusError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise TranslationError(f"API request failed during refinement after multiple retries: {e}") from e

    raise TranslationError(f"Failed to get a valid refined translation for '{original_text[:50]}...' after 3 attempts")