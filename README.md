# Monorepo for Python Utilities

This repository contains a collection of distinct Python projects, each serving a different purpose.

-   **`custom_xml_parser/`**: A robust parser for a custom, comment-preserving XML-like format.
-   **`text_translator/`**: A powerful command-line tool for translating text files using a local LLM API.

## 1. `custom_xml_parser`

This utility provides a parser and serializer for a custom hierarchical data format similar to XML. Its key feature is the ability to parse and re-serialize data while preserving comments, making it ideal for configuration files where human-readable documentation is important.

### Features

-   **Hierarchical Parsing**: Deserializes text into a nested Python dictionary.
-   **Comment Preservation**: Comments are not discarded and are re-inserted during serialization.
-   **CLI Tool**: Includes a command-line interface to copy and merge directory structures containing these files.

### Usage (as a library)

```python
from custom_xml_parser.parser import deserialize, serialize

# Deserialize a string to a dictionary
data_string = "[Action]<Tag>some text</Tag>[/Action]"
data_dict = deserialize(data_string)
# {'Action': {'Tag': {'#text': 'some text'}}}

# Serialize a dictionary back to a string
new_string = serialize(data_dict)
# [Action]
#   <Tag>
#       some text
#   </Tag>
# [/Action]
```

### Usage (CLI Tool)

The CLI tool can be used to merge directory structures. If a file exists in both the input and output directories, their contents will be intelligently merged.

```bash
python -m custom_xml_parser.cli ./input_directory ./output_directory
```

-   `--no-overwrite`: Prevents existing files from being modified.
-   `--quiet`: Suppresses informational messages.
-   `--dry-run`: Shows what would be done without making any changes.

---

## 2. `text_translator`

This is a sophisticated command-line tool designed to translate text files (specifically those using the `custom_xml_parser` format) from Japanese to English using a local Large Language Model (LLM) via an API, such as the one provided by the `oobabooga/text-generation-webui`.

### Features

-   **Refinement Mode**: A two-step process that first generates multiple "draft" translations and then uses a "refiner" model to produce a final, high-quality result.
-   **Configurable Models**: Define model parameters, prompts, and endpoints in a `models.json` file.
-   **Glossary Support**: Provide a glossary to guide the translation of specific terms.
-   **Directory Processing**: Translate entire directories of files, recursively or not.
-   **Line-by-Line Mode**: Process files one line at a time for more granular control.

### Setup

1.  **Install Dependencies**: The `text_translator` has external dependencies. Install them from the project's directory:
    ```bash
    pip install -r text_translator/requirements.txt
    ```

2.  **Run a Local LLM API**: This tool requires a running LLM server with an API compatible with the Oobabooga API extension. Ensure your server is running and the API is enabled. By default, the tool will look for it at `http://127.0.0.1:5000/v1`.

### Usage

The tool is run via its `cli.py` script. You must provide an input path and the name of the model to use.

**Translate a single file:**
```bash
python -m text_translator.cli "path/to/my_file.txt" --model "my-main-model" --output "path/to/my_file.eng.txt"
```

**Translate an entire directory using Refinement Mode:**
```bash
python -m text_translator.cli "./path/to/my_dir" --model "my-refiner-model" --refine --draft-model "my-draft-model" --output "./path/to/translated_dir"
```

### Key Arguments

-   `input_path`: The source file or directory.
-   `--model`: The name of the main (or refiner) model to use.
-   `--output`: The destination file or directory.
-   `--refine`: Enables Refinement Mode.
-   `--draft-model`: (Required for refine mode) The model to use for drafts.
-   `--api-base-url`: The URL of your LLM API server.
-   `--glossary-file`: Path to a text file containing glossary terms.
-   `--line-by-line`: Translates text line by line.
-   `--help`: Shows a full list of all available options.

## Repository-Wide Testing

To ensure both projects are functioning correctly, you can run the main test script from the root of the repository. This will install dependencies and run the unit tests for both `custom_xml_parser` and `text_translator`.

```bash
# From the repository root
./run_all_tests.sh
```
Note: A bash script `run_all_tests.sh` containing the test commands from `AGENTS.md` should be created to make this command work.
