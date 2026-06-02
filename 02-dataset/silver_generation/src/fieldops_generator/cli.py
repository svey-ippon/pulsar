"""fieldops-generate: generate the FieldOps silver dataset as CSV files.

Generates in memory, runs the divergence pre-flight checks, and only writes the
CSV files when every check passes (spec §6.2: a failing generation is rejected).
The written CSVs are then pushed to Snowflake by `fieldops-load`.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from .checks import format_report, run_checks
from .config import GeneratorConfig
from .output import DEFAULT_DATA_DIR, write_csvs
from .pipeline import generate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="override the RNG seed")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"output directory (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="generate and run the checks without writing any file",
    )
    args = parser.parse_args(argv)

    cfg = GeneratorConfig()
    if args.seed is not None:
        cfg = dataclasses.replace(cfg, seed=args.seed)

    data_dir = args.data_dir or DEFAULT_DATA_DIR

    print(f"Generating FieldOps dataset (seed={cfg.seed}) ...")
    ds = generate(cfg)

    results = run_checks(ds, cfg.thresholds)
    print(format_report(results))
    if any(not r.passed for r in results):
        print("Nothing written.")
        return 1

    if args.check_only:
        print("Check-only run: nothing written.")
        return 0

    counts = write_csvs(ds, data_dir)
    print(f"\nCSVs written to {data_dir}:")
    for file_name, n_rows in sorted(counts.items()):
        print(f"  {file_name}: {n_rows} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
