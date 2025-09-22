import argparse
import os
import sys
import argparse
from typing import Optional
from translator_lib.core import translate_file, DEFAULT_API_BASE_URL, check_server_status

def process_single_file(input_file: str, output_file: Optional[str], options: 'TranslationOptions') -> None:
    """Processes a single file."""
    try:
        if not options.quiet:
            print(f"Starting translation for '{input_file}'...")
            if options.refine_mode:
                print(f"Using refinement mode with draft model '{options.draft_model}' and refiner '{options.model_name}'.")

        # Update options for the single file being processed
        options.input_path = input_file
        options.output_path = output_file

        translated_content = translate_file(options)

        if output_file:
            # Ensure the output directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            if not options.quiet:
                print(f"\nTranslation complete. Output saved to {output_file}")
        else:
            # Print to stdout if no output file is specified
            if options.quiet:
                print(translated_content)
            else:
                print("\n--- Translated Content ---")
                print(translated_content)
                print("--------------------------")

    except Exception as e:
        print(f"Error processing file {input_file}: {e}", file=sys.stderr)

def process_directory(args: argparse.Namespace, options: 'TranslationOptions') -> None:
    """Processes all files in a directory."""
    input_dir = args.input_path
    output_dir = args.output or f"{os.path.basename(input_dir)}_translated"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if args.recursive:
        for root, _, files in os.walk(input_dir):
            for file in files:
                input_file = os.path.join(root, file)
                relative_path = os.path.relpath(input_file, input_dir)
                output_file = os.path.join(output_dir, relative_path)
                process_single_file(input_file, output_file, options)
    else:
        for item in os.listdir(input_dir):
            input_file = os.path.join(input_dir, item)
            if os.path.isfile(input_file):
                output_file = os.path.join(output_dir, item)
                process_single_file(input_file, output_file, options)

from translator_lib.options import TranslationOptions
__version__ = "1.1.0"

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate text in files from Japanese to English.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Core Arguments ---
    parser.add_argument("input_path", help="Path to the input file or directory.")
    parser.add_argument("--model", required=True, help="Main translation model name.")
    parser.add_argument("--output", help="Output file or directory path.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    # --- Directory Processing ---
    dir_group = parser.add_argument_group('Directory Options')
    dir_group.add_argument('--recursive', dest='recursive', action='store_true', help="Process directories recursively (default).")
    dir_group.add_argument('--no-recursive', dest='recursive', action='store_false', help="Disable recursive processing.")
    parser.set_defaults(recursive=True)

    # --- Refinement Mode ---
    refine_group = parser.add_argument_group('Refinement Mode')
    refine_group.add_argument("--refine", action="store_true", help="Enable refinement mode.")
    refine_group.add_argument("--draft-model", help="Model for draft translations (required for --refine).")
    refine_group.add_argument("--num-drafts", type=int, default=6, help="Number of drafts (default: 6).")

    # --- Configuration ---
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument("--api-base-url", default=None, help="API base URL (env: OOBABOOGA_API_BASE_URL).")
    glossary_group = config_group.add_mutually_exclusive_group()
    glossary_group.add_argument("--glossary-file", help="Path to glossary file.")
    glossary_group.add_argument("--glossary-text", help="Glossary content as a string.")
    config_group.add_argument("--glossary-for", choices=['draft', 'refine', 'all'], default='all', help="Apply glossary to: draft, refine, or all (default).")
    config_group.add_argument("--reasoning-for", choices=['draft', 'refine', 'main', 'all'], default=None, help="Enable reasoning for specific models.")
    config_group.add_argument("--line-by-line", action="store_true", help="Translate line-by-line (may reduce quality).")
    config_group.add_argument("--debug", action="store_true", help="Enable debug output.")

    # --- Verbosity ---
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="Enable detailed output.")
    verbosity_group.add_argument("--quiet", action="store_true", help="Suppress informational output.")

    args = parser.parse_args()

    # --- Argument Validation ---
    if not os.path.exists(args.input_path):
        parser.error(f"Input path does not exist: {args.input_path}")
    if args.refine and not args.draft_model:
        parser.error("--draft-model is required when using --refine.")
    if args.glossary_file and not os.path.exists(args.glossary_file):
        parser.error(f"Glossary file not found: {args.glossary_file}")

    # --- Glossary Processing ---
    glossary_text = args.glossary_text
    if args.glossary_file:
        with open(args.glossary_file, 'r', encoding='utf-8') as f:
            glossary_text = f.read()

    # --- API and Options Setup ---
    api_url = args.api_base_url or os.environ.get("OOBABOOGA_API_BASE_URL") or DEFAULT_API_BASE_URL
    if not args.quiet:
        print("Checking server status...")
    check_server_status(api_url, args.debug)
    if not args.quiet:
        print("Server is active.")

    options = TranslationOptions(
        input_path=args.input_path,
        model_name=args.model,
        output_path=args.output,
        api_base_url=api_url,
        glossary_text=glossary_text,
        glossary_for=args.glossary_for,
        refine_mode=args.refine,
        draft_model=args.draft_model,
        num_drafts=args.num_drafts,
        reasoning_for=args.reasoning_for,
        line_by_line=args.line_by_line,
        overwrite=args.overwrite,
        verbose=args.verbose,
        quiet=args.quiet,
        debug=args.debug
    )

    # --- Path Processing ---
    if os.path.isdir(args.input_path):
        if not args.quiet:
            print(f"Input is a directory. Translating all files in '{args.input_path}'...")
        process_directory(args, options)
    elif os.path.isfile(args.input_path):
        process_single_file(args.input_path, args.output, options)
    else:
        parser.error(f"Input path is not a valid file or directory: {args.input_path}")

if __name__ == "__main__":
    main()
