import argparse
import os
import sys
from translator_lib.core import translate_file, DEFAULT_API_BASE_URL

def main():
    """
    Main function for the command-line interface.
    """
    parser = argparse.ArgumentParser(
        description="Translate text in a custom XML-like file from Japanese to English.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("input_file", help="Path to the input file to be translated.")
    parser.add_argument("--model", required=True, help="Name of the translation model to use.")
    parser.add_argument("--output_file", help="Optional. Path to save the translated output file.\nIf not provided, the output is printed to the console.")

    # User-friendliness arguments
    parser.add_argument("--api-base-url", default=None, help="Base URL of the oobabooga API.\n(Default: checks OOBABOOGA_API_BASE_URL env var, then http://127.0.0.1:5000/v1)")
    parser.add_argument("--checkpoint-frequency", type=int, default=10, help="How often to save a checkpoint (number of translations).\nSet to 0 to disable. (Default: 10)")

    # Verbosity arguments
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verbose", action="store_true", help="Enable detailed output during translation.")
    group.add_argument("--quiet", action="store_true", help="Suppress all informational output except for the final result.")

    args = parser.parse_args()

    # Determine API base URL: CLI > Environment Variable > Default
    api_url = args.api_base_url or os.environ.get("OOBABOOGA_API_BASE_URL") or DEFAULT_API_BASE_URL

    try:
        if not args.quiet:
            print(f"Starting translation for '{args.input_file}'...")
            print(f"Using API base URL: {api_url}")

        translated_content = translate_file(
            input_path=args.input_file,
            model_name=args.model,
            api_base_url=api_url,
            checkpoint_freq=args.checkpoint_frequency,
            verbose=args.verbose,
            quiet=args.quiet
        )

        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            if not args.quiet:
                print(f"\nTranslation complete. Output saved to {args.output_file}")
        else:
            # If quiet, just print the content. Otherwise, add headers.
            if args.quiet:
                print(translated_content)
            else:
                print("\n--- Translated Content ---")
                print(translated_content)
                print("--------------------------")

    except FileNotFoundError:
        print(f"Error: Input file not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Core library now raises exceptions on failure
        print(f"A critical error occurred.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
