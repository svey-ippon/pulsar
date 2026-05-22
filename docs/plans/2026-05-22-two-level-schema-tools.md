# Implementation Plan: Two-Level Schema Discovery Tools

**Date:** 2026-05-22  
**Branch:** feat/desc_tools_2_levels

---

## Goal

Split the current `list_cubes` tool (which returns the full semantic model — all cubes, all measures, all dimensions) into two focused tools:

| Tool | Input | Output | LLM usage |
|---|---|---|---|
| `list_cubes` | — | `[{name, title, summary}]` for all cubes | Orient: which cube is relevant? |
| `get_cube_schema` | `cube_name: str` | Full schema for one cube: description, measures, dimensions | Inspect before querying |

The LLM's natural workflow becomes: call `list_cubes` once → identify the relevant cube(s) → call `get_cube_schema(cube_name)` for each → call `query_cube`.

This reduces token cost when the schema is large and focuses the LLM's attention on only the relevant cube.

---

## Required background: the brainstorm doc

`docs/brainstorming/2026-05-22-desc_tools_two_levels.md` proposed two new YAML fields:

- `meta.summary` (≤ 120 chars) — one-liner used by `list_cubes`
- `description` (multi-line prose) — already present in all cubes, used by `get_cube_schema`

Both are read from the same `/v1/meta` endpoint. No new Cube endpoint needed.

---

## Files to change

### 1. `cube/model/cubes/*.yml` — add `meta.summary` to all 9 cubes

Add a `meta:` block with a `summary` field to each cube. The `description` field is already present and does not need changes.

| Cube file | `meta.summary` value |
|---|---|
| `orders.yml` | `"Customer orders, one row per order; grain is order_id. Links to items, payments, reviews, and customers."` |
| `order_items.yml` | `"Line items within orders, one row per (order, item) pair. Tracks merchandise price and freight per item."` |
| `order_payments.yml` | `"Payments per order, one row per payment method used. payment_value includes freight and adjustments."` |
| `order_reviews.yml` | `"Post-delivery satisfaction surveys, one row per review. Provides avg_review_score (1–5) and review_count."` |
| `customers.yml` | `"Buyer profiles, one row per order-customer pair. Use customer_unique_id for repeat-buyer analysis."` |
| `sellers.yml` | `"Seller profiles, one row per seller. Geographic dimensions: seller_state, seller_city."` |
| `products.yml` | `"Product catalog, one row per product. Category names are in Portuguese; join translation cube for English."` |
| `product_category_name_translation.yml` | `"Lookup table: Portuguese product_category_name → English product_category_name_english."` |
| `geolocation.yml` | `"Brazilian zip code prefixes mapped to lat/lon, city, and state. Grain is zip prefix (5 digits)."` |

**Placement in YAML:** insert `meta:` immediately after the cube `name:`, before `sql_table:`.

```yaml
cubes:
  - name: orders
    meta:
      summary: "Customer orders, one row per order; ..."
    sql_table: ECOMMERCE_DB.MARTS.ORDERS
    description: >
      ...existing description unchanged...
```

---

### 2. `agent/cube_client.py` — add `get_cube_schema` method

**New method on `CubeClient`:**

```python
def get_cube_schema(self, cube_name: str) -> dict[str, Any]:
```

- Calls `self._get_meta()` (extract the `/meta` fetch into a private method to avoid a second HTTP round-trip when both tools are called in one turn — but since LangGraph calls tools sequentially this is not critical; a simple re-call is acceptable for now)
- Finds the cube by `name == cube_name`
- Raises `ValueError(f"Cube '{cube_name}' not found. Available: {names}")` if not found — the tool layer converts this to a structured error JSON
- Returns:

```python
{
    "name": str,
    "title": str,
    "description": str,
    "measures": [{"name": str, "type": str, "description": str}, ...],
    "dimensions": [{"name": str, "type": str, "description": str}, ...],
}
```

**`SupportsCubeQueries` protocol:** add `get_cube_schema(self, cube_name: str) -> dict[str, Any]`.

The existing `list_cubes() -> dict[str, Any]` method **stays unchanged** — it returns the raw `/meta` JSON that the `list_cubes` tool will filter down to summaries. This avoids having to update tests that call `client.list_cubes()` directly.

---

### 3. `agent/tools.py` — rework `list_cubes` tool, add `get_cube_schema` tool

**`list_cubes` tool (changed):**

- Docstring: "Return a lightweight list of all cubes. Each entry has name, title, and a one-line summary. Call this to identify which cube(s) are relevant, then call get_cube_schema for details before querying."
- Implementation: call `client.list_cubes()`, then extract summaries:
  - `summary = (cube.get("meta") or {}).get("summary")` — prefer `meta.summary`
  - Fallback (cube not yet migrated): `desc.split(".")[0].strip() + "."` from `description`
  - If neither: `"(no description)"`
- Return: `json.dumps([{"name": ..., "title": ..., "summary": ...}, ...])`

**`get_cube_schema` tool (new):**

```python
class GetCubeSchemaArgs(BaseModel):
    cube_name: str = Field(description="Exact cube name as returned by list_cubes().")
```

