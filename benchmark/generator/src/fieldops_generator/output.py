"""CSV output: one dbt seed file per silver table."""

from __future__ import annotations

from pathlib import Path

from .dataset import Dataset

SEED_PREFIX = "fieldops"


def write_seeds(ds: Dataset, seeds_dir: Path) -> dict[str, int]:
    """Write every table as `<prefix>_<table>.csv` and return row counts."""
    seeds_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, frame in ds.tables().items():
        path = seeds_dir / f"{SEED_PREFIX}_{name}.csv"
        frame.to_csv(path, index=False, date_format="%Y-%m-%d", na_rep="")
        counts[path.name] = len(frame)
    return counts


def find_default_seeds_dir(start: Path) -> Path | None:
    """Locate `transformations/dbt/seeds` from any directory inside the repo."""
    for candidate in [start, *start.parents]:
        seeds = candidate / "transformations" / "dbt" / "seeds"
        if seeds.is_dir() or (candidate / "transformations" / "dbt").is_dir():
            return seeds / "fieldops"
    return None
