# Benchmarks

This directory contains scripts for benchmarking the performance of different parts of the repository.

## `benchmark_xml_parser.py`

This script measures the performance of the `serialize` and `deserialize` functions in the `custom_xml_parser` module.

### Setup

Before running the benchmark, it's recommended to install the project in editable mode. This ensures that the `custom_xml_parser` package is correctly recognized without needing to modify the Python path. From the root of the repository, run:

```bash
pip install -e .
```

### How to Run

Execute the script from the root of the repository. You can customize the benchmark with command-line arguments.

**Basic execution (uses default settings):**
```bash
python benchmarks/benchmark_xml_parser.py
```

**Custom execution:**
```bash
python benchmarks/benchmark_xml_parser.py --iterations 50 --data-files path/to/your/data.txt
```

**JSON Output:**
To get the output in a machine-readable JSON format, use the `--output-json` flag:
```bash
python benchmarks/benchmark_xml_parser.py --output-json
```

### Command-Line Arguments

-   `--data-files`: (Optional) A space-separated list of paths to data files for benchmarking. Defaults to a predefined set of test files.
-   `--iterations`: (Optional) The number of times to run the operation within each benchmark repetition. Defaults to `100`.
-   `--repeat`: (Optional) The number of times to repeat the benchmark. The script will report the *best* (fastest) time among the repetitions, which helps to minimize the impact of system noise and provide a more accurate measurement. Defaults to `5`.
-   `--output-json`: (Optional) If specified, the output will be in JSON format. Otherwise, it will be a human-readable table.

### What it Measures

The script measures the best time it takes to:

1.  **Deserialize**: Parse a text file in the custom XML-like format into a Python dictionary.
2.  **Serialize**: Convert a Python dictionary back into a formatted string.

The results show the average time in milliseconds for each operation, which is useful for detecting performance regressions in the parser.
