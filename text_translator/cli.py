import argparse
import os
import sys
from typing import Optional, Any
from translator_lib.core import translate_file, DEFAULT_API_BASE_URL, check_server_status

def process_single_file(input_file: str, output_file: Optional[str], args: argparse.Namespace, api_url: str, glossary_text: Optional[str]) -> None:
    """Processes a single file."""
    try:
        if not args.quiet:
            print(f"Starting translation for '{input_file}'...")
            if args.refine:
                print(f"Using refinement mode with draft model '{args.draft_model}' and refiner '{args.model}'.")

        core_args = {
            "input_path": input_file,
            "model_name": args.model,
            "api_base_url": api_url,
            "verbose": args.verbose,
            "quiet": args.quiet,
            "debug": args.debug,
            "output_file": output_file,
            "refine_mode": args.refine,
            "draft_model": args.draft_model,
            "num_drafts": args.num_drafts,
            "glossary_text": glossary_text,
            "glossary_for": args.glossary_for,
            "reasoning_for": args.reasoning_for,
            "line_by_line": args.line_by_line,
            "overwrite": args.overwrite
        }

        translated_content = translate_file(**core_args)

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            if not args.quiet:
                print(f"\nTranslation complete. Output saved to {output_file}")
        else:
            if args.quiet:
                print(translated_content)
            else:
                print("\n--- Translated Content ---")
                print(translated_content)
                print("--------------------------")

    except Exception as e:
        print(f"Error processing file {input_file}: {e}", file=sys.stderr)

def process_directory(args: argparse.Namespace, api_url: str, glossary_text: Optional[str]) -> None:
    """Processes all files in a directory."""
    input_dir = args.input_path
    output_dir = args.output

    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = f"{os.path.basename(input_dir)}_translated"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

    if args.recursive:
        for root, _, files in os.walk(input_dir):
            for file in files:
                input_file = os.path.join(root, file)
                relative_path = os.path.relpath(input_file, input_dir)
                output_file = os.path.join(output_dir, relative_path)
                process_single_file(input_file, output_file, args, api_url, glossary_text)
    else:
        for item in os.listdir(input_dir):
            input_file = os.path.join(input_dir, item)
            if os.path.isfile(input_file):
                output_file = os.path.join(output_dir, item)
                process_single_file(input_file, output_file, args, api_url, glossary_text)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate text in files from Japanese to English. Can process a single file or all files in a directory.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Core arguments
    parser.add_argument("input_path", help="Path to the input file or directory to be translated.")
    parser.add_argument("--model", required=True, help="Name of the main translation model to use (or the refiner model in --refine mode).")
    parser.add_argument("--output", help="Optional. Path to the output file or directory. If not provided, a default will be used.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output file if it already exists.")

    # Directory processing options
    dir_group = parser.add_argument_group('Directory Options')
    dir_group.add_argument('--recursive', dest='recursive', action='store_true', help="Process directories recursively. (Default)")
    dir_group.add_argument('--no-recursive', dest='recursive', action='store_false', help="Disable recursive processing.")
    parser.set_defaults(recursive=True)

    # Refinement mode arguments
    refine_group = parser.add_argument_group('Refinement Mode')
    refine_group.add_argument("--refine", action="store_true", help="Enable refinement mode, which generates multiple drafts and refines them.")
    refine_group.add_argument("--draft-model", help="The model to use for generating draft translations. Required if --refine is used.")
    refine_group.add_argument("--num-drafts", type=int, default=6, help="Number of drafts to generate in refinement mode. (Default: 6)")

    # Configuration arguments
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument("--api-base-url", default=None, help="Base URL of the oobabooga API.\n(Default: checks OOBABOOGA_API_BASE_URL env var, then http://127.0.0.1:5000/v1)")
    glossary_group = config_group.add_mutually_exclusive_group()
    glossary_group.add_argument("--glossary-file", help="Path to a glossary file to provide extra context for translation.")
    glossary_group.add_argument("--glossary-text", help="A string containing glossary terms to provide extra context for translation.")
    config_group.add_argument("--glossary-for", choices=['draft', 'refine', 'all'], default='all', help="Model to apply the glossary to. (Default: all)")
    config_group.add_argument("--reasoning-for", choices=['draft', 'refine', 'main', 'all'], default=None, help="Enable reasoning for specific models (main, draft, refine, or all).")
    config_group.add_argument("--line-by-line", action="store_true", help="Translate each line individually instead of the whole text block. May reduce quality.")
    config_group.add_argument(
        "--debug",
        nargs='?',
        type=int,
        const=3,
        default=0,
        help="Enable debug output. Optionally provide a level (1-3). "
             "Defaults to 3 if no level is specified."
    )

    # Verbosity arguments
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="Enable detailed output.")
    verbosity_group.add_argument("--quiet", action="store_true", help="Suppress all informational output.")

    args = parser.parse_args()

    # --- Argument Validation ---
    if not os.path.exists(args.input_path):
        parser.error(f"Input path does not exist: {args.input_path}")
    if args.refine and not args.draft_model:
        parser.error("--draft-model is required when using --refine.")

    # Determine API base URL
    api_url = args.api_base_url or os.environ.get("OOBABOOGA_API_BASE_URL") or DEFAULT_API_BASE_URL

    # Check server status before proceeding
    if not args.quiet:
        print("Checking server status...")
    check_server_status(api_url, args.debug)
    if not args.quiet:
        print("Server is active.")

    # --- Glossary Processing ---
    glossary_text = args.glossary_text
    if args.glossary_file:
        if not os.path.exists(args.glossary_file):
            parser.error(f"Glossary file not found: {args.glossary_file}")
        with open(args.glossary_file, 'r', encoding='utf-8') as f:
            glossary_text = f.read()

    # --- Path Processing ---
    if os.path.isdir(args.input_path):
        if not args.quiet:
            print(f"Input is a directory. Translating all files in '{args.input_path}'...")
        process_directory(args, api_url, glossary_text)
    elif os.path.isfile(args.input_path):
        output_path = args.output
        if output_path and os.path.isdir(output_path):
            output_path = os.path.join(output_path, os.path.basename(args.input_path))
        process_single_file(args.input_path, output_path, args, api_url, glossary_text)
    else:
        parser.error(f"Input path is not a valid file or directory: {args.input_path}")

if __name__ == "__main__":
    main()
