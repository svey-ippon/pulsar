# fieldops-generator

Deterministic synthetic-data generator for the FieldOps benchmark
([`../FIELDOPS_SPEC.md`](../FIELDOPS_SPEC.md)). It simulates the **operational
(silver) layer** — never the gold, see
[`../GENERATOR_SILVER_FIRST.md`](../GENERATOR_SILVER_FIRST.md) — and writes one
dbt seed CSV per source table into `transformations/dbt/seeds/fieldops/`.

## Usage

```bash
cd benchmark/generator
uv run fieldops-generate            # generate, check, write seeds
uv run fieldops-generate --check-only
uv run pytest                       # determinism + invariants + divergence checks
```

The CLI generates in memory, runs the **divergence pre-flight checks**
(spec §6.2) and only writes the seeds when every check passes. A failing
generation is rejected: retune `config.py`, regenerate.

## Design

| Module | Responsibility |
|---|---|
| `config.py` | every simulation knob + the check thresholds (one frozen dataclass) |
| `vocab.py` | fictional vocabulary (states, cities, clients, equipment, parts) — hand-rolled, no faker, fully deterministic |
| `referentials.py` | geography, clients, sites, depots, technicians, equipment units, parts |
| `workorders.py` | the work-order lifecycle simulation (the core): milestones, crew, lines, payments, surveys — cross-table invariants hold by construction |
| `checks.py` | pre-flight implementation of every certified/naive divergence assert (A1..E2) |
| `output.py` | seed CSV writer |
| `cli.py` | `fieldops-generate` entry point |

Determinism: a single `numpy` `default_rng(seed)` stream feeds the whole
pipeline; same seed → byte-identical CSVs (tested).

Definitions shared with the dbt gold (keep aligned):
`sla_delay_bdays = np.busday_count(promised_date, completed_date)` — signed
count of business days (Mon–Fri, no holiday calendar) in `[promised,
completed)`.
