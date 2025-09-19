import requests
import sys
import os
import time
import json
import random
from tqdm import tqdm
from langdetect import detect, LangDetectException
from typing import Any, Dict, List, Optional, Union

# TODO: Add overwrite flag which overwrite files instead of just skipping them
# TODO: Check if server if active before any api request and if not then alert the user and stop

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from custom_xml_parser import parser

DEFAULT_API_BASE_URL: str = "http://127.0.0.1:5000/v1"

# --- API Communication & Model Management ---

def _api_request(endpoint: str, payload: Dict[str, Any], api_base_url: str, timeout: int = 60, is_get: bool = False, debug: int = 0) -> Dict[str, Any]:
    """
    Internal helper to send a request to the API, handling exceptions.
    """
    headers = {"Content-Type": "application/json"}
    if debug >= 1:
        print(f"\n--- DEBUG (L1): API Request to endpoint: {endpoint} ---", file=sys.stderr)
    if debug >= 3:
        print(f"--- DEBUG (L3): API Request Payload ---\n{json.dumps(payload, indent=2)}\n-------------------------------------", file=sys.stderr)

    try:
        if is_get:
            response = requests.get(f"{api_base_url}/{endpoint}", timeout=timeout)
        else:
            response = requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        response_data = response.json()

        if debug >= 3:
            print(f"--- DEBUG (L3): API Response ---\n{json.dumps(response_data, indent=2)}\n--------------------------------", file=sys.stderr)

        return response_data
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request to {endpoint} failed: {e}")

