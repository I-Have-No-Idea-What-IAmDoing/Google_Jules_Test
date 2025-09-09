import argparse
import os
import shutil
import sys
from .parser import deserialize, serialize, merge

def process_directories(input_dir, output_dir, no_overwrite=False, quiet=False, dry_run=False):
    """
    Processes the directories, merging or copying .txt files.
    """
    # Helper for conditional printing
    def log(message):
        if not quiet:
            print(message)

    for root, dirs, files in os.walk(input_dir):
        # Create corresponding directories in the output
        relative_path = os.path.relpath(root, input_dir)
        output_root = os.path.join(output_dir, relative_path)
        if not os.path.exists(output_root):
            log(f"Creating directory '{output_root}'")
            if not dry_run:
                os.makedirs(output_root)

        for file in files:
            if file.endswith(".txt"):
                input_path = os.path.join(root, file)
                output_path = os.path.join(output_root, file)

                if os.path.exists(output_path):
                    if no_overwrite:
                        log(f"Skipping existing file '{output_path}'")
                        continue

                    log(f"Merging '{input_path}' into '{output_path}'...")
                    if not dry_run:
                        try:
                            with open(input_path, 'r', encoding='utf-8') as f:
                                input_content = f.read()
                            with open(output_path, 'r', encoding='utf-8') as f:
                                output_content = f.read()

                            input_data = deserialize(input_content)
                            output_data = deserialize(output_content)

                            merged_data = merge(input_data, output_data)
                            serialized_data = serialize(merged_data)

                            with open(output_path, 'w', encoding='utf-8') as f:
                                f.write(serialized_data)
                        except Exception as e:
                            print(f"Error merging file {file}: {e}", file=sys.stderr)
                else:
                    log(f"Copying '{input_path}' to '{output_path}'...")
                    if not dry_run:
                        shutil.copy2(input_path, output_path)

def main():
    parser = argparse.ArgumentParser(description="Recursively copy and merge custom text files.")
    parser.add_argument("input_dir", help="The input directory.")
    parser.add_argument("output_dir", help="The output directory.")
    parser.add_argument("-n", "--no-overwrite", action="store_true", help="Do not overwrite existing files in the output directory.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress informational messages.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually modifying files.")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory not found at '{args.input_dir}'", file=sys.stderr)
        sys.exit(1)

    process_directories(args.input_dir, args.output_dir, args.no_overwrite, args.quiet, args.dry_run)
    print("\nProcessing complete.")

if __name__ == "__main__":
    main()
