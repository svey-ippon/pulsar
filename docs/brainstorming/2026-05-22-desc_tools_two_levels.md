# Cube Schema — Two-Level Description Convention

## Rationale

The semantic layer exposes two tools with different verbosity needs:

| Tool | Purpose | Description depth needed |
|---|---|---|
| `list_cubes` | Orient the agent — which cube is relevant? | One-liner summary |
| `get_cube_schema` | Inspect a specific cube in detail | Full prose + join hints |

Cube.js has no native two-level description field, but its `meta` dictionary is
arbitrary key/value data that the `/v1/meta` endpoint returns as-is. The
convention below uses `meta.summary` for the short description and the
top-level `description` field for the long one.

---

## YAML Convention

### Rule

Every cube **must** declare both fields:

| Field | Type | Max length | Content |
|---|---|---|---|
| `meta.summary` | string | 120 chars | One sentence: what the cube contains and its key grain |
| `description` | multi-line string | no limit | Full prose: coverage, caveats, joinable cubes, recommended filters |

### Template

```yaml
cubes:
  - name: <cube_name>

    meta:
      # Required. One sentence, ≤ 120 chars.
      # Answer: "What is this cube and what is its grain?"
      summary: "<short description>"

    description: |
      <Full description — cover the following points:>
      - What business entity/event this cube models.
      - Date range or coverage (e.g. "since 2020", "trailing 90 days").
      - Any pre-filtering or deduplication applied in the SQL view.
      - Which cubes can be joined and via which dimension.
      - Measures or dimensions that require a mandatory filter.

    sql_table: "<schema>.<table_or_view>"

    joins:
      ...

    measures:
      ...

    dimensions:
      ...
```

### Concrete example

```yaml
cubes:
  - name: orders

    meta:
      summary: "Customer orders since 2020, one row per order, cancellations excluded."

    description: |
      Models confirmed customer orders placed from January 2020 onward.
      Cancelled and test orders are filtered out at the view level — do not
      add an extra status filter unless you need a specific sub-status.

      Join surface:
        - customers  →  orders.customer_id = customers.id
        - products   →  orders.product_id  = products.id  (one product per row)

      Mandatory filter: always restrict to a time range on `orders.created_at`
      when querying revenue measures; full-table scans are blocked by row-level
      security on the Snowflake side.

    sql_table: "analytics.orders_v2"
```

---

## Linting rule

Add the following check to your schema validation pipeline to enforce the
convention on every cube:

```python
def lint_cube(cube: dict) -> list[str]:
    errors = []

    summary = (cube.get("meta") or {}).get("summary")
    if not summary:
        errors.append(f"[{cube['name']}] meta.summary is missing")
    elif len(summary) > 120:
        errors.append(
            f"[{cube['name']}] meta.summary exceeds 120 chars ({len(summary)})"
        )

    if not cube.get("description", "").strip():
        errors.append(f"[{cube['name']}] description is missing")

    return errors
```

---

## Using the Cube API in `list_cubes` and `get_cube_schema`

Both tools hit the same endpoint; they differ only in what they extract and
return to the agent.

### Endpoint

```
GET /cubejs-api/v1/meta
Authorization: Bearer <CUBE_API_TOKEN>
```

The response contains a `cubes` array. Each element has at minimum:

```json
{
  "name": "orders",
  "title": "Orders",
  "description": "...",
  "meta": { "summary": "..." },
  "measures": [...],
  "dimensions": [...]
}
```

---

### `list_cubes` implementation

Returns only names and summaries. Falls back to the first sentence of
`description` when `meta.summary` is absent, so the tool degrades gracefully
on cubes that haven't been migrated to the convention yet.

```python
import httpx

def list_cubes(base_url: str, api_token: str) -> list[dict]:
    """
    Returns a lightweight list of all cubes.

    Each entry:
        {
            "name":    str,   # cube identifier used in query_cube / get_cube_schema
            "title":   str,   # human-readable display name
            "summary": str,   # one-liner from meta.summary (or first sentence fallback)
        }
    """
    response = httpx.get(
        f"{base_url}/cubejs-api/v1/meta",
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=15,
    )
    response.raise_for_status()

    cubes = response.json().get("cubes", [])

    result = []
    for cube in cubes:
        summary = (cube.get("meta") or {}).get("summary")
        if not summary:
            # Graceful fallback: use the first sentence of description
            desc = cube.get("description", "")
            summary = desc.split(".")[0].strip() + "." if desc else "(no description)"

        result.append({
            "name":    cube["name"],
            "title":   cube.get("title", cube["name"]),
            "summary": summary,
        })

    return result
```

**Token footprint:** proportional to the number of cubes × ~80 chars each.
On a schema with 40 cubes this is roughly 400 tokens — safe to pass in full
to the agent.

---

### `get_cube_schema` implementation

Returns the full definition of a single cube. The agent calls this after
`list_cubes` once it has identified a candidate.

```python
def get_cube_schema(base_url: str, api_token: str, cube_name: str) -> dict:
    """
    Returns the full schema of one cube.

    Output shape:
        {
            "name":        str,
            "title":       str,
            "description": str,
            "measures": [
                {"name": str, "type": str, "description": str},
                ...
            ],
            "dimensions": [
                {"name": str, "type": str, "description": str},
                ...
            ],
        }

    Raises ValueError if cube_name is not found.
    """
    response = httpx.get(
        f"{base_url}/cubejs-api/v1/meta",
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=15,
    )
    response.raise_for_status()

    cubes = response.json().get("cubes", [])

    cube = next((c for c in cubes if c["name"] == cube_name), None)
    if cube is None:
        raise ValueError(
            f"Cube '{cube_name}' not found. "
            f"Available cubes: {[c['name'] for c in cubes]}"
        )

    def extract_field(item: dict) -> dict:
        return {
            "name":        item["name"],
            "type":        item.get("type", "unknown"),
            "description": item.get("description", ""),
        }

    return {
        "name":        cube["name"],
        "title":       cube.get("title", cube["name"]),
        "description": cube.get("description", ""),
        "measures":    [extract_field(m) for m in cube.get("measures", [])],
        "dimensions":  [extract_field(d) for d in cube.get("dimensions", [])],
    }
```

**Token footprint:** one cube schema with 10 measures and 15 dimensions is
roughly 600–900 tokens depending on description verbosity — still well within
a single tool-call response budget.

---

## Summary

```
meta.summary   →  list_cubes    →  agent orientation   (shallow, cheap)
description    →  get_cube_schema →  full schema detail  (deep, on demand)
```

Both fields are authored in the YAML, validated by the linter, and read from
the same `/v1/meta` response. No second endpoint, no schema duplication.
