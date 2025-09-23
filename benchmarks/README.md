# Benchmarks

This directory contains scripts for benchmarking the performance of different parts of the repository.

## `benchmark_xml_parser.py`

This script measures the performance of the `serialize` and `deserialize` functions in the `custom_xml_parser` module.

### How to Run

Execute the script from the root of the repository:

```bash
python benchmarks/benchmark_xml_parser.py
```

### What it Measures

The script measures the average time it takes to:

1.  **Deserialize**: Parse a text file in the custom XML-like format into a Python dictionary.
2.  **Serialize**: Convert a Python dictionary back into a formatted string.

The results are printed to the console, showing the average time in milliseconds for each operation on a set of test data files. This is useful for detecting performance regressions in the parser.
