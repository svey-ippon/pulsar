# Extended Thinking: Decision and Implications

## Why Claude Reasons Without Extended Thinking

Claude is an autoregressive language model — it generates tokens one by one, left to right. When the question is complex or requires several steps (e.g. deciding which tool to call, interpreting results), the model naturally produces reasoning-like text as ordinary tokens before committing to an action or a final answer.

This behaviour is not a feature that can be toggled on or off: it is an emergent property of the way the model was trained (RLHF with chain-of-thought). The model "thinks out loud" as plain text, indistinguishably from the final answer text. There is no structural separation between reasoning and response at the API level unless extended thinking is explicitly enabled.

Concretely, in a ReAct agent loop there are two moments where this reasoning text appears:

1. **Before each tool call** — the model generates text explaining why it is going to call a tool. This text lives inside an `AIMessage` that also carries `tool_calls`, so it is filtered out by `_extract_text` and never reaches the chat history.
2. **Before the final answer** — the model may generate a preamble before the actual answer. This text lives in the last `AIMessage` (no tool calls) and therefore ends up concatenated with the final answer in the chat history.

The result is unpredictable from a UI perspective: reasoning text sometimes appears in the history, sometimes not, depending on where in the loop it was generated.
