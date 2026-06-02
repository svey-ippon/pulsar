# 02 — The FieldOps domain and the gold star

> The full physical model (every column, with trap ids annotated) is in
> [`fieldops_gold_modelisation.dbml`](fieldops_gold_modelisation.dbml)
> (viewable on dbdiagram.io via [`fieldops_gold_modelisation.dbdiagram`](fieldops_gold_modelisation.dbdiagram)).
> The dbt models that build it live in
> [`../../02-dataset/gold_transformation/`](../../02-dataset/gold_transformation).

## The domain

**FieldOps** is a fictional industrial-maintenance provider. Client companies hold **service
contracts**; each client operates one or more **sites** where **equipment units**
(compressors, HVAC, conveyors, …) are installed. When something needs servicing, a **work
order** is opened, given an **SLA-promised date**, scheduled, and assigned to a
**technician** dispatched from a **depot**. The intervention produces **lines** (spare parts
used and labor), is invoiced per work order with a flat **call-out fee**, and is settled by
one or more **payments**. After completion the client may answer a **satisfaction survey**
(and may be re-surveyed).

Work-order lifecycle — the accumulating-snapshot milestones:

```
opened → promised (SLA) → scheduled → started → completed → validated
```

### Narrative facts that ground the traps

These are the domain rules that make the traps real. Each maps to trap ids in
[`03-trap-catalogue.md`](03-trap-catalogue.md).

- A **client** is the contract-holding company, **not** a site. Clients typically operate
  several sites (the generator enforces it). → *A1, CV-2*
- FieldOps prices interventions **all-in**: the call-out (travel) fee is part of service
  revenue. → *B1, CV-1, D1*
- SLA commitments are expressed in **business days** against the **promised** date, with a
  contractual grace period. → *B2, CV-3*
- A work order can cover **several equipment units of different categories** ("service all
  compressors on site B") → N-N to categories, hence a **weighted bridge**. → *C2*
- Two geographies per work order: the **site location** (where work happens) and the
  **technician's depot** (where the crew is dispatched from). → *C3*
- A work order carries a **crew** (a lead technician plus others): man-hours billed can far
  exceed the on-site elapsed presence. → *A3, A5, F4*
- **Equipment units exist in the silver layer only.** They ground realism and the bridge
  weights; the gold exposes the work-order ↔ category bridge, not the units.

## The gold star

A Kimball star: **thin facts**, **conformed dimensions**, a **keys-only weighted bridge**,
and **role-playing** dates and geography. Two structures (marked ➕) were added purely to
carry traps that the plain skeleton could not support.

### Structural choices (and why)

- **Client is reached by snowflaking, not a direct FK.** Facts carry `site_id`;
  `dim_sites.client_id → dim_clients`. No direct client key on facts — this keeps A1 a
  multi-hop navigation and avoids a second join path.
- **The technician on a work order is the crew lead** (his depot is the dispatch-geography
  role, C3). A `crew_size` degenerate attribute makes multi-technician work orders explicit
  and grounds the "billed hours ≫ on-site duration" divergence (A3).
- **Payments carry a `paid_date_key`.** Payment timing lags completion, so monthly collected
  cash ≠ monthly service revenue (A2).
- **Depot is carried as attributes on `dim_technicians`**, not a separate dimension.

### Facts

| Table | Grain | Notable content |
|---|---|---|
| `fct_work_orders` | one work order | FK `site_id`, `technician_id` (crew lead); 6 role-playing date keys (opened, promised, scheduled, started, completed, validated); degenerate `work_order_id`, type, priority, `crew_size`; `sla_delay_bdays` **precomputed by dbt** (business days vs promised; NULL = not completed); ➕ `call_out_fee` — header-grain measure (additivity trap D1); ➕ `duration_hours` — on-site elapsed presence, a false-friend pair with `billed_hours` (A3/F4) |
| `fct_work_order_lines` | one line | `line_kind` (PART \| LABOR); `line_amount`, `quantity`, `billed_hours` (labor only); `part_id` **NULL on labor lines** (meaningful NULL); FK work_order, part |
| `fct_work_order_payments` | work order × payment sequence | `payment_amount`, method, sequence; `paid_date_key` (payment lag → A2) |
| `fct_satisfaction_surveys` | one survey response | several responses possible per work order (re-surveys); `satisfaction_score` (1–10 scale); grain convention: **latest response counts** (D3) |

### Dimensions & bridge

| Table | Notes |
|---|---|
| `dim_date` | conformed calendar spine; role-played by every date key |
| `dim_clients` | contract holders (companies) — the "customer" of record (CV-2) |
| `dim_sites` | client locations; FK to client; zip → geography |
| `dim_technicians` | assigned to a depot; depot zip → geography |
| `dim_geography` | zip-prefix grain; role-playing: site location vs technician depot |
| `dim_equipment_categories` | category referential; reached from work orders via the weighted bridge |
| `dim_parts` | spare-parts catalogue (lines reference it) |
| `bridge_work_order_categories` | keys-only, with `allocation_weight` (1/N of the categories actually serviced) |

> The dbt model names are `fieldops_*` (dbt names are project-global) and are aliased back
> to the plain star names (`DIM_*`, `FCT_*`, `BRIDGE_*`) in the `FIELDOPS_GOLD` schema — see
> the [gold README](../../02-dataset/gold_transformation/README.md) for the full inventory.
