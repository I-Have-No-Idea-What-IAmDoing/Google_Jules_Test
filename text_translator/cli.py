import argparse
import os
import sys
from translator_lib.core import translate_file, DEFAULT_API_BASE_URL

def main():
    parser = argparse.ArgumentParser(
        description="Translate text in a custom XML-like file from Japanese to English.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Core arguments
    parser.add_argument("input_file", help="Path to the input file to be translated.")
    parser.add_argument("--model", required=True, help="Name of the main translation model to use (or the refiner model in --refine mode).")
    parser.add_argument("--output_file", help="Optional. Path to save the translated output file.")

    # Refinement mode arguments
    refine_group = parser.add_argument_group('Refinement Mode')
    refine_group.add_argument("--refine", action="store_true", help="Enable refinement mode, which generates multiple drafts and refines them.")
    refine_group.add_argument("--draft-model", help="The model to use for generating draft translations. Required if --refine is used.")

    # Configuration arguments
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument("--api-base-url", default=None, help="Base URL of the oobabooga API.\n(Default: checks OOBABOOGA_API_BASE_URL env var, then http://127.0.0.1:5000/v1)")

    # Verbosity arguments
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="Enable detailed output.")
    verbosity_group.add_argument("--quiet", action="store_true", help="Suppress all informational output.")

    args = parser.parse_args()

    # Validate arguments
    if args.refine and not args.draft_model:
        parser.error("--draft-model is required when using --refine.")

    # Determine API base URL
    api_url = args.api_base_url or os.environ.get("OOBABOOGA_API_BASE_URL") or DEFAULT_API_BASE_URL

    try:
        if not args.quiet:
            print(f"Starting translation for '{args.input_file}'...")
            if args.refine:
                print(f"Using refinement mode with draft model '{args.draft_model}' and refiner '{args.model}'.")

        # Prepare arguments for the core library function
        core_args = {
            "input_path": args.input_file,
            "model_name": args.model,
            "api_base_url": api_url,
            "verbose": args.verbose,
            "quiet": args.quiet,
            "output_file": args.output_file,
            "refine_mode": args.refine,
            "draft_model": args.draft_model
        }

        translated_content = translate_file(**core_args)

        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            if not args.quiet:
                print(f"\nTranslation complete. Output saved to {args.output_file}")
        else:
            if args.quiet:
                print(translated_content)
            else:
                print("\n--- Translated Content ---")
                print(translated_content)
                print("--------------------------")

    except Exception as e:
        print(f"A critical error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
