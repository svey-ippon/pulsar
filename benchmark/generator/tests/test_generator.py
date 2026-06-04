"""Generator tests: determinism, lifecycle invariants, divergence checks.

A small config keeps the fast tests fast; the divergence checks run on the full
default config because they are properties of the real dataset.
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from fieldops_generator import GeneratorConfig, generate
from fieldops_generator.checks import run_checks

SMALL = dataclasses.replace(
    GeneratorConfig(), n_clients=24, n_technicians=30, n_parts=60, n_work_orders=600
)


@pytest.fixture(scope="module")
def small_ds():
    return generate(SMALL)


@pytest.fixture(scope="module")
def full_ds():
    return generate(GeneratorConfig())


def test_same_seed_is_byte_identical(small_ds):
    again = generate(SMALL)
    for name, frame in small_ds.tables().items():
        pd.testing.assert_frame_equal(frame, again.tables()[name])


def test_milestones_are_ordered(small_ds):
    wo = small_ds.work_orders
    assert (wo["promised_date"] >= wo["opened_date"]).all()
    assert (wo["scheduled_date"] >= wo["opened_date"]).all()
    started = wo[wo["started_date"].notna()]
    assert (started["started_date"] >= started["scheduled_date"]).all()
    done = wo[wo["completed_date"].notna()]
    assert (done["completed_date"] >= done["started_date"]).all()
    validated = wo[wo["validated_date"].notna()]
    assert (validated["validated_date"] >= validated["completed_date"]).all()


def test_open_wos_have_no_downstream_activity(small_ds):
    wo = small_ds.work_orders
    open_ids = set(wo.loc[wo["completed_date"].isna(), "work_order_id"])
    assert open_ids.isdisjoint(set(small_ds.payments["work_order_id"]))
    assert open_ids.isdisjoint(set(small_ds.surveys["work_order_id"]))
    assert wo.loc[wo["completed_date"].isna(), "duration_hours"].isna().all()
    not_started_ids = set(wo.loc[wo["started_date"].isna(), "work_order_id"])
    assert not_started_ids.isdisjoint(set(small_ds.work_order_lines["work_order_id"]))


def test_line_kinds_are_consistent(small_ds):
    lines = small_ds.work_order_lines
    part_lines = lines[lines["line_kind"] == "PART"]
    labor_lines = lines[lines["line_kind"] == "LABOR"]
    assert part_lines["part_id"].notna().all()
    assert part_lines["billed_hours"].isna().all()
    assert labor_lines["part_id"].isna().all()
    assert (labor_lines["billed_hours"] > 0).all()


def test_payments_settle_the_invoice(small_ds):
    """Collected never exceeds the invoice (lines + fee); most WOs settle exactly.

    Late payment rows are dropped at the window edge, so equality cannot hold
    everywhere — but it must hold for the bulk of paid WOs.
    """
    wo = small_ds.work_orders.set_index("work_order_id")
    lines = small_ds.work_order_lines.groupby("work_order_id")["line_amount"].sum()
    paid = small_ds.payments.groupby("work_order_id")["payment_amount"].sum()
    invoice = (
        lines.reindex(paid.index).fillna(0.0) + wo.loc[paid.index, "call_out_fee"]
    ).round(2)
    assert (paid <= invoice + 0.02).all()
    assert ((paid - invoice).abs() < 0.02).mean() > 0.6


def test_servicing_units_belong_to_the_wo_site(small_ds):
    site_of_unit = small_ds.equipment_units.set_index("equipment_unit_id")["site_id"]
    site_of_wo = small_ds.work_orders.set_index("work_order_id")["site_id"]
    servicing = small_ds.work_order_servicing
    assert (
        servicing["equipment_unit_id"].map(site_of_unit).to_numpy()
        == servicing["work_order_id"].map(site_of_wo).to_numpy()
    ).all()


def test_default_config_passes_all_divergence_checks(full_ds):
    results = run_checks(full_ds, GeneratorConfig().thresholds)
    failed = [r for r in results if not r.passed]
    assert not failed, [f"{r.check_id}: {r.label} = {r.value} (target {r.target})" for r in failed]
