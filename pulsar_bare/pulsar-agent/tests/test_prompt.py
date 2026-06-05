from __future__ import annotations

from pulsar_bare_agent.prompt import build_system_prompt


def test_prompt_lists_every_domain():
    prompt = build_system_prompt()
    assert "olist_sales" in prompt
    assert "fieldops" in prompt


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
