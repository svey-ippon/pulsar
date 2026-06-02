"""CSV output: one file per silver table, written to the project's data/ dir."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from .dataset import Dataset

# silver_generation/ (this module lives at src/fieldops_generator/output.py)
PROJECT_DIR: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR: Final[Path] = PROJECT_DIR / "data"


def write_csvs(ds: Dataset, data_dir: Path) -> dict[str, int]:
    """Write every table as `<table>.csv` and return row counts."""
    data_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, frame in ds.tables().items():
        path = data_dir / f"{name}.csv"
        frame.to_csv(path, index=False, date_format="%Y-%m-%d", na_rep="")
        counts[path.name] = len(frame)
    return counts