def ensure_model_loaded(model_name: str, api_base_url: str, verbose: bool = False, debug: int = 0) -> None:
    """
    Checks if the correct model is loaded on the server and loads it if not.

    Args:
        model_name (str): The name of the model that should be loaded.
        api_base_url (str): The base URL of the API.
        verbose (bool): If True, prints status messages.
        debug (int): The debug level for logging.

    Raises:
        ConnectionError: If API calls to check or load the model fail.
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

def is_translation_valid(original_text: str, translated_text: str, debug: int = 0, line_by_line: bool = False) -> bool:
    """
    Validates the translated text against a set of heuristics.
    """
    # 1. Check for empty or whitespace-only translation
    if not translated_text.strip():
        if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation is empty.", file=sys.stderr)
        return False

    # 2. Check for identity with the original text
    if translated_text.strip() == original_text.strip():
        if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation is identical to original.", file=sys.stderr)
        return False

    # 3. Check for common model refusal phrases
    refusal_phrases = ["i'm sorry", "i cannot", "i am unable", "as an ai"]
    if any(phrase in translated_text.lower() for phrase in refusal_phrases):
        if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation contains a refusal phrase.", file=sys.stderr)
        return False

    # 4. Check if the translation is in English
    try:
        lang = detect(translated_text)
        if lang != 'en':
            if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation is not in English (detected: {lang}).", file=sys.stderr)
            return False
    except LangDetectException:
        # If language detection fails, assume it's valid to avoid false positives
        if debug >= 2: print(f"--- DEBUG (L2): Language detection failed. Assuming valid.", file=sys.stderr)
        pass

    # 5. Check if the translation contains the original text (for longer strings)
    # This is a strong indicator of the model simply repeating the input.
    if len(original_text) > 15 and original_text.lower() in translated_text.lower():
        if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation contains original text.", file=sys.stderr)
        return False

    # 6. Check for multiple lines when in line-by-line mode
    if line_by_line and len(translated_text.strip().splitlines()) > 1:
        if debug >= 1: print(f"--- DEBUG (L1): Validation failed: Translation contains multiple lines in line-by-line mode.", file=sys.stderr)
        return False

    return True

def get_translation(text: str, model_name: str, api_base_url: str, glossary_text: Optional[str] = None, debug: int = 0, use_reasoning: bool = False, line_by_line: bool = False, **kwargs: Any) -> str:
    """
    Gets a translation for a single piece of text, with retries.
    This is the simplest translation function, used for drafts and direct mode.
    """
    if use_reasoning:
        prompt = (
            "First, provide a step-by-step reasoning for your translation, including cultural nuances and grammar points. "
            "Then, on a new line, provide the final translation, and nothing else, prefixed with 'Translation:'.\n\n"
            f"Original text: {text}"
        )
    else:
        prompt = f"Translate the following segment into English, without additional explanation or commentary:\n\n{text}"

    if glossary_text:
        prompt = f"Please use this glossary for context:\n{glossary_text}\n\n{prompt}"

    if debug >= 2:
        print(f"--- DEBUG (L2): Translation Prompt ---\n{prompt}\n------------------------------------", file=sys.stderr)

    payload = {"prompt": prompt, "model": model_name}
    for attempt in range(3):
        try:
            response_data = _api_request("completions", payload, api_base_url, debug=debug)
            full_response = response_data.get("choices", [{}])[0].get("text", "").strip() or text

            if use_reasoning:
                if 'Translation:' in full_response:
                    _, translated_text = full_response.rsplit('Translation:', 1)
                    translated_text = translated_text.strip()
                else:
                    if debug >= 1:
                        print(f"--- DEBUG (L1): Reasoning mode enabled, but 'Translation:' marker not found. Retrying...", file=sys.stderr)
                    time.sleep(2 ** attempt)
                    continue
            else:
                translated_text = full_response

            if not is_translation_valid(text, translated_text, debug, line_by_line=line_by_line):
                if debug >= 1:
                    print(f"--- DEBUG (L1): Translation failed validation. Retrying... (Attempt {attempt + 1}/3)", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue

            if debug >= 1:
                print(f"--- DEBUG (L1): Translation Result ---\n{translated_text}\n------------------------------------", file=sys.stderr)
            return translated_text
        except ConnectionError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e
    return text

# --- Data Processing & Workflow ---

def collect_text_nodes(data: Union[Dict[str, Any], List[Any]], nodes_list: List[Dict[str, Any]]) -> None:
    """
    Recursively traverses the data structure to find all text nodes that
    need translation (non-English and not already processed).

    Args:
        data (dict or list): The data structure to traverse.
        nodes_list (list): A list to which references of text nodes will be appended.
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
    """Recursively removes the 'jp_text:::' processing markers from the data."""
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
    num_drafts: int,
    api_base_url: str,
    glossary_text: Optional[str],
    glossary_for: str,
    reasoning_for: Optional[str],
    verbose: bool,
    debug: int,
    line_by_line: bool = False
) -> str:
    """
    Gets a refined translation for a single piece of text.
    """
    use_draft_reasoning = reasoning_for in ['draft', 'all']
    use_refine_reasoning = reasoning_for in ['refine', 'all']

    # 1. Generate Drafts
    ensure_model_loaded(draft_model, api_base_url, verbose, debug=debug)
    draft_glossary = glossary_text if glossary_for in ['draft', 'all'] else None
    drafts = [get_translation(original_text, draft_model, api_base_url, glossary_text=draft_glossary, debug=debug, use_reasoning=use_draft_reasoning, line_by_line=line_by_line) for _ in range(num_drafts)]

    # 2. Refine Drafts
    ensure_model_loaded(refine_model, api_base_url, verbose, debug=debug)
    draft_list = "\n".join(f"{i+1}. ```{d}```" for i, d in enumerate(drafts))

    if use_refine_reasoning:
        prompt = (
            "First, provide a step-by-step reasoning for your translation refinement, explaining your choices. "
            "Then, on a new line, provide the final refined translation, and nothing else, prefixed with 'Translation:'.\n\n"
            f"Refine these translations of '{original_text}':\n{draft_list}"
        )
    else:
        prompt = f"Refine these translations of '{original_text}':\n{draft_list}"

    if glossary_text and glossary_for in ['refine', 'all']:
        prompt = f"Please use this glossary for context:\n{glossary_text}\n\n{prompt}"

    payload = {"prompt": prompt, "model": refine_model}
    response_data = _api_request("completions", payload, api_base_url, debug=debug)
    full_response = response_data.get("choices", [{}])[0].get("text", "").strip()

    if use_refine_reasoning:
        if 'Translation:' in full_response:
            _, refined_text = full_response.rsplit('Translation:', 1)
            refined_text = refined_text.strip()
        else:
            if debug >= 1:
                print(f"--- DEBUG (L1): Refine reasoning mode enabled, but 'Translation:' marker not found. Using full response.", file=sys.stderr)
            refined_text = full_response
    else:
        refined_text = full_response

    return refined_text or original_text


