import argparse
import json
import os
import statistics
import sys
import timeit
from typing import Any, Callable, Dict, List

from custom_xml_parser.parser import deserialize, serialize

# --- Default Configuration ---
DEFAULT_ITERATIONS = 100
DEFAULT_REPEAT = 5
DEFAULT_DATA_FILES = [
    "custom_xml_parser/tests/data/yuyuko_j.txt",
    "custom_xml_parser/tests/data/yuyuko_ev_j.txt",
]

class Statistics:
    """A container for statistical measurements of benchmark timings.

    Attributes:
        mean_s: The mean (average) time in seconds.
        median_s: The median time in seconds.
        stdev_s: The standard deviation in seconds.
        min_s: The minimum time in seconds.
        max_s: The maximum time in seconds.
    """
    def __init__(self, times_s: List[float]):
        """Initializes the Statistics object from a list of timings.

        Args:
            times_s: A list of time measurements in seconds.
        """
        self.mean_s = statistics.mean(times_s)
        self.median_s = statistics.median(times_s)
        self.stdev_s = statistics.stdev(times_s) if len(times_s) > 1 else 0.0
        self.min_s = min(times_s)
        self.max_s = max(times_s)

    def to_dict(self) -> Dict[str, float]:
        """Converts the statistics to a dictionary.

        The dictionary contains the statistical measures, with all time values
        converted to milliseconds for easier interpretation.

        Returns:
            A dictionary mapping statistic names to their values in milliseconds.
        """
        return {
            "mean_ms": self.mean_s * 1000,
            "median_ms": self.median_s * 1000,
            "stdev_ms": self.stdev_s * 1000,
            "min_ms": self.min_s * 1000,
            "max_ms": self.max_s * 1000,
        }

class BenchmarkResult:
    """Stores the results of a benchmark for a single file.

    This class holds the configuration and performance statistics for both
    serialization and deserialization of a specific data file.

    Attributes:
        file_path: The path to the data file that was benchmarked.
        iterations: The number of iterations per benchmark repetition.
        repetitions: The number of times the benchmark was repeated.
        deserialize_stats: A `Statistics` object for the deserialization test.
        serialize_stats: A `Statistics` object for the serialization test.
    """
    def __init__(self, file_path: str, iterations: int, repetitions: int):
        """Initializes the BenchmarkResult for a given file and configuration.

        Args:
            file_path: The path to the data file.
            iterations: The number of iterations per repetition.
            repetitions: The number of repetitions for the benchmark.
        """
        self.file_path = file_path
        self.iterations = iterations
        self.repetitions = repetitions
        self.deserialize_stats: Statistics = None
        self.serialize_stats: Statistics = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the benchmark result to a dictionary for serialization.

        Returns:
            A dictionary representation of the benchmark result, suitable for
            JSON output.
        """
        return {
            "file": os.path.basename(self.file_path),
            "iterations": self.iterations,
            "repetitions": self.repetitions,
            "deserialization": self.deserialize_stats.to_dict() if self.deserialize_stats else None,
            "serialization": self.serialize_stats.to_dict() if self.serialize_stats else None,
        }

class BenchmarkRunner:
    """Orchestrates the execution of the benchmark suite.

    This class manages the process of running benchmarks across multiple data
    files, collecting the results, and printing them in various formats.

    Attributes:
        data_files: A list of paths to the data files to be benchmarked.
        iterations: The number of iterations for each benchmark repetition.
        repeat: The number of times to repeat each benchmark.
        results: A list of `BenchmarkResult` objects, populated after `run()`
                 is called.
    """
    def __init__(self, data_files: List[str], iterations: int, repeat: int):
        """Initializes the BenchmarkRunner with the specified configuration.

        Args:
            data_files: A list of paths to the data files.
            iterations: The number of iterations per repetition.
            repeat: The number of times to repeat the benchmark.
        """
        self.data_files = data_files
        self.iterations = iterations
        self.repeat = repeat
        self.results: List[BenchmarkResult] = []

    def _run_benchmark(self, func: Callable[[], Any]) -> Statistics:
        """Runs a benchmark for a given function and returns statistics.

        This helper method uses the `timeit` module to repeatedly execute a
        function and captures the timing results.

        Args:
            func: The function to be benchmarked.

        Returns:
            A `Statistics` object containing the performance measurements.
        """
        timer = timeit.Timer(func)
        times = timer.repeat(repeat=self.repeat, number=self.iterations)
        # Calculate time per iteration
        times_per_iteration = [t / self.iterations for t in times]
        return Statistics(times_per_iteration)

    def run(self):
        """Executes the full benchmark suite for all specified data files.

        This method iterates through each data file, running both deserialization
        and serialization benchmarks, and stores the results.
        """
        for file_path in self.data_files:
            result = BenchmarkResult(file_path, self.iterations, self.repeat)
            raw_content = load_test_data(file_path)

            # 1. Benchmark Deserialization
            result.deserialize_stats = self._run_benchmark(lambda: deserialize(raw_content))

            # 2. Benchmark Serialization
            parsed_data = deserialize(raw_content)
            result.serialize_stats = self._run_benchmark(lambda: serialize(parsed_data))

            self.results.append(result)

    def print_results_human_readable(self):
        """Prints the benchmark results in a human-readable table."""
        print("--- Custom XML Parser Benchmark ---")
        print(f"Iterations per repetition: {self.iterations}")
        print(f"Repetitions: {self.repeat}")

        for result in self.results:
            print("\n" + "=" * 80)
            print(f"Benchmark for: {os.path.basename(result.file_path)}")
            print("=" * 80)

            stats = result.deserialize_stats.to_dict()
            print("\nDeserialization Performance:")
            print(f"  Mean:   {stats['mean_ms']:.4f} ms")
            print(f"  Median: {stats['median_ms']:.4f} ms")
            print(f"  Stdev:  {stats['stdev_ms']:.4f} ms")
            print(f"  Min:    {stats['min_ms']:.4f} ms (Best)")
            print(f"  Max:    {stats['max_ms']:.4f} ms (Worst)")

            stats = result.serialize_stats.to_dict()
            print("\nSerialization Performance:")
            print(f"  Mean:   {stats['mean_ms']:.4f} ms")
            print(f"  Median: {stats['median_ms']:.4f} ms")
            print(f"  Stdev:  {stats['stdev_ms']:.4f} ms")
            print(f"  Min:    {stats['min_ms']:.4f} ms (Best)")
            print(f"  Max:    {stats['max_ms']:.4f} ms (Worst)")
            print("-" * 80)

        print("\n--- Benchmark Complete ---")


    def print_results_json(self):
        """Prints the benchmark results in JSON format."""
        output_data = {
            "configuration": {
                "iterations": self.iterations,
                "repetitions": self.repeat,
                "data_files": self.data_files
            },
            "results": [res.to_dict() for res in self.results]
        }
        print(json.dumps(output_data, indent=2))


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
        help="Number of times to repeat the benchmark."
    )
    parser.add_argument(
        '--output-json',
        action='store_true',
        help="Output the results in JSON format instead of a human-readable table."
    )
    args = parser.parse_args()

    runner = BenchmarkRunner(
        data_files=args.data_files,
        iterations=args.iterations,
        repeat=args.repeat
    )
    runner.run()

    if args.output_json:
        runner.print_results_json()
    else:
        runner.print_results_human_readable()

if __name__ == "__main__":
    main()
