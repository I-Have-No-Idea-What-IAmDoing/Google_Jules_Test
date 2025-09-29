import argparse
import os
import sys
from typing import Optional, Tuple, Dict, Any

if __name__ == "__main__" and not __package__:
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import text_translator
    __package__ = "text_translator"

from .translator_lib.core import translate_file
from .translator_lib.options import TranslationOptions
from .translator_lib import model_loader
from .translator_lib.api_client import check_server_status, DEFAULT_API_BASE_URL
from .translator_lib.exceptions import TranslatorError
from . import color_console as cc

__version__ = "1.1.0"

def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser):
    """Performs validation checks on parsed command-line arguments."""
    if not os.path.exists(args.input_path):
        parser.error(f"Input path does not exist: {args.input_path}")
    if args.refine and not args.draft_model:
        parser.error("--draft-model is required when using --refine.")
    if args.glossary_file and not os.path.exists(args.glossary_file):
        parser.error(f"Glossary file not found: {args.glossary_file}")
    if args.glossary_for and not (args.glossary_file or args.glossary_text):
        parser.error("--glossary-for requires a glossary to be provided via --glossary-file or --glossary-text.")

def _load_configs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads model configurations from the specified JSON file."""
    try:
        all_model_configs = model_loader.load_model_configs(args.models_file)
        main_model_config = model_loader.get_model_config(args.model, all_model_configs)
        draft_model_config = {}
        if args.draft_model:
            draft_model_config = model_loader.get_model_config(args.draft_model, all_model_configs)
        return main_model_config, draft_model_config
    except model_loader.ModelConfigError as e:
        parser.error(str(e))
    # This line is unreachable but satisfies type checkers
    return {}, {}


def _build_translation_options(args: argparse.Namespace, main_model_config: Dict[str, Any], draft_model_config: Dict[str, Any]) -> TranslationOptions:
    """Assembles the TranslationOptions object from arguments and configurations."""
    glossary_text = args.glossary_text
    if args.glossary_file:
        with open(args.glossary_file, 'r', encoding='utf-8') as f:
            glossary_text = f.read()

    api_url = args.api_base_url or os.environ.get("OOBABOOGA_API_BASE_URL") or DEFAULT_API_BASE_URL
    cc.print_info("Checking server status...", quiet=args.quiet)
    check_server_status(api_url, args.debug)
    cc.print_success("Server is active.", quiet=args.quiet)

    return TranslationOptions(
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

def process_single_file(input_file: str, output_file: Optional[str], options: 'TranslationOptions') -> None:
    """Handles the translation process for a single file."""
    try:
        cc.print_info(f"Starting translation for '{input_file}'...", quiet=options.quiet)
        if options.refine_mode:
            cc.print_info(f"Using refinement mode with draft model '{options.draft_model}' and refiner '{options.model_name}'.", quiet=options.quiet)

        options.input_path = input_file
        options.output_path = output_file

        translated_content = translate_file(options)

        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                # Defensive check: ensure the target directory path is not a file.
                if os.path.exists(output_dir) and not os.path.isdir(output_dir):
                    cc.print_error(f"Error: Cannot create directory '{output_dir}' because a file with the same name exists.")
                    return
                os.makedirs(output_dir, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            cc.print_success(f"\nTranslation complete. Output saved to {output_file}", quiet=options.quiet)
        else:
            cc.print_translation(translated_content, quiet=options.quiet)

    except Exception as e:
        cc.print_error(f"Error processing file {input_file}: {e}")

def process_directory(args: argparse.Namespace, options: 'TranslationOptions') -> None:
    """Handles the translation process for an entire directory."""
    input_dir = args.input_path
    output_dir_base = args.output or f"{os.path.basename(input_dir)}_translated"

    if not os.path.exists(output_dir_base):
        os.makedirs(output_dir_base, exist_ok=True)

    if args.recursive:
        for root, _, files in os.walk(input_dir):
            for file in files:
                input_file = os.path.join(root, file)
                relative_path = os.path.relpath(input_file, input_dir)
                output_file = os.path.join(output_dir_base, relative_path)

                # Bug fix: Check for file/directory name collision before processing.
                output_dir_of_file = os.path.dirname(output_file)
                if os.path.exists(output_dir_of_file) and not os.path.isdir(output_dir_of_file):
                    cc.print_error(f"Skipping '{input_file}': Cannot create output directory because a file named '{os.path.basename(output_dir_of_file)}' exists in the parent output directory.")
                    continue

                process_single_file(input_file, output_file, options)
    else:
        for item in os.listdir(input_dir):
            input_file = os.path.join(input_dir, item)
            if os.path.isfile(input_file):
                output_file = os.path.join(output_dir_base, item)
                process_single_file(input_file, output_file, options)

def main_logic(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Orchestrates the main application workflow after argument parsing."""
    _validate_args(args, parser)
    main_model_config, draft_model_config = _load_configs(args, parser)
    options = _build_translation_options(args, main_model_config, draft_model_config)

    if os.path.isdir(args.input_path):
        cc.print_info(f"Input is a directory. Translating all files in '{args.input_path}'...", quiet=args.quiet)
        process_directory(args, options)
    elif os.path.isfile(args.input_path):
        process_single_file(args.input_path, args.output, options)
    else:
        parser.error(f"Input path is not a valid file or directory: {args.input_path}")

