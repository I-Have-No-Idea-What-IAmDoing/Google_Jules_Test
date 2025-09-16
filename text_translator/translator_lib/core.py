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

# ... (API and model loading functions remain the same) ...
def _api_request(endpoint, payload, api_base_url, timeout=60):
    headers = {"Content-Type": "application/json"}
    # This function can be expanded with retry logic if needed
    response = requests.post(f"{api_base_url}/{endpoint}", json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()

def ensure_model_loaded(model_name, api_base_url, verbose=False):
    # ... (implementation is the same)
    pass

# --- New Batch-Oriented Workflow ---

def collect_text_nodes(data, nodes_list):
    """Recursively finds all text nodes and appends a reference to them to a list."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "#text" and isinstance(value, str):
                try:
                    # Skip english text and already processed text
                    if not value.startswith("jp_text:::") and detect(value) != 'en':
                        nodes_list.append(data)
                except LangDetectException:
                    nodes_list.append(data) # Translate if detection fails
            else:
                collect_text_nodes(value, nodes_list)
    elif isinstance(data, list):
        for item in data:
            collect_text_nodes(item, nodes_list)

def get_direct_translation_batch(nodes, model_name, api_base_url, pbar):
    """Translates a list of nodes directly."""
    ensure_model_loaded(model_name, api_base_url)
    for node in nodes:
        original_text = node['#text']
        payload = {"prompt": f"Translate the following segment into English:\n\n{original_text}", "model": model_name}
        response_data = _api_request("completions", payload, api_base_url)
        translated_text = response_data.get("choices", [{}])[0].get("text", "").strip()
        node['#text'] = f"jp_text:::{translated_text or original_text}"
        pbar.update(1)

def get_refinement_translation_batch(nodes, draft_model, refine_model, api_base_url, pbar):
    """Performs the draft-and-refine workflow in batches."""
    # 1. Generate all drafts first
    pbar.set_description("Generating Drafts")
    ensure_model_loaded(draft_model, api_base_url)
    drafts_data = []
    for node in nodes:
        original_text = node['#text']
        drafts = []
        for _ in range(6):
            payload = {"prompt": f"Translate the following segment into English:\n\n{original_text}", "model": draft_model, "temperature": random.uniform(0.6, 0.95)}
            response_data = _api_request("completions", payload, api_base_url)
            draft = response_data.get("choices", [{}])[0].get("text", "").strip()
            if draft: drafts.append(draft)
        drafts_data.append({'original': original_text, 'drafts': drafts, 'node_ref': node})
        pbar.update(0.5) # Update halfway for draft stage

    # 2. Refine all drafts
    pbar.set_description("Refining Translations")
    ensure_model_loaded(refine_model, api_base_url)
    for item in drafts_data:
        draft_list = "\n".join(f"{i+1}. ```{draft}```" for i, draft in enumerate(item['drafts']))
        prompt = (f"Analyze and refine the following English translations of a Japanese segment.\n"
                  f"Japanese segment:\n```{item['original']}```\n"
                  f"Translations:\n{draft_list}")
        payload = {"prompt": prompt, "model": refine_model, "temperature": 0.5}
        response_data = _api_request("completions", payload, api_base_url)
        refined_text = response_data.get("choices", [{}])[0].get("text", "").strip()
        item['node_ref']['#text'] = f"jp_text:::{refined_text or item['original']}"
        pbar.update(0.5) # Update the other half for refine stage

def cleanup_markers(data):
    """Recursively removes the 'jp_text:::' processing markers."""
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
    """Main function to translate a file using the batch-oriented workflow."""
    input_path = args['input_path']

    # Checkpointing is now simpler: just check if the output file exists.
    # A more robust solution would save a map of translated texts. For now, we skip if output exists.
    if args.get('output_file') and os.path.exists(args['output_file']):
        if not args.get('quiet'): print(f"Output file {args['output_file']} already exists. Skipping.")
        return

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
            get_refinement_translation_batch(
                nodes_to_translate, args['draft_model'], args['model_name'],
                args['api_base_url'], pbar
            )
        else:
            get_direct_translation_batch(
                nodes_to_translate, args['model_name'], args['api_base_url'], pbar
            )

    cleanup_markers(data_structure)
    return parser.serialize(data_structure)