- Docstring: "Return the full schema for a single cube: description, all measures, all dimensions with types and descriptions. Call this after list_cubes() has identified the relevant cube, before calling query_cube."
- Calls `client.get_cube_schema(cube_name)`
- On `ValueError` (cube not found): return `json.dumps({"error": "...", "available_cubes": [...]})`
- On `CubeServiceError`: return `_UNAVAILABLE`
- Return: `json.dumps(schema_dict)`

**`make_tools` returns 3 tools:** `[list_cubes, get_cube_schema, query_cube]`

Note: the `query_cube` tool docstring currently says "Use only member names returned by list_cubes()." — update to "Use only member names returned by get_cube_schema()."

---

### 4. `agent/prompt.py` — update Rule 1

Current Rule 1: "Call list_cubes first if schema not in history; reuse if already present."

New Rule 1: "To discover the schema: first call list_cubes to see all cubes and their summaries, then call get_cube_schema(cube_name) for the specific cube(s) you need before querying. Reuse schema already in the message history — do not call list_cubes or get_cube_schema again if the relevant cube's schema is already there."

---

### 5. `tests/test_agent_tools.py` — update and extend

**Update `FakeCubeClient`:**

```python
def get_cube_schema(self, cube_name: str) -> dict:
    cubes = self.metadata.get("cubes", [])
    cube = next((c for c in cubes if c["name"] == cube_name), None)
    if cube is None:
        raise ValueError(f"Cube '{cube_name}' not found.")
    return {
        "name": cube["name"],
        "title": cube.get("title", cube["name"]),
        "description": cube.get("description", ""),
        "measures": [{"name": m["name"], "type": m.get("type", ""), "description": m.get("description", "")} for m in cube.get("measures", [])],
        "dimensions": [{"name": d["name"], "type": d.get("type", ""), "description": d.get("description", "")} for d in cube.get("dimensions", [])],
    }
```

**Also update `ErrorCubeClient`:**

```python
def get_cube_schema(self, cube_name: str) -> dict:
    raise CubeServiceError("unavailable")
```

**New tests to add:**

- `test_list_cubes_tool_returns_summaries_not_full_schema` — verify the tool returns `[{name, title, summary}]` without measures/dimensions
- `test_list_cubes_tool_falls_back_to_description_when_summary_missing` — metadata with no `meta.summary`, verify fallback to first sentence
- `test_get_cube_schema_tool_returns_full_schema_for_known_cube`
- `test_get_cube_schema_tool_returns_error_json_for_unknown_cube`
- `test_get_cube_schema_tool_returns_error_json_when_cube_unavailable`
- `test_make_tools_returns_three_tools_with_correct_names` — update from 2 to 3

**Update existing tests:**

- `test_list_cubes_tool_calls_client_and_returns_metadata` → rename and update assertion to check for `[{name, summary}]` shape
- `test_make_tools_does_not_require_env_vars_when_client_is_injected` → expect 3 tools, check names include `get_cube_schema`
- `test_make_tools_returns_two_tools_with_correct_names` → update to 3 tools and correct names

---

### 6. `tests/test_cube_model.py` — add `meta.summary` lint check

Add a new test:

```python
def test_all_cube_models_have_meta_summary():
    for path in sorted(CUBE_MODEL_DIR.glob("*.yml")):
        cube = load_cube(str(path.relative_to(ROOT)))
        summary = (cube.get("meta") or {}).get("summary")
        assert summary, f"{path.name} is missing meta.summary"
        assert len(summary) <= 120, (
            f"{path.name} meta.summary exceeds 120 chars ({len(summary)})"
        )
```

---

### 7. `tests/test_agent_graph.py` — update `FakeCubeClient`

The `FakeCubeClient` in this file implements `SupportsCubeQueries`. Add `get_cube_schema`:

```python
def get_cube_schema(self, cube_name: str) -> dict:
    return {"name": cube_name, "title": cube_name, "description": "", "measures": [], "dimensions": []}
```

---

## Files NOT affected

| File | Reason |
|---|---|
| `agent/graph.py` | Tools are injected via `make_tools`; graph routing logic unchanged |
| `agent/memory.py` | Unrelated |
| `app/main.py` | Tool status label for `get_cube_schema` is handled by the existing `tool_call` event path; the label mapping may need a new entry (`get_cube_schema` → `"Fetching cube details..."`) |
| `cube/docker-compose.yml` | Unrelated |

Wait — `app/main.py` does have a label mapping for tool names. Check and add `get_cube_schema → "Fetching cube details..."`.

---

## Execution order

1. YAML files (no code dependencies)
2. `cube_client.py` (no tool dependencies)
3. `tools.py` (depends on client)
4. `prompt.py` (independent, but logically follows tools)
5. `app/main.py` tool label (independent)
6. Tests (validate all of the above)

Run `uv run pytest tests -v` after step 6 — all 32 existing tests should still pass plus the new ones.

---

## Out of scope

- Caching the `/meta` response within a request to avoid double-fetching (not critical for a POC)
- Linting the YAML summaries at CI time (the `test_cube_model.py` test covers it)
- Changing `query_cube` signature or behavior
