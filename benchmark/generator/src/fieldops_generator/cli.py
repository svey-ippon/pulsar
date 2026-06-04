"""fieldops-generate: generate the FieldOps silver dataset as dbt seeds.

Generates in memory, runs the divergence pre-flight checks, and only writes the
seed CSVs when every check passes (spec §6.2: a failing generation is rejected).
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from .checks import format_report, run_checks
from .config import GeneratorConfig
from .output import find_default_seeds_dir, write_seeds
from .pipeline import generate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None, help="override the RNG seed")
    parser.add_argument(
        "--seeds-dir",
        type=Path,
        default=None,
        help="output directory (default: <repo>/transformations/dbt/seeds/fieldops)",
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

    seeds_dir = args.seeds_dir or find_default_seeds_dir(Path.cwd())
    if seeds_dir is None and not args.check_only:
        parser.error("could not locate transformations/dbt/seeds — pass --seeds-dir")

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

    counts = write_seeds(ds, seeds_dir)
    print(f"\nSeeds written to {seeds_dir}:")
    for file_name, n_rows in sorted(counts.items()):
        print(f"  {file_name}: {n_rows} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
