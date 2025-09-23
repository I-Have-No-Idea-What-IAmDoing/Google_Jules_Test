import os
import sys
import timeit
from typing import Any, Dict

# Add the root directory to the Python path to allow for absolute imports
# This is necessary because the script is not in a package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from custom_xml_parser.parser import deserialize, serialize

# --- Configuration ---
BENCHMARK_ITERATIONS = 100
DATA_FILES = [
    "custom_xml_parser/tests/data/yuyuko_j.txt",
    "custom_xml_parser/tests/data/yuyuko_ev_j.txt",
]

def load_test_data(file_path: str) -> str:
    """Loads content from a specified data file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Data file not found at '{file_path}'.")
        print("Please ensure the script is run from the repository's root directory.")
        sys.exit(1)

def run_deserialize_benchmark(content: str, iterations: int) -> float:
    """Runs the benchmark for the deserialize function."""
    timer = timeit.Timer(lambda: deserialize(content))
    total_time = timer.timeit(number=iterations)
    return total_time / iterations

def run_serialize_benchmark(data: Dict[str, Any], iterations: int) -> float:
    """Runs the benchmark for the serialize function."""
    timer = timeit.Timer(lambda: serialize(data))
    total_time = timer.timeit(number=iterations)
    return total_time / iterations

def main():
    """
    Main function to execute the benchmark suite.

    This function iterates through the predefined data files and performs
    the following actions for each:
    1.  Loads the file content.
    2.  Runs a benchmark on the `deserialize` function to measure its
        performance in parsing the text into a dictionary.
    3.  Deserializes the content to get the data structure needed for the
        serialization benchmark.
    4.  Runs a benchmark on the `serialize` function to measure its
        performance in converting the dictionary back into a string.
    5.  Prints the results in a formatted table.
    """
    print("--- Custom XML Parser Benchmark ---")
    print(f"Iterations per test: {BENCHMARK_ITERATIONS}\n")
    print(f"{'Data File':<40} | {'Avg. Deserialize Time (ms)':<30} | {'Avg. Serialize Time (ms)':<30}")
    print("-" * 105)

    for file_path in DATA_FILES:
        # Load the raw text content from the file.
        raw_content = load_test_data(file_path)

        # 1. Benchmark Deserialization
        avg_deserialize_time = run_deserialize_benchmark(raw_content, BENCHMARK_ITERATIONS)

        # Prepare data for serialization benchmark by deserializing it once.
        # This is done outside the timed loop to not affect serialization timing.
        parsed_data = deserialize(raw_content)

        # 2. Benchmark Serialization
        avg_serialize_time = run_serialize_benchmark(parsed_data, BENCHMARK_ITERATIONS)

        # Print results for the current file.
        file_name = os.path.basename(file_path)
        deserialize_ms = avg_deserialize_time * 1000
        serialize_ms = avg_serialize_time * 1000
        print(f"{file_name:<40} | {f'{deserialize_ms:.4f} ms':<30} | {f'{serialize_ms:.4f} ms':<30}")

    print("\n--- Benchmark Complete ---")

if __name__ == "__main__":
    main()
