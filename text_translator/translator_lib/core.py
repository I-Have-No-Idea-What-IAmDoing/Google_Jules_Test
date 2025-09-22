import requests
import sys
import os
import time
import json
import random
import re
from collections import Counter
from tqdm import tqdm
from langdetect import detect, LangDetectException
from typing import Any, Dict, List, Optional, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from custom_xml_parser import parser

DEFAULT_API_BASE_URL: str = "http://127.0.0.1:5000/v1"

# --- API Communication & Model Management ---

def check_server_status(api_base_url: str, debug: bool = False) -> None:
    """
    Checks if the translation API server is running and available.

    Sends a request to a known endpoint. If the request fails, it prints an
    error message and terminates the program.

    Args:
        api_base_url: The base URL of the API server.
        debug: If True, prints debug information for the check.
    """
    if debug:
        print(f"--- DEBUG: Checking server status at {api_base_url} ---", file=sys.stderr)
    try:
        _api_request("internal/model/info", {}, api_base_url, is_get=True, timeout=10, debug=debug)
        if debug:
            print(f"--- DEBUG: Server is active. ---", file=sys.stderr)
    except ConnectionError:
        print(
            f"\n---FATAL ERROR---\n"
            f"Could not connect to the translation API server at '{api_base_url}'.\n"
            f"Please ensure the oobabooga web UI server is running and the API is enabled.\n"
            f"-------------------\n",
            file=sys.stderr
        )
        sys.exit(1)


def _api_request(endpoint: str, payload: Dict[str, Any], api_base_url: str, timeout: int = 60, is_get: bool = False, debug: bool = False) -> Dict[str, Any]:
    """
    Sends a request to the specified API endpoint and handles responses.

    This is a low-level helper for communicating with the API. It wraps the
    `requests` library to handle POST/GET requests, JSON serialization, and
    common exceptions.

    Args:
        endpoint: The API endpoint to target (e.g., "completions").
        payload: The dictionary to send as a JSON payload.
        api_base_url: The base URL of the API server.
        timeout: The request timeout in seconds.
        is_get: If True, sends a GET request; otherwise, sends a POST request.
        debug: If True, prints the request payload and response.

    Returns:
        The JSON response from the API as a dictionary.

    Raises:
        ConnectionError: If the request fails due to a network error or an
                         unsuccessful HTTP status code.
    """
    headers = {"Content-Type": "application/json"}
    if debug:
        print(f"\n--- DEBUG: API Request to endpoint: {endpoint} ---", file=sys.stderr)
        print(f"--- DEBUG: API Request Payload ---\n{json.dumps(payload, indent=2)}\n-------------------------------------", file=sys.stderr)

    try:
        if is_get:
            response = requests.get(f"{api_base_url}/{endpoint}", timeout=timeout)
        else:
            response = requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        response_data = response.json()

        if debug:
            print(f"--- DEBUG: API Response ---\n{json.dumps(response_data, indent=2)}\n--------------------------------", file=sys.stderr)

        return response_data
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request to {endpoint} failed: {e}")


def ensure_model_loaded(model_name: str, api_base_url: str, verbose: bool = False, debug: bool = False) -> None:
    """
    Ensures the specified model is loaded on the API server.

    Queries the server for the currently loaded model. If it does not match
    the desired model, this function sends a request to load the correct one
    and waits for it to complete.

    Args:
        model_name: The name of the model that should be loaded.
        api_base_url: The base URL of the API server.
        verbose: If True, prints status messages about model switching.
        debug: If True, passes debug flag to the underlying API request.

    Raises:
        ConnectionError: If it fails to get the current model or load the new one.
    """
    try:
        current_model_data = _api_request("internal/model/info", {}, api_base_url, is_get=True, debug=debug)
        current_model = current_model_data.get("model_name")
    except (ConnectionError, KeyError) as e:
        raise ConnectionError(f"Error getting current model: {e}")

    if current_model != model_name:
        if verbose:
            print(f"Switching model from '{current_model}' to '{model_name}'...")
        try:
            _api_request("internal/model/load", {"model_name": model_name}, api_base_url, timeout=300, debug=debug)
            if verbose: print("Model loaded successfully.")
            time.sleep(5)
        except ConnectionError as e:
            raise ConnectionError(f"Failed to load model '{model_name}': {e}")

