"""Fictional vocabulary for the FieldOps domain.

Everything here is invented (spec §6.6): no real brands, no real geography, no
values that could point back to a public dataset. Hand-rolled lists rather than
faker so the output is fully controlled and deterministic across environments.
"""

from __future__ import annotations

# ── Geography: 12 fictional states, fictional city name parts ────────────────

STATES: list[tuple[str, str]] = [
    ("Northvale", "NTV"),
    ("Caldera", "CLD"),
    ("Ostbrook", "OSB"),
    ("Veyland", "VYL"),
    ("Harrowfield", "HRW"),
    ("Duskmoor", "DSK"),
    ("Eastmere", "EMR"),
    ("Quillan", "QLN"),
    ("Sablewood", "SBW"),
    ("Tarrindale", "TRD"),
    ("Westhollow", "WSH"),
    ("Bryceland", "BRC"),
]

CITY_STEMS = [
    "Bram", "Hale", "Cor", "Fen", "Gar", "Lin", "Mar", "Nor", "Pel", "Ros",
    "Stan", "Tre", "Vel", "Wick", "Yar", "Ald", "Birch", "Crag", "Dun", "Elm",
]
CITY_SUFFIXES = ["ford", "wick", "ton", "field", "bridge", "haven", "mont", "dale", "port", "crest"]

# ── Clients ──────────────────────────────────────────────────────────────────

CLIENT_STEMS = [
    "Apex", "Boreal", "Cobalt", "Drayton", "Everline", "Foundry", "Granite",
    "Helix", "Ironwood", "Juniper", "Keystone", "Lattice", "Meridian",
    "Northgate", "Oakum", "Praxis", "Quarry", "Ridgeline", "Solstice",
    "Tidewater", "Umber", "Vantage", "Wexford", "Yieldstone", "Zephyr",
    "Anvil", "Bastion", "Crucible", "Dynamo", "Ember",
]
CLIENT_SUFFIXES = [
    "Manufacturing", "Industries", "Foods", "Processing", "Logistics",
    "Materials", "Packaging", "Components", "Fabrication", "Works",
]
INDUSTRIES = [
    "manufacturing", "food_processing", "logistics", "chemicals",
    "packaging", "automotive", "pharmaceuticals", "textiles",
]

SITE_TYPES: list[tuple[str, float]] = [("plant", 0.55), ("warehouse", 0.30), ("office", 0.15)]
SITE_LABELS = {"plant": "Plant", "warehouse": "Warehouse", "office": "Office"}

# ── Equipment ────────────────────────────────────────────────────────────────

EQUIPMENT_CATEGORIES: list[tuple[str, str]] = [
    ("compressor", "rotating"),
    ("industrial_pump", "rotating"),
    ("conveyor_system", "rotating"),
    ("hvac_unit", "climate"),
    ("chiller", "climate"),
    ("boiler", "thermal"),
    ("furnace", "thermal"),
    ("control_panel", "electrical"),
    ("switchgear", "electrical"),
    ("storage_tank", "static"),
]

# ── Parts: family -> (label, base unit price) ────────────────────────────────

PART_FAMILIES: dict[str, tuple[str, float]] = {
    "filter": ("Filter", 45.0),
    "bearing": ("Bearing", 80.0),
    "valve": ("Valve", 120.0),
    "belt": ("Drive belt", 35.0),
    "seal": ("Seal kit", 25.0),
    "sensor": ("Sensor", 150.0),
    "motor": ("Motor", 420.0),
    "gasket": ("Gasket", 18.0),
    "hose": ("Hose", 40.0),
    "lubricant": ("Lubricant", 22.0),
}

SENIORITY_LEVELS: list[tuple[str, float]] = [("junior", 0.35), ("senior", 0.45), ("expert", 0.20)]
