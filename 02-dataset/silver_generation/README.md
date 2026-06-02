# FieldOps silver generation

Owns the **operational (silver) layer** of the FieldOps benchmark dataset: it
**generates** it deterministically and **pushes it to Snowflake**
(`PULSAR_DB.FIELDOPS_SILVER`). The gold star is built downstream by dbt in
[`../gold_transformation/`](../gold_transformation) — it reads these silver tables
as **sources** (not dbt seeds).

See [`../../00-doc/dataset/`](../../00-doc/dataset) for the dataset design (start with its
[`README.md`](../../00-doc/dataset/README.md)); in particular
[`04-generation.md`](../../00-doc/dataset/04-generation.md) for why we generate silver (not
gold) and let dbt transform.

## Workflow

```bash
cd 02-dataset/silver_generation

uv run fieldops-generate            # simulate + divergence checks + write data/*.csv
uv run fieldops-generate --check-only   # simulate + checks in memory, write nothing
uv run pytest                       # tests the in-memory regenerated dataset (NOT data/*.csv):
                                    #   determinism + lifecycle invariants + divergence checks

uv run fieldops-load                # push data/*.csv -> PULSAR_DB.FIELDOPS_SILVER
```

`fieldops-generate` generates in memory, runs the **divergence pre-flight checks**
(spec §6.2 — acceptance gates on the *data*, not code tests; coverage in
[`../../00-doc/dataset/04-generation.md`](../../00-doc/dataset/04-generation.md))
and only writes the CSVs when every check passes. A failing generation is
rejected: retune `config.py`, regenerate.

`fieldops-load` (needs Snowflake creds) creates one typed, commented table per
`schemas/<table>.yaml` in `FIELDOPS_SILVER` and loads the matching `data/*.csv`
via an internal stage + `COPY INTO`. Options:

```bash
uv run fieldops-load --connection-name dev
uv run fieldops-load --role PULSAR_ADM --database PULSAR_DB --schema FIELDOPS_SILVER
```

Connection is resolved from a Snowflake `config.toml` / `connections.toml`
profile (default: `PULSAR_ADM` role, `PULSAR_DB.FIELDOPS_SILVER`).

## Layout

```text
silver_generation/
  data/                 # generated CSVs (committed; deterministic), one per silver table
  schemas/              # YAML source-of-truth per table: types + column comments
  src/fieldops_generator/
  tests/
```

## Generator design

| Module | Responsibility |
|---|---|
| `config.py` | every simulation knob + the check thresholds (one frozen dataclass) |
| `vocab.py` | fictional vocabulary (states, cities, clients, equipment, parts) — hand-rolled, no faker, fully deterministic |
| `referentials.py` | geography, clients, sites, depots, technicians, equipment units, parts |
| `workorders.py` | the work-order lifecycle simulation (the core): milestones, crew, lines, payments, surveys — cross-table invariants hold by construction |
| `checks.py` | pre-flight implementation of every certified/naive divergence assert (A1..E2) |
| `output.py` | CSV writer (one `<table>.csv` per silver table into `data/`) |
| `load.py` | `fieldops-load` — Snowflake loader into `FIELDOPS_SILVER` |
| `cli.py` | `fieldops-generate` entry point |

Determinism: a single `numpy` `default_rng(seed)` stream feeds the whole
pipeline; same seed → byte-identical CSVs (tested).

Definitions shared with the dbt gold (keep aligned):
`sla_delay_bdays = np.busday_count(promised_date, completed_date)` — signed
count of business days (Mon–Fri, no holiday calendar) in `[promised, completed)`.
