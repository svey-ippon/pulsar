# Streaming and Reasoning Design

How `pulsar-agent` handles LLM token streaming and Claude's reasoning text.

---

## Why Claude Reasons as Plain Tokens

Claude is an autoregressive model — it generates tokens one at a time, left to right. When a
question requires multiple steps (deciding which tool to call, interpreting results), the model
naturally produces reasoning-like text as ordinary tokens before committing to an action or a
final answer.

This is an emergent property of chain-of-thought training, not a togglable feature. There is no
structural separation between reasoning and response at the API level unless the extended-thinking
feature is explicitly enabled. The model "thinks out loud" in plain text, indistinguishable from
final answer text.

### The two moments where reasoning text appears

In a ReAct loop, reasoning tokens surface at two different points:

1. **Before a tool call** — the model generates text explaining why it will call a tool.
   This text lives inside an `AIMessage` that also carries `tool_calls`. `extract_text` in
   `pulsar_agent.extraction` skips such messages, so this reasoning never reaches the chat
   history. It is only visible through the live stream.

2. **Before the final answer** — the model may generate a preamble before the actual answer.
   This text lives in the last `AIMessage` (no tool calls) and is therefore concatenated with
   the final answer in `extract_text`.

The result is structurally ambiguous: reasoning text sometimes appears in history, sometimes not,
depending on where in the loop it was generated.

---

## How the UI Handles It

`stream_agent_events` buffers text chunks until LangGraph emits the complete `AIMessage` for the
current agent step. If that message has tool calls, the buffered text is emitted as
`reasoning_token`; if it is the final AI message without tool calls, the buffered text is emitted
as `answer_token`. The Streamlit app uses those classified events to build **reasoning blocks** —
an ordered sequence of text fragments and tool call records.

This gives a clean separation:

- The collapsed **reasoning details** status shows tool calls + any intermediate reasoning text.
- The visible **answer area** shows only the final answer text.

See `pulsar_agent.streaming.stream_agent_events` for how token and tool-call events are emitted,
and `pulsar_ui.reasoning.build_final_reasoning_blocks` for how the final blocks are assembled.

---

## Why the Agent Uses `.stream()` Not `.invoke()`

`make_agent_node` in `pulsar_agent.nodes` calls `llm_with_tools.stream(messages, config)` rather
than `invoke(...)`. This is deliberate: `.stream()` fires `on_chat_model_stream` callbacks as
each chunk arrives, which LangGraph captures as `("messages", chunk)` events when
`stream_mode="messages"` is set. `.invoke()` is blocking and never fires those callbacks, making
token-level streaming impossible.

---

## Decision: No Extended Thinking (for now)

Extended thinking adds a dedicated reasoning block to the API response with explicit start/end
markers and budget control. The trade-offs for this POC:

| | Extended thinking | Plain token streaming |
|---|---|---|
| Reasoning visibility | Explicit, structured | Implicit, mixed with output |
| Latency | Higher (reasoning budget consumed before output) | Lower |
| Cost | Higher | Lower |
| Streaming complexity | Lower (clear boundary) | Higher (must strip reasoning from answer) |
| Required for correctness | No — Claude reasons adequately without it | — |

Given that the current questions are answerable with 2–3 tool calls and the model reasons
reliably without extended thinking, the overhead is not justified at the POC stage.