def translate_file(**args: Any) -> str:
    """
    The main orchestrator function for the entire translation process.
    Handles file I/O, batching, model loading, and progress display.

    Args:
        **args (dict): A dictionary of arguments from the CLI.
    """
    # --- Argument Unpacking ---
    input_path = args['input_path']
    api_base_url = args.get('api_base_url', DEFAULT_API_BASE_URL)
    glossary_text = args.get('glossary_text')
    glossary_for = args.get('glossary_for', 'all')
    debug_mode = args.get('debug', 0)
    reasoning_for = args.get('reasoning_for')
    verbose = args.get('verbose', False)
    line_by_line = args.get('line_by_line', False)
    refine_mode = args.get('refine_mode', False)
    model_name = args.get('model_name')

    # --- File I/O and Setup ---
    if args.get('output_file') and os.path.exists(args['output_file']):
        if not args.get('quiet'): print(f"Output file {args['output_file']} already exists. Skipping.")
        return ""

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    data_structure = parser.deserialize(content)

    nodes_to_translate: List[Dict[str, Any]] = []
    collect_text_nodes(data_structure, nodes_to_translate)

    if not nodes_to_translate:
        if not args.get('quiet'): print("No text to translate.")
        return parser.serialize(data_structure)

    # --- Pre-load model for direct mode to avoid reloading in loop ---
    if not refine_mode:
        ensure_model_loaded(model_name, api_base_url, verbose, debug=debug_mode)

    # --- Main Translation Loop ---
    with tqdm(total=len(nodes_to_translate), desc="Translating", unit="node", disable=args.get('quiet')) as pbar:
        for node in nodes_to_translate:
            original_text = node['#text']
            translated_text = ""

            if line_by_line:
                had_trailing_newline = original_text.endswith('\n')
                lines = original_text.splitlines()
                translated_lines = []
                for line in lines:
                    if not line.strip():
                        translated_lines.append(line)
                        continue

                    if refine_mode:
                        translated_line = _get_refined_translation(
                            original_text=line,
                            draft_model=args['draft_model'],
                            refine_model=model_name,
                            num_drafts=args.get('num_drafts', 6),
                            api_base_url=api_base_url,
                            glossary_text=glossary_text,
                            glossary_for=glossary_for,
                            reasoning_for=reasoning_for,
                            verbose=verbose,
                            debug=debug_mode,
                            line_by_line=True
                        )
                    else: # Direct mode
                        translated_line = get_translation(
                            text=line,
                            model_name=model_name,
                            api_base_url=api_base_url,
                            glossary_text=glossary_text,
                            debug=debug_mode,
                            use_reasoning=(reasoning_for in ['main', 'all']),
                            line_by_line=True
                        )
                    translated_lines.append(translated_line)
                translated_text = "\n".join(translated_lines)
                if had_trailing_newline and not translated_text.endswith('\n'):
                    translated_text += '\n'
            else: # Translate entire node at once
                if refine_mode:
                    translated_text = _get_refined_translation(
                        original_text=original_text,
                        draft_model=args['draft_model'],
                        refine_model=model_name,
                        num_drafts=args.get('num_drafts', 6),
                        api_base_url=api_base_url,
                        glossary_text=glossary_text,
                        glossary_for=glossary_for,
                        reasoning_for=reasoning_for,
                        verbose=verbose,
                        debug=debug_mode
                    )
                else: # Direct mode
                    translated_text = get_translation(
                        text=original_text,
                        model_name=model_name,
                        api_base_url=api_base_url,
                        glossary_text=glossary_text,
                        debug=debug_mode,
                        use_reasoning=(reasoning_for in ['main', 'all'])
                    )

            node['#text'] = f"jp_text:::{translated_text or original_text}"
            pbar.update(1)

    cleanup_markers(data_structure)
    return parser.serialize(data_structure)
