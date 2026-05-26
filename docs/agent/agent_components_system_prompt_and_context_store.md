# System prompt construction and state lifecycle

How the system prompt is built, when context is injected, and what is stateful vs stateless
across a multi-turn conversation in a LangGraph agent.

---

## Direct answers

**Is the system prompt recreated on every turn?**
Yes — on every single agent node call, including each loop iteration within a single user turn.
It is a cheap in-memory operation (string prepend). The LLM has no memory of it across calls;
it must be included every time.

**Is the new message appended to the state?**
Yes — this is exactly what the checkpointer does. On each `ainvoke`, LangGraph loads the full
message history for that `thread_id`, appends the new message, runs the graph, and saves the
updated state back.

The subtlety is **where context store retrieval fits into this**. That is the part worth getting right.

---

## Two-phase architecture

Each user turn has two distinct phases.

### Phase 1 — pre-graph (API layer, once per user message)

- Receive the user message.
- Retrieve relevant entries from the context store (glossary matches, verified queries, domain
  rules) based on the current question.
- Pass the result into the graph as a state field alongside the new user message.

This phase runs **once per user message**, not once per loop iteration.

### Phase 2 — LangGraph agent loop

- The checkpointer loads the full message history for the session.
- The new user message and retrieved context are appended to the state.
- The agent loop runs: agent node → tools node → agent node → … → END.
- On every agent node call, the system prompt is reconstructed: static text + context field from
  state. This is cheap and correct — the context does not change mid-loop.
- The checkpointer saves the updated state (full history + context field) when the loop ends.

On the next user turn, Phase 1 retrieves context for the **new** question, overwrites the context
field, and the cycle repeats. The message history from prior turns is carried forward automatically.

---

## What is stateless, what is not

| | Stateless (rebuilt every call) | Stateful (persisted in checkpointer) |
|---|---|---|
| Static system prompt text | ✓ | |
| Tool definitions and descriptions | ✓ | |
| LLM client | ✓ | |
| Context store retrieval result | Once per user message | ✓ stored in state |
| Full message history | | ✓ |
| Current turn's injected context | | ✓ |

**Key nuance:** context store retrieval is stateless work that produces a stateful result. You
retrieve once per user message, store the result in the state, and reuse it for all loop
iterations within that turn.

---

## Implementation

### Custom state

A dedicated `injected_context` field carries the retrieved context separately from messages.
This keeps concerns clean — message history and business context are two different things.

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    injected_context: str  # retrieved once per user turn, reused across loop iterations
```

### Agent node

Rebuilds the full system prompt on every call using the static text and the context field already
in state. No retrieval happens here.

```python
from langchain_core.messages import SystemMessage

STATIC_PROMPT = """You are an analytics assistant for our data platform.
- Always use the Semantic Layer tools first for any numeric question.
- Never invent metrics or dimensions not found via list_cubes / get_cube_schema.
- Always include the generated SQL in your final answer.
- If a question cannot be answered from modeled metrics, say so explicitly."""

async def agent_node(state: AgentState):
    system_prompt = STATIC_PROMPT
    if state.get("injected_context"):
        system_prompt += f"\n\n## Relevant business context\n{state['injected_context']}"

    messages = [SystemMessage(system_prompt)] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}
```

### Graph definition

```python
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres import PostgresSaver

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")

checkpointer = PostgresSaver(conn)  # persistent across server restarts
app = graph.compile(checkpointer=checkpointer)
```

### API layer — one call per user message

Context retrieval happens here, before the graph is invoked. The result is passed as a state
field and will overwrite the previous turn's context.

```python
async def handle_user_message(session_id: str, user_message: str):

    # 1. retrieve context for this specific question (once)
    context_chunks = await context_store.retrieve(user_message, top_k=5)
    injected_context = format_context(context_chunks)

    # 2. invoke graph — checkpointer loads prior history automatically
    result = await app.ainvoke(
        {
            "messages": [("user", user_message)],
            "injected_context": injected_context,  # overwrites the field each turn
        },
        config={"configurable": {"thread_id": session_id}},
    )

    return result["messages"][-1].content
```

---

## Why this pattern is correct

**Context retrieval runs once per user turn, not once per loop iteration.**
The agent loop can run 3–5 times for a single user question (agent → tools → agent → …).
The question has not changed mid-loop, so there is no reason to re-hit the vector store.
Storing the result in state makes it available to every iteration without redundant calls.

**The full conversation history is always available to the LLM.**
`add_messages` merges the new user message with the history loaded from the checkpointer.
Every agent node call within a turn sees the complete conversation, including prior tool results
from the current turn and all messages from prior turns.

**Context is always fresh for the current question.**
`injected_context` is overwritten on every call to `handle_user_message`. Turn 2's context
is relevant to the follow-up question, not to Turn 1's question. The checkpointer persists it
within a turn, but the API layer replaces it at the start of every new turn.

---

## System prompt anatomy

At any given agent node call the full prompt passed to the LLM is:

```
[SystemMessage]
  ├── static part    persona, policies, output conventions, tool usage rules
  └── dynamic part   glossary matches, verified queries, domain rules
                     retrieved from context store for the current user question

[HumanMessage]   Turn 1 user message
[AIMessage]      Turn 1 assistant response (may contain tool_calls)
[ToolMessage]    Turn 1 tool result(s)
[AIMessage]      Turn 1 final answer
[HumanMessage]   Turn 2 user message   ← current
```

The static part never changes. The dynamic part changes once per user turn.
The message history grows with every turn and is managed entirely by the checkpointer.
