import os
from typing import Any, Dict, List
from tqdm import tqdm

# Adjust the import path to correctly locate the custom_xml_parser module.
# This assumes that the script is run from a context where the project's root directory is in the Python path.
from custom_xml_parser import parser

from .options import TranslationOptions
from .api_client import ensure_model_loaded
from .translation import get_translation, _get_refined_translation
from .data_processor import collect_text_nodes, cleanup_markers

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
                        api_base_url=options.api_base_url,
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
