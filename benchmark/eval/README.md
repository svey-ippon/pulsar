# FieldOps eval items

The benchmark's question set (FIELDOPS_SPEC.md §4/§7): **33 items** — 17 traps +
16 controls — across the six families of `TRAP_FAMILIES.md`, plus a **probe
layer**: each convention has exactly one item testing it in isolation (see
`ITEMS.md`, "Prerequisite probes").

## Layout

| File | Content |
|---|---|
| `ITEMS.md` | **Human-readable catalogue**: per family, what each item tests, the verbatim question, the required conventions. |
| `items/family_*.yml` | **Authored, frozen.** Questions, certified SQL, naive signatures, pass criteria. Never edited after materialization without rebuilding answers. |
| `conventions.yml` | The conventions the contracts MUST carry — coverage checklist for `fieldops.yaml` (pulsar) and the semantic view (SI). Each convention lists the items that depend on it. |
| `answers.yml` | **Generated, never hand-edited** (lockfile pattern). Written by `fieldops-eval-build`: expected answers, signature values, divergence verdicts, build metadata. |
| `SCORING.md` | The manual scoring sheet template used during an eval run. |

## Item anatomy

- `kind: trap` items carry `naive_signatures`: every plausible wrong path with
  the capability it `indicates`. A wrong agent answer is matched against the
  signatures so the verdict is a **vector** (e.g. `C3: PASS, B1: FAIL`), not a
  boolean — this is what keeps conjunctive items (every revenue question also
  embeds CV-1) diagnostically clean.
- `kind: control` items are the easy twins: same capability, no trap. They
  separate *missing capability* (fails both) from *accident* (fails the trap
  only). Family F controls test the **inverse** calibration: they must be
  ANSWERED — refusal or asking is the failure.
- `requires_conventions` ties an item to `conventions.yml`: if a contract
  omits one of those conventions, the dependent items are unfair by
  construction.
- `probes: <convention-id>` marks the item as that convention's **prerequisite
  probe** (one per convention, consistency with `conventions.yml` validated by
  the builder). Probe fails → the convention is not held: dependent failures
  attributed to it are expected. Probe passes but a dependent item fails on
  that signature → **composition failure** (rule held in isolation, lost under
  complexity).
- `pass_criterion: numeric` items are compared within `tolerance`
  (exact / relative / absolute); `behavioural` items (family F traps) are
  human-scored against `expected_behaviour`.

## Building the answers

```bash
cd benchmark/generator
uv run fieldops-eval-build          # materialize + verify against FIELDOPS_GOLD
uv run fieldops-eval-build --verify-only
```

The builder executes every certified SQL and every signature SQL against
`PULSAR_DB.FIELDOPS_GOLD` (via `snow` CLI), writes `answers.yml`, and **asserts
each certified/signature pair diverges** beyond the item's tolerance — the
authoritative version of the generator's pre-flight checks
(`DIVERGENCE_CHECKS.md`). Re-run it after any dataset regeneration: stale
answers fail loudly instead of silently corrupting the eval.
