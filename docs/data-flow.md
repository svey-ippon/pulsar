# Data Flow: Question to Chart

How a user question becomes a chart or table in the Streamlit UI.

---

## Example question

> "What is the total revenue per month?"

---

## Step 1 — The agent queries Cube

`stream_question` runs the LangGraph ReAct loop. The LLM calls `list_cubes` to read the
schema, then calls `query_cube` with the appropriate measures and dimensions.

Inside `tool_node`, each `query_cube` call is executed and its result is **immediately
captured into the graph state** as a `QueryResult`:

```python
# tool_node (agent/graph.py)
result_str = tools_by_name["query_cube"].invoke(tc["args"])
parsed = json.loads(result_str)
if isinstance(parsed, list):
    new_results.append({"query": tc["args"], "data": parsed})
```

The raw JSON string is also stored as a `ToolMessage` so the LLM can read it. At the same
time, the structured `QueryResult` is appended to `state["cube_results"]` via the
`operator.add` reducer — no scanning or ID-matching needed later.

If the agent calls `query_cube` twice (e.g. revenue per month AND average review score), both
results accumulate independently in `cube_results`.

---

## Step 2 — Answer assembly

After the graph finishes, `stream_question` reads directly from the final state:

```python
{
    "text":    _extract_text(last_state["messages"]),   # last AIMessage without tool_calls
    "results": last_state["cube_results"][prev_count:], # only results from this turn
}
```

`prev_count` is the number of `cube_results` already saved from previous turns (via the
`MemorySaver` checkpointer). Slicing from that index isolates the current turn's results.

For the revenue question, `results` contains one entry:

```python
[
    {
        "query": {
            "measures": ["order_items.total_revenue"],
            "timeDimensions": [{"dimension": "orders.order_purchase_timestamp", "granularity": "month"}]
        },
        "data": [
            {"orders.order_purchase_timestamp.month": "2017-01-01T00:00:00.000", "order_items.total_revenue": 12450.50},
            {"orders.order_purchase_timestamp.month": "2017-02-01T00:00:00.000", "order_items.total_revenue": 18230.75},
            ...
        ]
    }
]
```

---

## Step 3 — `render_answer` dispatches per result

```python
def render_answer(answer: dict) -> None:
    st.write(answer["text"])           # LLM prose explanation
    for result in answer["results"]:
        render_chart(result["data"])   # chart or table
        with st.expander("Show Cube query"):
            st.json(result["query"])   # auditable query dict
```

Each `QueryResult` gets its own visualisation block. If the agent ran two queries, two
charts appear sequentially below the prose answer.

---

## Step 4 — `render_chart` picks the visualisation

The column names returned by Cube encode their type:

- A column ending in `.month` (or another granularity) is a **time axis**.
- A column whose values are numeric is a **measure**.

```
df columns: ["orders.order_purchase_timestamp.month", "order_items.total_revenue"]
              └── ends with ".month" → time_col          └── numeric → value_col
```

Decision tree:

```
time column AND numeric column?
  └── yes → px.line(x=time_col, y=value_col)          ← revenue per month

numeric column but no time column?
  └── yes → px.bar(x=first_col, y=value_col)           ← avg review score per state

neither?
  └── st.dataframe(df)                                  ← purely categorical output
```

Below the chart, `st.expander("Show raw data")` always renders the full DataFrame.

---

## What happens when there is no data

For refusal answers (predictions, unsupported metrics, Cube errors), the agent returns:

```python
{"text": "I can't make predictions...", "results": []}
```

`render_answer` calls `st.write(text)` only — the `for result in results` loop has nothing
to iterate, and no chart or expander appears.

---

## Full flow summary

```
User question
    │
    ▼
stream_question()
    │
    ├── [tool_call: list_cubes]  → st.status "Fetching schema..."
    ├── [tool_call: query_cube]  → st.status "Querying data..."
    │       └── Cube /load → list[dict] rows
    │               └── tool_node captures → state["cube_results"] += [QueryResult]
    │
    └── answer assembly
            ├── text    ← _extract_text(messages): last AIMessage, current turn
            └── results ← state["cube_results"][prev_count:]
                    │
                    ▼
            render_answer(answer)
                    │
                    ├── st.write(text)
                    └── for each result:
                            ├── render_chart(result["data"])
                            │       ├── time + numeric  → px.line
                            │       ├── numeric only   → px.bar
                            │       └── other          → st.dataframe
                            └── st.expander → st.json(result["query"])
```
