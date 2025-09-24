import argparse
import json
import os
import sys
import timeit
from typing import Any, Dict, List

from custom_xml_parser.parser import deserialize, serialize

# --- Default Configuration ---
DEFAULT_ITERATIONS = 100
DEFAULT_REPEAT = 5
DEFAULT_DATA_FILES = [
    "custom_xml_parser/tests/data/yuyuko_j.txt",
    "custom_xml_parser/tests/data/yuyuko_ev_j.txt",
]

def load_test_data(file_path: str) -> str:
    """Loads content from a specified data file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Data file not found at '{file_path}'.", file=sys.stderr)
        print("Please ensure the path is correct and the script is run from the repository's root directory.", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)

def run_deserialize_benchmark(content: str, iterations: int, repeat: int) -> float:
    """Runs the benchmark for the deserialize function."""
    timer = timeit.Timer(lambda: deserialize(content))
    times = timer.repeat(repeat=repeat, number=iterations)
    best_time = min(times)
    return best_time / iterations

def run_serialize_benchmark(data: Dict[str, Any], iterations: int, repeat: int) -> float:
    """Runs the benchmark for the serialize function."""
    timer = timeit.Timer(lambda: serialize(data))
    times = timer.repeat(repeat=repeat, number=iterations)
    best_time = min(times)
    return best_time / iterations

def main():
    """
    Main function to execute the benchmark suite.
    Parses command-line arguments and runs the benchmarks.
    """
    parser = argparse.ArgumentParser(
        description="Run benchmarks for the custom XML parser.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--data-files',
        nargs='+',
        default=DEFAULT_DATA_FILES,
        help="Paths to the data files to use for benchmarking."
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Number of times to run the operation within each benchmark repetition."
    )
    parser.add_argument(
        '--repeat',
        type=int,
        default=DEFAULT_REPEAT,
        help="Number of times to repeat the benchmark. The best result is taken."
    )
    parser.add_argument(
        '--output-json',
        action='store_true',
        help="Output the results in JSON format instead of a human-readable table."
    )
    args = parser.parse_args()

    results = []

    for file_path in args.data_files:
        raw_content = load_test_data(file_path)

        # 1. Benchmark Deserialization
        avg_deserialize_time = run_deserialize_benchmark(raw_content, args.iterations, args.repeat)

        # Prepare data for serialization benchmark
        parsed_data = deserialize(raw_content)

        # 2. Benchmark Serialization
        avg_serialize_time = run_serialize_benchmark(parsed_data, args.iterations, args.repeat)

        results.append({
            "file": os.path.basename(file_path),
            "deserialize_time_ms": avg_deserialize_time * 1000,
            "serialize_time_ms": avg_serialize_time * 1000
        })

    if args.output_json:
        output_data = {
            "iterations": args.iterations,
            "repetitions": args.repeat,
            "benchmarks": results
        }
        print(json.dumps(output_data, indent=2))
    else:
        print("--- Custom XML Parser Benchmark ---")
        print(f"Iterations per repetition: {args.iterations}")
        print(f"Repetitions: {args.repeat} (best time taken)")
        print(f"\n{'Data File':<40} | {'Best Deserialize Time (ms)':<30} | {'Best Serialize Time (ms)':<30}")
        print("-" * 105)
        for res in results:
            print(f'{res["file"]:<40} | {f"{res['deserialize_time_ms']:.4f} ms":<30} | {f"{res['serialize_time_ms']:.4f} ms":<30}')
        print("\n--- Benchmark Complete ---")

if __name__ == "__main__":
    main()
