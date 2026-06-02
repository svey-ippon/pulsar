"""End-to-end generation pipeline: referentials -> work-order simulation -> Dataset."""

from __future__ import annotations

import numpy as np

from .config import GeneratorConfig
from .dataset import Dataset
from . import referentials
from .workorders import simulate_work_orders


def generate(cfg: GeneratorConfig | None = None) -> Dataset:
    cfg = cfg or GeneratorConfig()
    rng = np.random.default_rng(cfg.seed)

    geography = referentials.build_geography(rng)
    clients = referentials.build_clients(rng, cfg)
    sites = referentials.build_sites(rng, cfg, clients, geography)
    depots = referentials.build_depots(rng, geography)
    technicians = referentials.build_technicians(rng, cfg, depots)
    equipment_categories, equipment_units = referentials.build_equipment(rng, cfg, sites)
    parts = referentials.build_parts(rng, cfg)

    activity = simulate_work_orders(
        rng, cfg, sites, geography, depots, technicians, equipment_units, parts
    )

    return Dataset(
        geography=geography,
        clients=clients,
        sites=sites,
        depots=depots,
        technicians=technicians,
        equipment_categories=equipment_categories,
        equipment_units=equipment_units,
        parts=parts,
        work_orders=activity["work_orders"],
        work_order_lines=activity["work_order_lines"],
        work_order_servicing=activity["work_order_servicing"],
        payments=activity["payments"],
        surveys=activity["surveys"],
    )
