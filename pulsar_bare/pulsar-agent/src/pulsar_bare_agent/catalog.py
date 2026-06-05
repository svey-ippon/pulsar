from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml

class DomainNotFoundError(ValueError):
    """Raised when a requested domain has no semantic contract."""


@lru_cache(maxsize=8)
def load_domain(domain_id: str) -> dict[str, Any]:
    """Load and parse the YAML semantic contract for *domain_id*.

    The contract files ship inside the package under ``semantic/<domain_id>.yaml``.
    """
    resource = files("pulsar_bare_agent.semantic").joinpath(f"{domain_id}.yaml")
    if not resource.is_file():
        raise DomainNotFoundError(domain_id)
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


def list_domain_ids() -> list[str]:
    """Return the domain ids for which a contract exists (one per *.yaml in semantic/)."""
    root = files("pulsar_bare_agent.semantic")
    return sorted(
        p.name[: -len(".yaml")]
        for p in root.iterdir()
        if p.name.endswith(".yaml")
    )
