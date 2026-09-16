"""Count null/NaN values in a Parquet file without loading it all into memory.

Usage: python count_missing.py [path/to/file.parquet]
Empty strings and zeroes are not counted as missing.
"""

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def count_missing(path):
    parquet = pq.ParquetFile(path)
    names = parquet.schema_arrow.names
    counts = [0] * len(names)
    rows = 0
    incomplete_rows = 0

    for batch in parquet.iter_batches(batch_size=65536):
        row_missing = pa.array([False] * batch.num_rows)
        for i, column in enumerate(batch.columns):
            # nan_is_null also counts floating-point NaN values as missing.
            missing = pc.is_null(column, nan_is_null=True)
            counts[i] += pc.sum(pc.cast(missing, pa.int64())).as_py() or 0
            row_missing = pc.or_(row_missing, missing)
        incomplete_rows += pc.sum(pc.cast(row_missing, pa.int64())).as_py() or 0
        rows += batch.num_rows

    total_cells = rows * len(names)
    total_missing = sum(counts)
    percentage = lambda count, total: 100 * count / total if total else 0.0
    print(f"File: {path.name}")
    print("Missing means null or NaN; empty strings and zeroes are excluded.")
    print(f"Rows: {rows:,} | Columns: {len(names):,}")
    print(f"Missing cells: {total_missing:,} / {total_cells:,} "
          f"({percentage(total_missing, total_cells):.2f}%)")
    print(f"Rows with any missing value: {incomplete_rows:,} "
          f"({percentage(incomplete_rows, rows):.2f}%)")
    print(f"Complete rows: {rows - incomplete_rows:,}")
    print(f"Columns with missing values: {sum(c > 0 for c in counts)}")
    print()
    print(f"{'Column':<40} {'Missing':>12} {'Missing %':>12}")
    print("-" * 66)
    for name, count in sorted(zip(names, counts), key=lambda item: (-item[1], item[0])):
        print(f"{name:<40} {count:>12,} {percentage(count, rows):>11.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent / "raw" / "chars_final_with_names.parquet")
    args = parser.parse_args()
    count_missing(args.path)
