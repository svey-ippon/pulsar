"""FieldOps synthetic-data generator (see FIELDOPS_SPEC.md)."""

from .config import CheckThresholds, GeneratorConfig
from .dataset import Dataset
from .pipeline import generate

__all__ = ["CheckThresholds", "Dataset", "GeneratorConfig", "generate"]
