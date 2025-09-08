import argparse
import os
import shutil
from .parser import deserialize, serialize, merge

def process_directories(input_dir, output_dir):
    """
    Processes the directories, merging or copying .txt files.
    """
    for root, dirs, files in os.walk(input_dir):
        # Create corresponding directories in the output
        relative_path = os.path.relpath(root, input_dir)
        output_root = os.path.join(output_dir, relative_path)
        if not os.path.exists(output_root):
            os.makedirs(output_root)

        for file in files:
            if file.endswith(".txt"):
                input_path = os.path.join(root, file)
                output_path = os.path.join(output_root, file)

                if os.path.exists(output_path):
                    # Merge logic
                    print(f"Merging '{input_path}' into '{output_path}'...")
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
                        print(f"Error merging file {file}: {e}")
                else:
                    # Copy logic
                    print(f"Copying '{input_path}' to '{output_path}'...")
                    shutil.copy2(input_path, output_path)

def main():
    parser = argparse.ArgumentParser(description="Recursively copy and merge custom text files.")
    parser.add_argument("--input-dir", required=True, help="The input directory.")
    parser.add_argument("--output-dir", required=True, help="The output directory.")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory not found at '{args.input_dir}'")
        return

    process_directories(args.input_dir, args.output_dir)
    print("\nProcessing complete.")

if __name__ == "__main__":
    main()