# --- Translation Logic ---

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

    payload = {
        "prompt": prompt,
        "model": model_name,
        **model_config.get("params", {})
    }

    for attempt in range(3):
        try:
            response_data = _api_request("completions", payload, api_base_url, debug=debug)
            full_response = response_data.get("choices", [{}])[0].get("text", "").strip() or text

            if use_reasoning:
                if 'Translation:' in full_response:
                    _, translated_text = full_response.rsplit('Translation:', 1)
                    translated_text = translated_text.strip()
                else:
                    if debug:
                        print(f"--- DEBUG: Reasoning mode enabled, but 'Translation:' marker not found. Retrying...", file=sys.stderr)
                    time.sleep(2 ** attempt)
                    continue
            else:
                translated_text = full_response

            if not is_translation_valid(text, translated_text, debug=debug, line_by_line=line_by_line):
                if debug:
                    print(f"--- DEBUG: Translation failed validation. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            if debug:
                print(f"--- DEBUG: Translation Result ---\n{translated_text}\n------------------------------------", file=sys.stderr)
            return translated_text
        except ConnectionError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e
    raise ValueError(f"Failed to get a valid translation for '{text[:50]}...' after 3 attempts")

# --- Data Processing & Workflow ---

def collect_text_nodes(data: Union[Dict[str, Any], List[Any]], nodes_list: List[Dict[str, Any]]) -> None:
    """
    Recursively finds all text nodes in the data structure that need translation.

    A node needs translation if its key is `"#text"`, its value is a string,
    it is not already marked as processed (with `jp_text:::`), and its language
    is detected as non-English.

    Args:
        data: The nested dictionary or list to traverse.
        nodes_list: A list to which the dictionaries containing text nodes
                    (i.e., the parent dict of the '#text' key) are appended.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str):
                try:
                    if not value.startswith("jp_text:::") and detect(value) != 'en':
                        nodes_list.append(data)
                except LangDetectException:
                    nodes_list.append(data)
            else:
                collect_text_nodes(value, nodes_list)
    elif isinstance(data, list):
        for item in data:
            collect_text_nodes(item, nodes_list)

def cleanup_markers(data: Union[Dict[str, Any], List[Any]]) -> None:
    """
    Recursively removes the 'jp_text:::' processing marker from all text nodes.

    This is called after translation is complete to clean up the temporary
    markers used to prevent re-translation.

    Args:
        data: The nested dictionary or list to clean.
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

# --- Main Orchestrator ---

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

    payload = {
        "prompt": prompt,
        "model": refine_model,
        **refine_model_config.get("params", {})
    }

    for attempt in range(3):
        try:
            response_data = _api_request("completions", payload, api_base_url, debug=debug)
            full_response = response_data.get("choices", [{}])[0].get("text", "").strip()

            if use_refine_reasoning:
                if 'Translation:' in full_response:
                    _, refined_text = full_response.rsplit('Translation:', 1)
                    refined_text = refined_text.strip()
                else:
                    if debug:
                        print(f"--- DEBUG: Refine reasoning mode enabled, but 'Translation:' marker not found. Retrying...", file=sys.stderr)
                    time.sleep(2 ** attempt)
                    continue
            else:
                refined_text = full_response

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


from .options import TranslationOptions

def translate_file(options: TranslationOptions) -> str:
    """
    Orchestrates the entire translation process for a single file.

    This function reads a file, deserializes it using the custom_xml_parser,
    identifies all text nodes needing translation, and then translates them
    according to the specified options. It supports direct translation, a
    refinement mode (generating drafts and then refining them), and various
    other configurations like line-by-line processing and glossaries.

    Args:
        options: A TranslationOptions object containing all settings for the
                 translation job, such as input/output paths, model names,
                 API details, and processing flags.

    Returns:
        A string containing the full content of the file with all targeted
        text nodes translated, serialized back into the custom format.
        Returns an empty string if the output file already exists and
        overwrite is not enabled.
    """
    # --- File I/O and Setup ---
    if options.output_path and os.path.exists(options.output_path) and not options.overwrite:
        if not options.quiet: print(f"Output file {options.output_path} already exists. Skipping.")
        return ""

    with open(options.input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    data_structure = parser.deserialize(content)

    nodes_to_translate: List[Dict[str, Any]] = []
    collect_text_nodes(data_structure, nodes_to_translate)

    if not nodes_to_translate:
        if not options.quiet: print("No text to translate.")
        return parser.serialize(data_structure)

    # --- Pre-load model for direct mode to avoid reloading in loop ---
    if not options.refine_mode:
        ensure_model_loaded(options.model_name, options.api_base_url, options.verbose, debug=options.debug)

    # --- Main Translation Loop ---
    with tqdm(total=len(nodes_to_translate), desc="Translating", unit="node", disable=options.quiet) as pbar:
        for node in nodes_to_translate:
            original_text = node['#text']
            translated_text = ""

            if options.line_by_line:
                lines = original_text.splitlines(True) # Keep endings
                translated_lines = []
                for line in lines:
                    if not line.strip():
                        translated_lines.append(line)
                        continue

                    if options.refine_mode:
                        translated_line = _get_refined_translation(
                            original_text=line,
                            draft_model=options.draft_model,
                            refine_model=options.model_name,
                            draft_model_config=options.draft_model_config,
                            refine_model_config=options.model_config,
                            num_drafts=options.num_drafts,
                            api_base_url=options.api_base_url,
                            glossary_text=options.glossary_text,
                            glossary_for=options.glossary_for,
                            reasoning_for=options.reasoning_for,
                            verbose=options.verbose,
                            debug=options.debug,
                            line_by_line=True
                        )
                    else: # Direct mode
                        translated_line = get_translation(
                            text=line,
                            model_name=options.model_name,
                            api_base_url=options.api_base_url,
                            model_config=options.model_config,
                            glossary_text=options.glossary_text,
                            debug=options.debug,
                            use_reasoning=(options.reasoning_for in ['main', 'all']),
                            line_by_line=True
                        )
                    translated_lines.append(translated_line)
                translated_text = "".join(translated_lines)
            else: # Translate entire node at once
                if options.refine_mode:
                    translated_text = _get_refined_translation(
                        original_text=original_text,
                        draft_model=options.draft_model,
                        refine_model=options.model_name,
                        draft_model_config=options.draft_model_config,
                        refine_model_config=options.model_config,
                        num_drafts=options.num_drafts,
                        api_base_url=options..api_base_url,
                        glossary_text=options.glossary_text,
                        glossary_for=options.glossary_for,
                        reasoning_for=options.reasoning_for,
                        verbose=options.verbose,
                        debug=options.debug
                    )
                else: # Direct mode
                    translated_text = get_translation(
                        text=original_text,
                        model_name=options.model_name,
                        api_base_url=options.api_base_url,
                        model_config=options.model_config,
                        glossary_text=options.glossary_text,
                        debug=options.debug,
                        use_reasoning=(options.reasoning_for in ['main', 'all'])
                    )

            node['#text'] = f"jp_text:::{translated_text or original_text}"
            pbar.update(1)

    cleanup_markers(data_structure)
    return parser.serialize(data_structure)
