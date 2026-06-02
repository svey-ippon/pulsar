"""The generated dataset: one DataFrame per silver (operational) table."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd


@dataclass
class Dataset:
    """All FieldOps silver tables, keyed by their seed file name (without prefix)."""

    geography: pd.DataFrame
    clients: pd.DataFrame
    sites: pd.DataFrame
    depots: pd.DataFrame
    technicians: pd.DataFrame
    equipment_categories: pd.DataFrame
    equipment_units: pd.DataFrame
    parts: pd.DataFrame
    work_orders: pd.DataFrame
    work_order_lines: pd.DataFrame
    work_order_servicing: pd.DataFrame
    payments: pd.DataFrame
    surveys: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
