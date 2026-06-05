from __future__ import annotations

from pulsar_bare_agent.catalog import list_domain_ids
from pulsar_bare_agent.prompt import build_system_prompt


def test_prompt_lists_every_domain():
    prompt = build_system_prompt()
    domain_ids = list_domain_ids()
    assert "fieldops" in domain_ids
    for domain_id in domain_ids:
        assert domain_id in prompt


def test_prompt_declares_the_three_tools():
    prompt = build_system_prompt()
    for tool_name in ("describe_domain", "execute_sql", "display_table"):
        assert tool_name in prompt


def test_prompt_carries_no_domain_semantics():
    """Domain content (tables, keys, conventions) belongs to the contracts, not the prompt."""
    prompt = build_system_prompt()
    leaked = [
        token for token in (
            # Olist physical names / definitions
            "FCT_ORDERS", "ORDER_ID", "CUSTOMER_UNIQUE_ID", "DELAY_DAYS", "PULSAR_DB.GOLD",
            # FieldOps physical names / definitions
            "FCT_WORK_ORDERS", "WORK_ORDER_ID", "CALL_OUT_FEE", "SLA_DELAY_BDAYS",
        ) if token in prompt
    ]
    assert not leaked, f"domain-specific tokens leaked into the system prompt: {leaked}"
