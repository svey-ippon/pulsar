"""Generator configuration.

All simulation knobs live here so the generate -> check -> retune loop of
FIELDOPS_SPEC.md §6.2 is a matter of editing one frozen dataclass. Every check
threshold (see checks.py) maps to one or more knobs below; the mapping is noted
in comments.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CheckThresholds:
    """Divergence thresholds asserted by the pre-flight checks (spec §4 / §6.2)."""

    a1_min_sites_per_client: float = 3.0
    a2_min_monthly_rel_diff: float = 0.15
    a3_min_billed_over_duration: float = 1.3
    b1_fee_share_range: tuple[float, float] = (0.09, 0.16)
    b2_min_late_rate_gap_pts: float = 5.0
    c2_min_bridge_inflation: float = 1.2
    c3_min_cross_state_share: float = 0.40
    d1_min_lines_per_wo: float = 3.0
    d3_min_survey_avg_gap: float = 0.25
    e1_open_share_range: tuple[float, float] = (0.07, 0.13)
    e2_labor_line_share_range: tuple[float, float] = (0.35, 0.45)


@dataclass(frozen=True)
class GeneratorConfig:
    """All simulation parameters, with the spec requirement each one serves."""

    seed: int = 1042

    # ── Time window (spec §6.4: 3 full fictional years) ────────────────────
    start_date: str = "2017-01-01"
    end_date: str = "2019-12-31"

    # ── Volumes (spec §6.4) ─────────────────────────────────────────────────
    n_clients: int = 120
    n_technicians: int = 80
    n_parts: int = 200
    n_work_orders: int = 10_000

    # ── Clients & sites (A1: avg sites/client >= 3) ─────────────────────────
    # sites drawn uniformly in [lo, hi] per contract tier
    sites_per_tier: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {"standard": (1, 3), "premium": (2, 6), "enterprise": (5, 15)}
    )
    tier_probs: dict[str, float] = field(
        default_factory=lambda: {"standard": 0.50, "premium": 0.35, "enterprise": 0.15}
    )

    # ── Equipment (C2: multi-category WOs) ──────────────────────────────────
    units_per_site: tuple[int, int] = (2, 12)
    # how many units a WO services: P(k) for k = 1..4 (drives distinct categories)
    units_serviced_probs: tuple[float, ...] = (0.50, 0.25, 0.15, 0.10)

    # ── Work-order mix ───────────────────────────────────────────────────────
    wo_type_probs: dict[str, float] = field(
        default_factory=lambda: {"corrective": 0.55, "preventive": 0.35, "inspection": 0.10}
    )
    priority_probs: dict[str, float] = field(
        default_factory=lambda: {"critical": 0.15, "high": 0.35, "standard": 0.50}
    )
    # weekly/seasonal arrival shape (Jan..Dec multipliers; climate peak in summer)
    month_weights: tuple[float, ...] = (
        0.90, 0.85, 0.95, 1.00, 1.05, 1.20, 1.30, 1.25, 1.05, 0.95, 0.90, 1.00,
    )
    weekend_open_weight: float = 0.09  # most WOs are opened on business days

    # ── Lifecycle (B2/CV-3, E1) ──────────────────────────────────────────────
    # SLA promise in business days after opening, per priority (before jitter)
    sla_busdays: dict[str, int] = field(
        default_factory=lambda: {"critical": 3, "high": 7, "standard": 12}
    )
    # scheduling lead time in calendar days, uniform [lo, hi] per priority
    schedule_days: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {"critical": (1, 5), "high": (2, 10), "standard": (3, 14)}
    )
    start_after_scheduled_probs: tuple[float, ...] = (0.70, 0.20, 0.10)  # +0/+1/+2 days
    complete_after_started_probs: tuple[float, ...] = (0.75, 0.18, 0.07)  # +0/+1/+2 days
    # parts-on-backorder overruns: pushes certified lateness to a realistic level
    p_overrun: float = 0.18
    overrun_days: tuple[int, int] = (4, 18)
    # E1: open (not completed) WOs ~10%, concentrated near the window end
    open_tail_days: int = 60
    p_open_tail: float = 0.75
    p_open_base: float = 0.045
    p_open_started: float = 0.45  # share of open WOs that have at least started
    # validation lag (completed -> validated), in business days
    p_validated: float = 0.85
    validated_busdays: tuple[int, int] = (1, 10)

    # ── Crew & duration (A3: billed_hours >> duration_hours) ───────────────
    crew_probs_standard: tuple[float, ...] = (0.65, 0.22, 0.09, 0.04)  # crew = 1..4
    crew_probs_critical: tuple[float, ...] = (0.35, 0.30, 0.20, 0.15)
    duration_mean_hours: dict[str, float] = field(
        default_factory=lambda: {"corrective": 6.0, "preventive": 4.0, "inspection": 2.0}
    )
    duration_sigma: float = 0.45
    billed_utilization: tuple[float, float] = (0.85, 1.05)  # billed = duration*crew*u

    # ── Lines (D1: avg lines/WO >= 3; E2: labor share ~40%) ─────────────────
    part_lines_range: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {"corrective": (1, 5), "preventive": (1, 3), "inspection": (0, 1)}
    )
    p_two_labor_lines: float = 0.80  # when crew >= 2
    p_split_solo_labor: float = 0.15  # split shift: second labor line even solo
    quantity_geometric_p: float = 0.50  # part quantity ~ 1 + Geom(p), capped
    quantity_cap: int = 6

    # ── Pricing (B1: call-out fee ~= 10-15% of service revenue) ────────────
    callout_fee_base: dict[str, float] = field(
        default_factory=lambda: {"standard": 90.0, "high": 140.0, "critical": 220.0}
    )
    callout_cross_state_factor: float = 1.25
    labor_rate_by_seniority: dict[str, float] = field(
        default_factory=lambda: {"junior": 55.0, "senior": 70.0, "expert": 90.0}
    )
    labor_priority_multiplier: dict[str, float] = field(
        default_factory=lambda: {"standard": 1.0, "high": 1.1, "critical": 1.25}
    )

    # ── Dispatch (C3: site state != depot state often) ──────────────────────
    p_same_state_depot: float = 0.30

    # ── Payments (A2: collected != revenue by month) ────────────────────────
    n_payments_probs: tuple[float, ...] = (0.75, 0.20, 0.05)  # 1, 2 or 3 payments
    payment_lag_mean: float = 38.0
    payment_lag_sd: float = 18.0
    payment_lag_clip: tuple[int, int] = (5, 120)
    extra_payment_lag: tuple[int, int] = (15, 45)
    payment_method_probs: dict[str, float] = field(
        default_factory=lambda: {"bank_transfer": 0.55, "purchase_order": 0.30, "corporate_card": 0.15}
    )

    # ── Surveys (D3: latest-per-WO vs naive average) ─────────────────────────
    p_survey_response: float = 0.55
    survey_lag_days: tuple[int, int] = (1, 21)
    score_mean: float = 7.8
    score_sd: float = 1.5
    late_score_penalty: float = 3.2
    low_score_max: int = 5
    p_resurvey_low: float = 0.80  # unhappy clients get a follow-up survey
    p_resurvey_high: float = 0.05
    resurvey_lag_days: tuple[int, int] = (7, 30)
    resurvey_low_boost_mean: float = 3.2  # follow-up after recovery actions
    resurvey_low_boost_sd: float = 1.2

    thresholds: CheckThresholds = field(default_factory=CheckThresholds)
