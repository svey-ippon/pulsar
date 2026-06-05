# FieldOps eval items

The benchmark's question set (FIELDOPS_SPEC.md §4/§7): **31 items** — 16 traps +
15 controls — across the six families of `TRAP_FAMILIES.md`.

## Layout

| File | Content |
|---|---|
| `ITEMS.md` | **Human-readable catalogue**: per family, what each item tests, the verbatim question, the required conventions. |
| `items/family_*.yml` | **Authored, frozen.** Questions, certified SQL, naive signatures, pass criteria. Never edited after materialization without rebuilding answers. |
| `conventions.yml` | The conventions the SEMANTIC MODEL must define — coverage checklist for `fieldops.yaml` (pulsar) and the semantic view (SI). Each convention lists the items that depend on it. |
| `instructions.yml` | The behaviours the AGENT INSTRUCTIONS must prescribe (family F) — coverage checklist for the pulsar system prompt and the SI agent `instructions`. |
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
- `requires_conventions` ties an item to `conventions.yml`: conventions the
  semantic model must DEFINE for the question to be answerable. Not a tested
  capability — but without the convention defined in the contract, there is no
  correct answer, and the failure is the contract author's, not the agent's.
- `requires_instructions` (family F) ties an item to `instructions.yml`: the
  same idea one layer up — behaviours the agent instructions must PRESCRIBE
  (state what's missing, raise ambiguity, disclose ad-hoc figures). The
  *detection* of absence/ambiguity stays a tested semantic capability; only
  the response form is prescribed.
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