def main() -> None:
    """Defines and executes the command-line interface for the translator."""
    parser = argparse.ArgumentParser(
        description="A command-line tool to translate text files from Japanese to English using a local LLM API.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example usage:\n"
               "  # Translate a single file\n"
               "  python -m text_translator.cli my_file.txt --model 'my-model-name' --output my_file.eng.txt\n\n"
               "  # Translate a whole directory in refinement mode\n"
               "  python -m text_translator.cli ./my_dir --model 'refiner-model' --refine --draft-model 'draft-model'"
    )
    
    # Argument groups
    core_group = parser.add_argument_group('Core Arguments')
    core_group.add_argument("input_path", help="Path to the input file or directory.")
    core_group.add_argument("--model", required=True, help="Main translation model name (must exist in models.json).")
    core_group.add_argument("--output", help="Output file or directory path.")
    core_group.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")
    core_group.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    dir_group = parser.add_argument_group('Directory Options')
    dir_group.add_argument('--recursive', dest='recursive', action='store_true', help="Process directories recursively (default).")
    dir_group.add_argument('--no-recursive', dest='recursive', action='store_false', help="Disable recursive processing.")
    parser.set_defaults(recursive=True)

    refine_group = parser.add_argument_group('Refinement Mode')
    refine_group.add_argument("--refine", action="store_true", help="Enable refinement mode.")
    refine_group.add_argument("--draft-model", help="Model for draft translations (required for --refine).")
    refine_group.add_argument("--num-drafts", type=int, default=6, help="Number of drafts (default: 6).")

    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument("--api-base-url", default=None, help="API base URL (env: OOBABOOGA_API_BASE_URL).")
    config_group.add_argument("--models-file", default=os.path.join(os.path.dirname(__file__), 'models.json'), help="Path to the models JSON configuration file.")

    glossary_group = config_group.add_mutually_exclusive_group()
    glossary_group.add_argument("--glossary-file", help="Path to a text file containing a glossary for context.")
    glossary_group.add_argument("--glossary-text", help="A string containing glossary terms.")
    config_group.add_argument("--glossary-for", choices=['draft', 'refine', 'all'], default=None, help="Apply glossary to: 'draft' model, 'refine' model, or 'all'.")
    config_group.add_argument("--reasoning-for", choices=['draft', 'refine', 'main', 'all'], default=None, help="Enable step-by-step reasoning for specific model types.")
    config_group.add_argument("--line-by-line", action="store_true", help="Process files line by line instead of translating the whole content at once.")

    info_group = parser.add_argument_group('General')
    verbosity_group = info_group.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    verbosity_group.add_argument("--quiet", "-q", action="store_true", help="Suppress all informational output.")
    info_group.add_argument("--debug", action="store_true", help="Enable extensive debug output.")

    args = parser.parse_args()

    try:
        main_logic(args, parser)
    except TranslatorError as e:
        cc.print_error(f"\n---FATAL ERROR---\n{e}\n-------------------\n")
        sys.exit(1)
    except Exception as e:
        cc.print_error(f"\n---UNEXPECTED FATAL ERROR---\n{e}\n-------------------\n")
        sys.exit(1)

if __name__ == "__main__":
    main()