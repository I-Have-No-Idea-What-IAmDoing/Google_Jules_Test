import requests
import sys
import os
import time
import json
import random
from tqdm import tqdm
from langdetect import detect, LangDetectException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from custom_xml_parser import parser

DEFAULT_API_BASE_URL = "http://127.0.0.1:5000/v1"

# --- API Communication & Model Management ---

def _api_request(endpoint, payload, api_base_url, timeout=60, is_get=False):
    headers = {"Content-Type": "application/json"}
    try:
        if is_get:
            response = requests.get(f"{api_base_url}/{endpoint}", timeout=timeout)
        else:
            response = requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Re-raise as a connection error for unified handling
        raise ConnectionError(f"API request to {endpoint} failed: {e}")

def get_current_model(api_base_url):
    """Gets the currently loaded model from the API."""
    try:
        response_data = _api_request("models", {}, api_base_url, is_get=True)
        return response_data.get("data", [{}])[0].get("id")
    except (ConnectionError, IndexError, KeyError) as e:
        raise ConnectionError(f"Error getting current model: {e}")

def ensure_model_loaded(model_name, api_base_url, verbose=False):
    """Checks if the correct model is loaded, and loads it if not."""
    current_model = get_current_model(api_base_url)
    if current_model != model_name:
        if verbose:
            print(f"Switching model from '{current_model}' to '{model_name}'...")
        try:
            _api_request("internal/model/load", {"model_name": model_name}, api_base_url, timeout=300)
            if verbose: print("Model loaded successfully.")
            time.sleep(5)
        except ConnectionError as e:
            raise ConnectionError(f"Failed to load model '{model_name}': {e}")

# --- Translation Logic ---

def get_direct_translation(text, model_name, api_base_url):
    """Gets a single direct translation with retry logic."""
    payload = {"prompt": f"Translate into English:\n\n{text}", "model": model_name}
    for attempt in range(3):
        try:
            response_data = _api_request("completions", payload, api_base_url)
            return response_data.get("choices", [{}])[0].get("text", "").strip() or text
        except ConnectionError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise e # Re-raise the final error
    return text

# ... (The rest of the file needs to be updated to use these restored functions) ...

def collect_text_nodes(data, nodes_list):
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

def cleanup_markers(data):
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
def translate_file(**args):
    input_path = args['input_path']
    api_base_url = args.get('api_base_url', DEFAULT_API_BASE_URL)

    if args.get('output_file') and os.path.exists(args['output_file']):
        if not args.get('quiet'): print(f"Output file {args['output_file']} already exists. Skipping.")
        return ""

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    data_structure = parser.deserialize(content)

    nodes_to_translate = []
    collect_text_nodes(data_structure, nodes_to_translate)

    if not nodes_to_translate:
        if not args.get('quiet'): print("No text to translate.")
        return parser.serialize(data_structure)

    with tqdm(total=len(nodes_to_translate), desc="Translating", unit="node", disable=args.get('quiet')) as pbar:
        if args.get('refine_mode'):
            # Refinement Batch Logic
            draft_model = args['draft_model']
            refine_model = args['model_name']

            ensure_model_loaded(draft_model, api_base_url, args.get('verbose'))
            drafts_data = []
            for node in nodes_to_translate:
                original_text = node['#text']
                drafts = [get_direct_translation(original_text, draft_model, api_base_url) for _ in range(6)]
                drafts_data.append({'original': original_text, 'drafts': drafts, 'node_ref': node})
                pbar.update(0.5)

            ensure_model_loaded(refine_model, api_base_url, args.get('verbose'))
            for item in drafts_data:
                draft_list = "\n".join(f"{i+1}. ```{d}```" for i, d in enumerate(item['drafts']))
                prompt = f"Refine these translations of '{item['original']}':\n{draft_list}"
                payload = {"prompt": prompt, "model": refine_model}
                refined_text = _api_request("completions", payload, api_base_url).get("choices", [{}])[0].get("text", "").strip()
                item['node_ref']['#text'] = f"jp_text:::{refined_text or item['original']}"
                pbar.update(0.5)
        else:
            # Direct Batch Logic
            model_name = args['model_name']
            ensure_model_loaded(model_name, api_base_url, args.get('verbose'))
            for node in nodes_to_translate:
                translated_text = get_direct_translation(node['#text'], model_name, api_base_url)
                node['#text'] = f"jp_text:::{translated_text or node['#text']}"
                pbar.update(1)

    cleanup_markers(data_structure)
    return parser.serialize(data_structure)
