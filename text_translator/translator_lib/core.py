import requests
import sys
import os
import time
import json
from tqdm import tqdm

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from custom_xml_parser import parser

DEFAULT_API_BASE_URL = "http://127.0.0.1:5000/v1"

def get_current_model(api_base_url):
    """Gets the currently loaded model from the API."""
    try:
        response = requests.get(f"{api_base_url}/models")
        response.raise_for_status()
        models = response.json()
        if models.get("data"):
            return models["data"][0].get("id")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting current model: {e}", file=sys.stderr)
        return None

def load_model(model_name, api_base_url, verbose=False):
    """Loads a new model via the API."""
    if verbose:
        print(f"Attempting to load model: {model_name}...")
    try:
        response = requests.post(
            f"{api_base_url}/internal/model/load",
            json={"model_name": model_name},
            timeout=300
        )
        response.raise_for_status()
        if verbose:
            print("Model loaded successfully.")
        time.sleep(5)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error loading model: {e}", file=sys.stderr)
        return False

def list_available_models(api_base_url):
    """Gets a list of all available models from the API."""
    try:
        response = requests.get(f"{api_base_url}/internal/model/list")
        response.raise_for_status()
        # The response is expected to be a JSON object with a 'model_names' key
        return response.json().get('model_names', [])
    except requests.exceptions.RequestException as e:
        print(f"Error getting available models: {e}", file=sys.stderr)
        return None # Return None to indicate failure to get the list

# --- Retry Logic Constants ---
MAX_RETRIES = 5
BACKOFF_FACTOR = 2
MAX_BACKOFF_SECONDS = 8

def translate_text(text, model_name, api_base_url):
    """Translates a single piece of text with retries."""
    prompt = f"Translate the following segment into English, without additional explanation.\n\n{text}"
    payload = {
        "prompt": prompt, "model": model_name, "max_tokens": 2048,
        "temperature": 0.7, "top_k": 20, "top_p": 0.6, "repetition_penalty": 1.05,
    }
    headers = {"Content-Type": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(f"{api_base_url}/completions", json=payload, headers=headers, timeout=60)
            response.raise_for_status()

            data = response.json()
            translated_text = data.get("choices", [{}])[0].get("text", "").strip()
            return translated_text if translated_text else text

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                sleep_time = BACKOFF_FACTOR ** attempt
                if sleep_time > MAX_BACKOFF_SECONDS:
                    raise TimeoutError(f"API backoff time ({sleep_time}s) exceeded maximum ({MAX_BACKOFF_SECONDS}s).")

                print(f"\nAPI request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {sleep_time}s...", file=sys.stderr)
                time.sleep(sleep_time)
            else:
                # On the last attempt, re-raise the exception to be handled by the main loop
                raise e
    return text

def count_text_nodes(data):
    """Recursively counts the number of text nodes that need translation."""
    count = 0
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str) and not value.startswith("jp_text:::"):
                count += 1
            else:
                count += count_text_nodes(value)
    elif isinstance(data, list):
        for item in data:
            count += count_text_nodes(item)
    return count

def process_data(data, model_name, api_base_url, pbar, verbose=False, checkpoint_path=None, checkpoint_freq=10):
    """Recursively traverses a data structure to find and translate text."""
    state = {'count': 0}

    def _save_checkpoint(full_data):
        if checkpoint_path:
            if verbose:
                pbar.write(f"--- Saving checkpoint to {checkpoint_path} ---")
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, ensure_ascii=False, indent=4)

    def _recursive_process(sub_data, full_data_root):
        if isinstance(sub_data, dict):
            for key, value in sub_data.items():
                if key == "#text" and isinstance(value, str) and not value.startswith("jp_text:::"):
                    original_text = value
                    if verbose:
                        pbar.write(f"Translating: {original_text}")

                    translated_text = translate_text(original_text, model_name, api_base_url)
                    sub_data[key] = f"jp_text:::{translated_text}"
                    pbar.update(1)

                    if verbose:
                        pbar.write(f"Translated: {translated_text}")

                    state['count'] += 1
                    if checkpoint_freq > 0 and state['count'] % checkpoint_freq == 0:
                        _save_checkpoint(full_data_root)
                else:
                    _recursive_process(value, full_data_root)
        elif isinstance(sub_data, list):
            for item in sub_data:
                _recursive_process(item, full_data_root)

    def _cleanup_markers(sub_data):
        if isinstance(sub_data, dict):
            for key, value in sub_data.items():
                if key == "#text" and isinstance(value, str) and value.startswith("jp_text:::"):
                    sub_data[key] = value.replace("jp_text:::", "", 1)
                else:
                    _cleanup_markers(value)
        elif isinstance(sub_data, list):
            for item in sub_data:
                _cleanup_markers(item)

    _recursive_process(data, data)
    _cleanup_markers(data)
    if checkpoint_freq > 0:
        _save_checkpoint(data)

def translate_file(input_path, model_name, api_base_url=DEFAULT_API_BASE_URL, checkpoint_freq=10, verbose=False, quiet=False):
    """Main function to translate a file, with all user-friendly features."""
    checkpoint_path = f"{input_path}.checkpoint.json"
    data_structure = None

    try:
        if os.path.exists(checkpoint_path):
            if not quiet:
                print(f"Resuming from checkpoint: {checkpoint_path}")
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data_structure = json.load(f)
        else:
            if verbose:
                print("No checkpoint found. Starting new translation.")
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()
            data_structure = parser.deserialize(content)

        # Step 2: Check and load model
        current_model = get_current_model(api_base_url)
        if current_model != model_name:
            if not quiet:
                print(f"Current model is '{current_model}'. Requested model is '{model_name}'.")

            # Validate that the requested model exists on the server
            available_models = list_available_models(api_base_url)
            if available_models is not None and model_name not in available_models:
                raise ValueError(f"Model '{model_name}' not found on server. Available models: {', '.join(available_models)}")

            if not load_model(model_name, api_base_url, verbose):
                raise Exception(f"Failed to load model '{model_name}'.")
        elif verbose:
            print(f"Model '{model_name}' is already loaded.")

        nodes_to_translate = count_text_nodes(data_structure)
        if nodes_to_translate == 0:
            if not quiet:
                print("No text to translate.")
            return parser.serialize(data_structure)

        with tqdm(total=nodes_to_translate, desc="Translating", unit="node", disable=quiet) as pbar:
            process_data(data_structure, model_name, api_base_url, pbar, verbose, checkpoint_path, checkpoint_freq)

        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            if verbose:
                print(f"Checkpoint file {checkpoint_path} removed.")

        return parser.serialize(data_structure)

    except FileNotFoundError:
        raise
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        if checkpoint_path and os.path.exists(checkpoint_path):
             print(f"Work has been saved to checkpoint file: {checkpoint_path}", file=sys.stderr)
        raise
