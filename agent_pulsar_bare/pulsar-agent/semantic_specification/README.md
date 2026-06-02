# Semantic contract — specification

The **agent-facing semantic contract** is a per-domain YAML (the active one is
[`../src/pulsar_bare_agent/semantic/fieldops.yaml`](../src/pulsar_bare_agent/semantic/fieldops.yaml),
format `version: 2`) that the agent reads through `describe_domain(domain_id)`. Unlike a
Snowflake Semantic View it does **not** constrain execution — the agent still writes raw SQL.
The contract's only job is to give the model the business meaning, grain, join and metric
guidance it cannot infer from a well-named schema, so it generates correct SQL.

## The one guiding principle

> **A field earns its place only when it varies and changes the SQL the agent writes.**
> Constant, always-true, or trivially-derivable values are prompt noise — omit them.

Everything in these docs is an application of that rule.

## The three documents

| Doc | Answers |
|---|---|
| [`CONTRACT_SPEC.md`](CONTRACT_SPEC.md) | **How to author a contract** — the format (fields + enums), when/why to fill each field, and where each piece of information lives. |
| [`AGENT_USAGE.md`](AGENT_USAGE.md) | **How the agent must consume it** — the runtime behaviour rules (metric authority, joins/grain, disclosure). Source of truth for `prompt.py`. |

The list of deferred format enrichments (relationships, join_paths, derived-concept
registry, …) lives in the roadmap:
[`../../../00-doc/agents/agent_pulsar_bare/next_steps.md`](../../../00-doc/agents/agent_pulsar_bare/next_steps.md).
