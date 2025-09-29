import os
import sys
from typing import Any, Dict, List
from tqdm import tqdm

from custom_xml_parser import parser

from .options import TranslationOptions
from .api_client import ensure_model_loaded
from .translation import get_translation, _get_refined_translation
from .data_processor import collect_text_nodes, cleanup_markers
from .exceptions import TranslatorError


def _get_translation_for_text(text: str, options: TranslationOptions, is_line_by_line: bool) -> str:
    """
    Performs translation for a given string of text based on the specified options.

    This helper function abstracts the logic for choosing between direct and
    refinement mode translation. It centralizes the call to either `get_translation`
    or `_get_refined_translation`, reducing code duplication in the main loop.

    Args:
        text: The text content to translate.
        options: The `TranslationOptions` object containing all settings.
        is_line_by_line: A boolean indicating if this is part of a line-by-line
                         translation job, which can affect parameter passing.

    Returns:
        The translated text as a string.
    """
    if options.refine_mode:
        return _get_refined_translation(
            original_text=text,
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
            line_by_line=is_line_by_line
        )
    else:  # Direct mode
        direct_glossary = options.glossary_text if options.glossary_for in [None, 'all', 'main'] else None
        return get_translation(
            text=text,
            model_name=options.model_name,
            api_base_url=options.api_base_url,
            model_config=options.model_config,
            glossary_text=direct_glossary,
            debug=options.debug,
            use_reasoning=(options.reasoning_for in ['main', 'all']),
            line_by_line=is_line_by_line
        )


def translate_file(options: TranslationOptions) -> str:
    """
    Orchestrates the translation process for a single file.

    This function reads and deserializes the input file, finds all text nodes,
    translates them according to the provided options, and then serializes the
    modified data structure back into a string. It handles both full-content
    and line-by-line translation modes efficiently by delegating the core
    translation logic to a helper function.

    Args:
        options: A `TranslationOptions` object containing all settings for the job.

    Returns:
        A string containing the file's content with text nodes translated.
    """
    if options.output_path and os.path.exists(options.output_path) and not options.overwrite:
        if not options.quiet:
            print(f"Output file {options.output_path} already exists. Skipping.")
        return ""

    with open(options.input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    data_structure = parser.deserialize(content)

    nodes_to_translate: List[Dict[str, Any]] = []
    collect_text_nodes(data_structure, nodes_to_translate)

    if not nodes_to_translate:
        if not options.quiet:
            print("No text to translate.")
        return parser.serialize(data_structure)

    # Pre-load the main model for direct mode to avoid reloading in the loop.
    if not options.refine_mode:
        ensure_model_loaded(
            options.model_name,
            options.api_base_url,
            model_config=options.model_config,
            verbose=options.verbose,
            debug=options.debug
        )

    # --- Main Translation Loop ---
    with tqdm(total=len(nodes_to_translate), desc="Translating", unit="node", disable=options.quiet) as pbar:
        for i, node in enumerate(nodes_to_translate):
            original_text = node['#text']
            translated_text = ""

            try:
                if options.line_by_line:
                    lines = original_text.splitlines(True)  # Keep endings
                    translated_lines = [
                        _get_translation_for_text(line, options, is_line_by_line=True) if line.strip() else line
                        for line in lines
                    ]
                    translated_text = "".join(translated_lines)
                else:  # Translate entire node at once
                    translated_text = _get_translation_for_text(original_text, options, is_line_by_line=False)

            except TranslatorError as e:
                pbar.write(f"Warning: Could not translate node {i+1} due to an error: {e}", file=sys.stderr)
                pbar.write(f"Skipping translation for this node. Original text will be kept.", file=sys.stderr)
                translated_text = ""  # Ensure we fall back to original

            # Use a temporary marker to distinguish translated from original empty text.
            # If translation returns an empty string, we keep the original.
            node['#text'] = f"jp_text:::{translated_text}" if translated_text else original_text
            pbar.update(1)

    cleanup_markers(data_structure)
    return parser.serialize(data_structure)