# pulsar-web

React + Vite chat UI for `pulsar_bare`: multi-conversation chat, token-streamed answers, live
tool calls, and rendered result tables / ECharts charts. It talks to
[`pulsar-bare-api`](../pulsar-api) over HTTP/SSE (the dev server proxies `/api` to it).

## How it works

An assistant turn is a list of **segments** (text, tool call, table, chart, error). As SSE
events arrive, `applyEvent` (in `App.tsx`) folds each event into that segment list, and the
components render it. Charts are **consent-first**: a proposal renders a `ChartProposalCard`;
only on **accept** (persisted via the API) does it become a `ChartCard`.

## File map (`src/`)

| File | Responsibility |
|---|---|
| `main.tsx` | React root / mount. |
| `App.tsx` | Top-level state: threads + the streaming chat loop; `applyEvent` reduces SSE events into segments. |
| `api.ts` | API client — thread CRUD, `acceptChart`, and `streamQuestion` (an async generator over the SSE stream). |
| `types.ts` | Shared types: `Segment`, `StreamEvent`, `TableData`, `ChartData`, `ThreadMeta`, … |
| `chartOption.ts` | Builds the ECharts option object from a `ChartData`. |
| `components/` | Presentational pieces (see below). |
| `index.css` | Tailwind entry. |

### `components/`

| Component | Renders |
|---|---|
| `Sidebar` | Thread list + new/delete conversation. |
| `Chat` | The message thread (maps segments → cards). |
| `ToolChip` | A live tool call (`describe_domain`, `execute_sql`, …) with its summary. |
| `SqlBlock` | Executed SQL (syntax-highlighted). |
| `TableCard` | A result table. |
| `ChartProposalCard` / `ChartCard` | The chart consent offer / the accepted chart. |
| `EChart` | Thin ECharts wrapper. |
| `Markdown` | Assistant prose (react-markdown + GFM). |

## Dev

```bash
npm install
npm run dev      # http://localhost:5173  (proxies /api → the API on :8000)
npm run build    # tsc -b && vite build → dist/
npm run lint
```

Key deps: `react`, `echarts`, `react-markdown` + `remark-gfm`, `tailwindcss`. See the folder
[`../README.md`](../README.md) for the full stack and how to run it end to end.
