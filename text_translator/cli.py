import argparse
import os
import sys
from typing import Optional
from translator_lib.core import translate_file, DEFAULT_API_BASE_URL, check_server_status
from translator_lib.options import TranslationOptions
from translator_lib import model_loader

__version__ = "1.1.0"

def process_single_file(input_file: str, output_file: Optional[str], options: 'TranslationOptions') -> None:
    """
    Manages the translation process for a single file.

    Args:
        input_file: The path to the input file.
        output_file: The path to the output file (or None to print to stdout).
        options: The TranslationOptions object with all settings.
    """
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
    """
    Manages the translation process for an entire directory.

    Args:
        args: The parsed command-line arguments.
        options: The TranslationOptions object with all settings.
    """
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

def main() -> None:
    """Sets up the argument parser and orchestrates the translation process based on user input."""
    parser = argparse.ArgumentParser(
        description="A command-line tool to translate text files from Japanese to English using a local LLM API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example usage:\n"
               "  # Translate a single file\n"
               "  python -m text_translator.cli my_file.txt --model 'my-model-name' --output my_file.eng.txt\n\n"
               "  # Translate a whole directory in refinement mode\n"
               "  python -m text_translator.cli ./my_dir --model 'refiner-model' --refine --draft-model 'draft-model'"
    )

    # --- Core I/O Arguments ---
    io_group = parser.add_argument_group('Input/Output')
    io_group.add_argument("input_path", help="Path to the input file or directory.")
    io_group.add_argument("--output", "-o", help="Path for the output file or directory. If not provided, prints to standard output.")
    dir_processing_group = io_group.add_mutually_exclusive_group()
    dir_processing_group.add_argument('--recursive', dest='recursive', action='store_true', help="Process directories recursively (default).")
    dir_processing_group.add_argument('--no-recursive', dest='recursive', action='store_false', help="Disable recursive directory processing.")
    io_group.add_argument("--overwrite", action="store_true", help="Allow overwriting of existing output files.")
    parser.set_defaults(recursive=True)

    # --- Model & Translation Arguments ---
    model_group = parser.add_argument_group('Model and Translation Settings')
    model_group.add_argument("--model", required=True, help="Name of the main model to use (must exist in models.json).")
    model_group.add_argument("--refine", action="store_true", help="Enable refinement mode, where drafts are generated and then refined.")
    model_group.add_argument("--draft-model", help="Name of the model for generating drafts (required for --refine).")
    model_group.add_argument("--num-drafts", type=int, default=6, help="Number of drafts to generate in refinement mode (default: 6).")
    model_group.add_argument("--line-by-line", action="store_true", help="Translate file line-by-line. May reduce quality but useful for simple files.")

    # --- Advanced Configuration ---
    config_group = parser.add_argument_group('Advanced Configuration')
    config_group.add_argument("--api-base-url", default=None, help="Base URL for the API. Overrides OOBABOOGA_API_BASE_URL env var.")
    config_group.add_argument("--models-file", default=os.path.join(os.path.dirname(__file__), 'models.json'), help="Path to the models JSON configuration file.")
    glossary_group = config_group.add_mutually_exclusive_group()
    glossary_group.add_argument("--glossary-file", help="Path to a text file containing a glossary for context.")
    glossary_group.add_argument("--glossary-text", help="A string containing glossary terms.")
    config_group.add_argument("--glossary-for", choices=['draft', 'refine', 'all'], default='all', help="Apply glossary to: 'draft' model, 'refine' model, or 'all' (default).")
    config_group.add_argument("--reasoning-for", choices=['draft', 'refine', 'main', 'all'], default=None, help="Enable step-by-step reasoning for specific model types.")

    # --- General & Info ---
    info_group = parser.add_argument_group('General')
    verbosity_group = info_group.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="Enable verbose output, showing model loading and other details.")
    verbosity_group.add_argument("--quiet", "-q", action="store_true", help="Suppress all informational output, printing only final results or errors.")
    info_group.add_argument("--debug", action="store_true", help="Enable extensive debug output for troubleshooting.")
    info_group.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    # --- Argument Validation ---
    if not os.path.exists(args.input_path):
        parser.error(f"Input path does not exist: {args.input_path}")
    if args.refine and not args.draft_model:
        parser.error("--draft-model is required when using --refine.")
    if args.glossary_file and not os.path.exists(args.glossary_file):
        parser.error(f"Glossary file not found: {args.glossary_file}")

    # --- Load Model Configurations ---
    try:
        all_model_configs = model_loader.load_model_configs(args.models_file)
        main_model_config = model_loader.get_model_config(args.model, all_model_configs)
        draft_model_config = {}
        if args.draft_model:
            draft_model_config = model_loader.get_model_config(args.draft_model, all_model_configs)
    except model_loader.ModelConfigError as e:
        parser.error(str(e))


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
        debug=args.debug,
        model_config=main_model_config,
        draft_model_config=draft_model_config,
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
