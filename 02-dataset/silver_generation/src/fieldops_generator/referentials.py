"""Referential (slowly-changing) entities: geography, clients, sites, depots,
technicians, equipment, parts.

Each builder takes the shared numpy Generator so the whole dataset is one
deterministic stream (config.seed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import GeneratorConfig
from . import vocab


def _weighted_choice(rng: np.random.Generator, items: list[tuple[str, float]], size: int) -> np.ndarray:
    values = [v for v, _ in items]
    probs = np.array([p for _, p in items])
    return rng.choice(values, size=size, p=probs / probs.sum())


def build_geography(rng: np.random.Generator) -> pd.DataFrame:
    """~12 zip prefixes per state, each tied to a fictional city.

    Zip prefixes are 3-digit strings allocated in per-state blocks (mirrors how
    real postal systems regionalize prefixes).
    """
    rows = []
    city_names = [s + suf for s in vocab.CITY_STEMS for suf in vocab.CITY_SUFFIXES]
    rng.shuffle(city_names)
    city_iter = iter(city_names)
    for i, (state, _abbr) in enumerate(vocab.STATES):
        block_start = 100 + i * 25
        n_zips = int(rng.integers(10, 15))
        prefixes = rng.choice(np.arange(block_start, block_start + 25), size=n_zips, replace=False)
        n_cities = int(rng.integers(4, 7))
        cities = [next(city_iter) for _ in range(n_cities)]
        for prefix in sorted(prefixes):
            rows.append(
                {
                    "zip_code_prefix": str(prefix),
                    "city": cities[int(rng.integers(0, n_cities))],
                    "state": state,
                }
            )
    return pd.DataFrame(rows)


def build_clients(rng: np.random.Generator, cfg: GeneratorConfig) -> pd.DataFrame:
    combos = [f"{s} {suf}" for s in vocab.CLIENT_STEMS for suf in vocab.CLIENT_SUFFIXES]
    names = rng.choice(combos, size=cfg.n_clients, replace=False)
    tiers = rng.choice(
        list(cfg.tier_probs), size=cfg.n_clients, p=list(cfg.tier_probs.values())
    )
    return pd.DataFrame(
        {
            "client_id": [f"CL-{i + 1:04d}" for i in range(cfg.n_clients)],
            "client_name": names,
            "industry": rng.choice(vocab.INDUSTRIES, size=cfg.n_clients),
            "contract_tier": tiers,
        }
    )


def build_sites(
    rng: np.random.Generator, cfg: GeneratorConfig, clients: pd.DataFrame, geography: pd.DataFrame
) -> pd.DataFrame:
    """Sites per client drawn per contract tier — A1 requires avg >= 3 sites/client."""
    zips = geography["zip_code_prefix"].to_numpy()
    rows = []
    for client in clients.itertuples(index=False):
        lo, hi = cfg.sites_per_tier[client.contract_tier]
        n_sites = int(rng.integers(lo, hi + 1))
        site_types = _weighted_choice(rng, vocab.SITE_TYPES, n_sites)
        site_zips = rng.choice(zips, size=n_sites)
        for site_type, zip_prefix in zip(site_types, site_zips):
            rows.append(
                {
                    "site_id": f"ST-{len(rows) + 1:04d}",
                    "client_id": client.client_id,
                    "site_type": site_type,
                    "zip_code_prefix": zip_prefix,
                }
            )
    sites = pd.DataFrame(rows)
    city_by_zip = geography.set_index("zip_code_prefix")["city"]
    sites["site_name"] = [
        f"{city_by_zip[z]} {vocab.SITE_LABELS[t]}"
        for z, t in zip(sites["zip_code_prefix"], sites["site_type"])
    ]
    return sites[["site_id", "client_id", "site_name", "site_type", "zip_code_prefix"]]


def build_depots(rng: np.random.Generator, geography: pd.DataFrame) -> pd.DataFrame:
    """One depot per state (12) so a same-state dispatch always exists (C3 knob)."""
    rows = []
    for state, abbr in vocab.STATES:
        state_zips = geography.loc[geography["state"] == state, "zip_code_prefix"].to_numpy()
        rows.append(
            {
                "depot_code": f"DP-{abbr}",
                "zip_code_prefix": rng.choice(state_zips),
            }
        )
    return pd.DataFrame(rows)


def build_technicians(
    rng: np.random.Generator, cfg: GeneratorConfig, depots: pd.DataFrame
) -> pd.DataFrame:
    depot_codes = rng.choice(depots["depot_code"].to_numpy(), size=cfg.n_technicians)
    return pd.DataFrame(
        {
            "technician_id": [f"TC-{i + 1:03d}" for i in range(cfg.n_technicians)],
            "depot_code": depot_codes,
            "seniority_level": _weighted_choice(rng, vocab.SENIORITY_LEVELS, cfg.n_technicians),
        }
    )


def build_equipment(
    rng: np.random.Generator, cfg: GeneratorConfig, sites: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    categories = pd.DataFrame(
        vocab.EQUIPMENT_CATEGORIES, columns=["equipment_category", "category_group"]
    )
    cat_values = categories["equipment_category"].to_numpy()
    rows = []
    for site in sites.itertuples(index=False):
        n_units = int(rng.integers(cfg.units_per_site[0], cfg.units_per_site[1] + 1))
        unit_cats = rng.choice(cat_values, size=n_units)
        for cat in unit_cats:
            unit_no = len(rows) + 1
            install_year = int(rng.integers(2005, 2019))
            rows.append(
                {
                    "equipment_unit_id": f"EQ-{unit_no:05d}",
                    "site_id": site.site_id,
                    "equipment_category": cat,
                    "serial_number": f"SN-{cat[:3].upper()}-{rng.integers(10_000, 99_999)}",
                    "installed_date": f"{install_year}-{int(rng.integers(1, 13)):02d}-{int(rng.integers(1, 29)):02d}",
                }
            )
    return categories, pd.DataFrame(rows)


def build_parts(rng: np.random.Generator, cfg: GeneratorConfig) -> pd.DataFrame:
    families = list(vocab.PART_FAMILIES)
    rows = []
    for i in range(cfg.n_parts):
        family = families[i % len(families)]
        label, base_price = vocab.PART_FAMILIES[family]
        code = f"{chr(65 + int(rng.integers(0, 26)))}{chr(65 + int(rng.integers(0, 26)))}-{rng.integers(100, 999)}"
        rows.append(
            {
                "part_id": f"PT-{i + 1:04d}",
                "part_name": f"{label} {code}",
                "part_family": family,
                "list_price": round(float(base_price * rng.uniform(0.8, 1.3)), 2),
            }
        )
    return pd.DataFrame(rows)
