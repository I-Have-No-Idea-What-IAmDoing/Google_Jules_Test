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
def _api_request(endpoint, payload, api_base_url, timeout=60):
    headers = {"Content-Type": "application/json"}
    return requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)

def get_current_model(api_base_url):
    try:
        response = requests.get(f"{api_base_url}/models", timeout=10)
        response.raise_for_status()
        return response.json().get("data", [{}])[0].get("id")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error getting current model: {e}")

def ensure_model_loaded(model_name, api_base_url, verbose=False):
    """Checks if the correct model is loaded, and loads it if not."""
    current_model = get_current_model(api_base_url)
    if current_model != model_name:
        if verbose:
            print(f"Switching model from '{current_model}' to '{model_name}'...")
        try:
            response = _api_request("internal/model/load", {"model_name": model_name}, api_base_url, timeout=300)
            response.raise_for_status()
            if verbose: print("Model loaded successfully.")
            time.sleep(5) # Give the server a moment to settle
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to load model '{model_name}': {e}")

# --- Translation Logic ---
def get_translation(original_text, **kwargs):
    """
    Handles both direct and refinement translation modes.
    `kwargs` should contain all necessary parameters like models, mode, etc.
    """
    api_base_url = kwargs['api_base_url']

    if kwargs.get('refine_mode'):
        # 1. Generate drafts
        ensure_model_loaded(kwargs['draft_model'], api_base_url, kwargs.get('verbose'))
        drafts = []
        draft_prompt = f"Translate the following segment into English:\n\n{original_text}"
        for i in range(6):
            payload = {"prompt": draft_prompt, "model": kwargs['draft_model'], "temperature": random.uniform(0.6, 0.95)}
            draft = _api_request("completions", payload, api_base_url)
            if draft: drafts.append(draft)
        if len(drafts) < 3: raise Exception(f"Failed to generate enough drafts, only got {len(drafts)}.")

        # 2. Refine drafts
        ensure_model_loaded(kwargs['model_name'], api_base_url, kwargs.get('verbose'))
        draft_list = "\n".join(f"{i+1}. ```{draft}```" for i, draft in enumerate(drafts))
        refine_prompt = (f"Analyze the following multiple English translations of the Japanese segment "
                         f"and generate a single refined English translation.\n\n"
                         f"The Japanese segment:\n```{original_text}```\n\n"
                         f"The multiple English translations:\n{draft_list}")
        payload = {"prompt": refine_prompt, "model": kwargs['model_name'], "temperature": 0.5}
        return _api_request("completions", payload, api_base_url)
    else:
        # Direct translation
        ensure_model_loaded(kwargs['model_name'], api_base_url, kwargs.get('verbose'))
        prompt = f"Translate the following segment into English:\n\n{original_text}"
        payload = {"prompt": prompt, "model": kwargs['model_name'], "max_tokens": 2048}
        return _api_request("completions", payload, api_base_url)

# --- Data Processing ---
def count_text_nodes(data):
    # ... (same as before)
    count = 0
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str) and not value.startswith("jp_text:::"):
                try:
                    if detect(value) != 'en': count += 1
                except LangDetectException: count += 1
            else: count += count_text_nodes(value)
    elif isinstance(data, list):
        for item in data: count += count_text_nodes(item)
    return count

def process_data(data, pbar, args):
    # ... (refactored to use the new get_translation function) ...
    state = {'count': 0}
    def _save_checkpoint(full_data):
        if args.get('checkpoint_path') and args.get('checkpoint_freq', 0) > 0:
            if args.get('verbose'): pbar.write(f"--- Saving checkpoint to {args['checkpoint_path']} ---")
            with open(args['checkpoint_path'], 'w', encoding='utf-8') as f: json.dump(full_data, f, ensure_ascii=False, indent=4)
    def _recursive_process(sub_data, full_data_root):
        if isinstance(sub_data, dict):
            for key, value in sub_data.items():
                if key == "#text" and isinstance(value, str) and not value.startswith("jp_text:::"):
                    original_text = value
                    try:
                        if detect(original_text) == 'en':
                            sub_data[key] = f"jp_text:::{original_text}"
                            continue
                    except LangDetectException: pass

                    translated_text = get_translation(original_text, **args)
                    sub_data[key] = f"jp_text:::{translated_text or original_text}"
                    pbar.update(1)
                    state['count'] += 1
                    if state['count'] % args.get('checkpoint_freq', 10) == 0: _save_checkpoint(full_data_root)
                else: _recursive_process(value, full_data_root)
        elif isinstance(sub_data, list):
            for item in sub_data: _recursive_process(item, full_data_root)
    def _cleanup_markers(sub_data):
        if isinstance(sub_data, dict):
            for key, value in sub_data.items():
                if key == "#text" and isinstance(value, str) and value.startswith("jp_text:::"): sub_data[key] = value.replace("jp_text:::", "", 1)
                else: _cleanup_markers(value)
        elif isinstance(sub_data, list):
            for item in sub_data: _cleanup_markers(item)
    _recursive_process(data, data)
    _cleanup_markers(data)
    if args.get('checkpoint_path') and args.get('checkpoint_freq', 0) > 0: _save_checkpoint(data)

# --- Main Orchestrator ---
def translate_file(**args):
    checkpoint_path = f"{args['input_path']}.checkpoint.json"
    try:
        if os.path.exists(checkpoint_path):
            if not args.get('quiet'): print(f"Resuming from checkpoint: {checkpoint_path}")
            with open(checkpoint_path, 'r', encoding='utf-8') as f: data_structure = json.load(f)
        else:
            with open(args['input_path'], 'r', encoding='utf-8') as f: content = f.read()
            data_structure = parser.deserialize(content)

        nodes_to_translate = count_text_nodes(data_structure)
        if nodes_to_translate == 0:
            if not args.get('quiet'): print("No text to translate.")
            return parser.serialize(data_structure)

        with tqdm(total=nodes_to_translate, desc="Translating", unit="node", disable=args.get('quiet')) as pbar:
            args['checkpoint_path'] = checkpoint_path
            process_data(data_structure, pbar, args)

        if os.path.exists(checkpoint_path): os.remove(checkpoint_path)
        return parser.serialize(data_structure)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        if 'checkpoint_path' in locals() and os.path.exists(checkpoint_path):
             print(f"Work has been saved to checkpoint file: {checkpoint_path}", file=sys.stderr)
        raise
