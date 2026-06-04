"""Pre-flight divergence checks (FIELDOPS_SPEC.md §6.2).

Every certified/naive pair of the trap catalogue (§4) is asserted to diverge
beyond its threshold. A generation that fails any check must be rejected and
retuned — divergence is a verified property of the dataset, not a hope.

These pandas implementations are the *pre-flight* (fast iteration, no Snowflake
roundtrip); the authoritative asserts run against the built gold with the eval
items. Definitions must stay aligned with the dbt gold models (in particular
sla_delay_bdays = np.busday_count(promised, completed), signed).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CheckThresholds
from .dataset import Dataset


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    label: str
    value: str
    target: str
    passed: bool


def _dates(series: pd.Series) -> np.ndarray:
    return series.to_numpy().astype("datetime64[D]")


def _wo_revenue(ds: Dataset) -> pd.DataFrame:
    """Service revenue per completed WO = lines + call-out fee (CV-1)."""
    completed = ds.work_orders[ds.work_orders["completed_date"].notna()].copy()
    lines_total = ds.work_order_lines.groupby("work_order_id")["line_amount"].sum()
    completed["lines_amount"] = completed["work_order_id"].map(lines_total).fillna(0.0)
    completed["revenue"] = completed["lines_amount"] + completed["call_out_fee"]
    return completed


def run_checks(ds: Dataset, thresholds: CheckThresholds) -> list[CheckResult]:
    t = thresholds
    results: list[CheckResult] = []

    def add(check_id: str, label: str, value: str, target: str, passed: bool) -> None:
        results.append(CheckResult(check_id, label, value, target, passed))

    completed = _wo_revenue(ds)

    # A1 — clients vs sites: avg sites per client
    sites_per_client = ds.sites.groupby("client_id").size().mean()
    add(
        "A1", "avg sites per client", f"{sites_per_client:.2f}",
        f">= {t.a1_min_sites_per_client}", sites_per_client >= t.a1_min_sites_per_client,
    )

    # A2 — monthly service revenue (by completed month) vs collected payments (by paid month)
    revenue_m = completed.groupby(completed["completed_date"].dt.to_period("M"))["revenue"].sum()
    collected_m = ds.payments.groupby(ds.payments["paid_date"].dt.to_period("M"))[
        "payment_amount"
    ].sum()
    months = revenue_m[revenue_m > 0].index
    rel_diff = ((revenue_m[months] - collected_m.reindex(months).fillna(0.0)).abs() / revenue_m[months]).mean()
    add(
        "A2", "mean monthly |revenue - collected| / revenue", f"{rel_diff:.2%}",
        f">= {t.a2_min_monthly_rel_diff:.0%}", rel_diff >= t.a2_min_monthly_rel_diff,
    )

    # A3 — man-hours delivered vs elapsed on-site duration
    billed = ds.work_order_lines["billed_hours"].sum()
    duration = completed["duration_hours"].sum()
    ratio = billed / duration
    add(
        "A3", "sum(billed_hours) / sum(duration_hours)", f"{ratio:.2f}",
        f">= {t.a3_min_billed_over_duration}", ratio >= t.a3_min_billed_over_duration,
    )

    # B1 — call-out fee share of service revenue (CV-1)
    fee_share = completed["call_out_fee"].sum() / completed["revenue"].sum()
    lo, hi = t.b1_fee_share_range
    add(
        "B1", "call-out fee share of revenue", f"{fee_share:.2%}",
        f"in [{lo:.0%}, {hi:.0%}]", lo <= fee_share <= hi,
    )

    # B2 — certified late rate (busdays vs promised + grace) vs naive (calendar vs scheduled)
    delay_bd = np.busday_count(
        _dates(completed["promised_date"]), _dates(completed["completed_date"])
    )
    late_certified = (delay_bd > 2).mean()
    late_naive = (completed["completed_date"] > completed["scheduled_date"]).mean()
    gap_pts = abs(late_certified - late_naive) * 100
    add(
        "B2", f"late rate gap (certified {late_certified:.1%} vs naive {late_naive:.1%})",
        f"{gap_pts:.1f} pts", f">= {t.b2_min_late_rate_gap_pts} pts",
        gap_pts >= t.b2_min_late_rate_gap_pts,
    )

    # C2 — bridge inflation: unweighted category join double-counts WO revenue
    unit_cat = ds.equipment_units.set_index("equipment_unit_id")["equipment_category"]
    servicing = ds.work_order_servicing.copy()
    servicing["category"] = servicing["equipment_unit_id"].map(unit_cat)
    ncat = servicing.groupby("work_order_id")["category"].nunique()
    completed_ncat = completed["work_order_id"].map(ncat).fillna(1)
    inflation = (completed_ncat * completed["revenue"]).sum() / completed["revenue"].sum()
    add(
        "C2", "unweighted bridge total / true total", f"{inflation:.2f}",
        f">= {t.c2_min_bridge_inflation}", inflation >= t.c2_min_bridge_inflation,
    )

    # C3 — geography role-playing: share of WOs with site state != depot state
    state_by_zip = ds.geography.set_index("zip_code_prefix")["state"]
    site_state = ds.work_orders["site_id"].map(
        ds.sites.set_index("site_id")["zip_code_prefix"]
    ).map(state_by_zip)
    depot_state = ds.work_orders["technician_id"].map(
        ds.technicians.set_index("technician_id")["depot_code"]
    ).map(ds.depots.set_index("depot_code")["zip_code_prefix"]).map(state_by_zip)
    cross_share = (site_state != depot_state).mean()
    add(
        "C3", "share of WOs dispatched cross-state", f"{cross_share:.1%}",
        f">= {t.c3_min_cross_state_share:.0%}", cross_share >= t.c3_min_cross_state_share,
    )

    # D1 — header fee fan-out: avg lines per WO (among WOs with lines)
    lines_per_wo = ds.work_order_lines.groupby("work_order_id").size().mean()
    add(
        "D1", "avg lines per WO with lines", f"{lines_per_wo:.2f}",
        f">= {t.d1_min_lines_per_wo}", lines_per_wo >= t.d1_min_lines_per_wo,
    )

    # D3 — naive AVG over all survey rows vs latest-response-per-WO
    naive_avg = ds.surveys["satisfaction_score"].mean()
    latest = ds.surveys.sort_values("response_sequence").groupby("work_order_id").last()
    latest_avg = latest["satisfaction_score"].mean()
    gap = abs(latest_avg - naive_avg)
    add(
        "D3", f"survey avg gap (latest {latest_avg:.2f} vs naive {naive_avg:.2f})",
        f"{gap:.2f}", f">= {t.d3_min_survey_avg_gap}", gap >= t.d3_min_survey_avg_gap,
    )

    # E1 — open WOs (completed_date NULL)
    open_share = ds.work_orders["completed_date"].isna().mean()
    lo, hi = t.e1_open_share_range
    add(
        "E1", "share of open WOs", f"{open_share:.1%}",
        f"in [{lo:.0%}, {hi:.0%}]", lo <= open_share <= hi,
    )

    # E2 — labor lines (part_id NULL) share of all lines
    labor_share = (ds.work_order_lines["line_kind"] == "LABOR").mean()
    lo, hi = t.e2_labor_line_share_range
    add(
        "E2", "labor share of lines", f"{labor_share:.1%}",
        f"in [{lo:.0%}, {hi:.0%}]", lo <= labor_share <= hi,
    )

    return results


def format_report(results: list[CheckResult]) -> str:
    lines = ["Divergence pre-flight checks (FIELDOPS_SPEC.md §6.2):"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"  [{status}] {r.check_id}: {r.label} = {r.value} (target {r.target})")
    n_fail = sum(1 for r in results if not r.passed)
    lines.append(
        "All checks passed." if n_fail == 0 else f"{n_fail} check(s) FAILED — dataset rejected."
    )
    return "\n".join(lines)
