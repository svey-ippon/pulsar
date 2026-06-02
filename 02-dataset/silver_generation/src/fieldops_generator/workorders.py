"""Work-order lifecycle simulation.

Simulates the operational process (spec / GENERATOR_SILVER_FIRST.md): a work
order is opened at a site, given an SLA promise, scheduled, dispatched to a
crew, accumulates part/labor lines, is invoiced (call-out fee + lines), settled
by one or more payments, and optionally surveyed (with re-surveys).

All cross-table invariants (payments vs invoice total, billed vs duration vs
crew, milestone ordering, serviced units -> categories) hold by construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import GeneratorConfig

DAY = np.timedelta64(1, "D")


def _choice_index(rng: np.random.Generator, probs: tuple[float, ...]) -> int:
    return int(rng.choice(len(probs), p=np.array(probs) / np.sum(probs)))


def _sample_opened_dates(
    rng: np.random.Generator, cfg: GeneratorConfig
) -> np.ndarray:
    """Arrival dates: seasonal monthly shape x strong business-day preference."""
    days = np.arange(
        np.datetime64(cfg.start_date, "D"), np.datetime64(cfg.end_date, "D") + DAY, DAY
    )
    months = days.astype("datetime64[M]").astype(int) % 12
    weights = np.array(cfg.month_weights)[months]
    weekdays = ((days - np.datetime64("1970-01-05", "D")).astype(int)) % 7  # 0 = Monday
    weights = weights * np.where(weekdays >= 5, cfg.weekend_open_weight, 1.0)
    weights = weights / weights.sum()
    opened = rng.choice(days, size=cfg.n_work_orders, p=weights)
    return np.sort(opened)


def simulate_work_orders(
    rng: np.random.Generator,
    cfg: GeneratorConfig,
    sites: pd.DataFrame,
    geography: pd.DataFrame,
    depots: pd.DataFrame,
    technicians: pd.DataFrame,
    equipment_units: pd.DataFrame,
    parts: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    end = np.datetime64(cfg.end_date, "D")

    # ── lookups ──────────────────────────────────────────────────────────────
    state_by_zip = geography.set_index("zip_code_prefix")["state"].to_dict()
    site_records = sites.to_dict("records")
    units_by_site: dict[str, list[tuple[str, str]]] = {}
    for unit in equipment_units.itertuples(index=False):
        units_by_site.setdefault(unit.site_id, []).append(
            (unit.equipment_unit_id, unit.equipment_category)
        )
    depot_state = {
        d.depot_code: state_by_zip[d.zip_code_prefix] for d in depots.itertuples(index=False)
    }
    techs_by_depot: dict[str, list[str]] = {}
    seniority_by_tech: dict[str, str] = {}
    for t in technicians.itertuples(index=False):
        techs_by_depot.setdefault(t.depot_code, []).append(t.technician_id)
        seniority_by_tech[t.technician_id] = t.seniority_level
    depot_by_state: dict[str, list[str]] = {}
    for code, state in depot_state.items():
        depot_by_state.setdefault(state, []).append(code)
    all_depots = list(depot_state)
    part_ids = parts["part_id"].to_numpy()
    price_by_part = parts.set_index("part_id")["list_price"].to_dict()

    opened_dates = _sample_opened_dates(rng, cfg)
    open_tail_start = end - np.timedelta64(cfg.open_tail_days, "D")

    wo_rows, line_rows, servicing_rows, payment_rows, survey_rows = [], [], [], [], []

    for i in range(cfg.n_work_orders):
        wo_id = f"WO-{i + 1:06d}"
        opened = opened_dates[i]
        site = site_records[int(rng.integers(0, len(site_records)))]
        site_state = state_by_zip[site["zip_code_prefix"]]

        wo_type = rng.choice(list(cfg.wo_type_probs), p=list(cfg.wo_type_probs.values()))
        priority = rng.choice(list(cfg.priority_probs), p=list(cfg.priority_probs.values()))

        # ── serviced equipment units -> categories (C2) ─────────────────────
        site_units = units_by_site[site["site_id"]]
        k = min(1 + _choice_index(rng, cfg.units_serviced_probs), len(site_units))
        picked = [site_units[j] for j in rng.choice(len(site_units), size=k, replace=False)]
        for unit_id, _cat in picked:
            servicing_rows.append({"work_order_id": wo_id, "equipment_unit_id": unit_id})

        # ── dispatch (C3) ────────────────────────────────────────────────────
        if rng.random() < cfg.p_same_state_depot and site_state in depot_by_state:
            depot = rng.choice(depot_by_state[site_state])
        else:
            depot = all_depots[int(rng.integers(0, len(all_depots)))]
        technician = rng.choice(techs_by_depot.get(depot, list(seniority_by_tech)))
        cross_state = depot_state[depot] != site_state

        # ── milestones ───────────────────────────────────────────────────────
        sla = cfg.sla_busdays[priority] + int(rng.integers(-1, 3))
        promised = np.busday_offset(opened, max(sla, 2), roll="forward")
        lo, hi = cfg.schedule_days[priority]
        scheduled = opened + np.timedelta64(int(rng.integers(lo, hi + 1)), "D")

        # open (not completed) WOs: ~10%, concentrated near the window end (E1)
        p_open = cfg.p_open_tail if opened >= open_tail_start else cfg.p_open_base
        is_open = rng.random() < p_open

        started = completed = validated = None
        duration_hours = None
        if not is_open or rng.random() < cfg.p_open_started:
            started = scheduled + np.timedelta64(
                _choice_index(rng, cfg.start_after_scheduled_probs), "D"
            )
        if not is_open and started is not None:
            gap = _choice_index(rng, cfg.complete_after_started_probs)
            if rng.random() < cfg.p_overrun:  # parts on backorder -> certified lateness
                gap += int(rng.integers(cfg.overrun_days[0], cfg.overrun_days[1] + 1))
            completed = started + np.timedelta64(gap, "D")
            if completed > end:  # spills past the window: still open
                completed = None
        if started is not None and started > end:
            started = None
        is_completed = completed is not None

        crew_probs = (
            cfg.crew_probs_critical if priority == "critical" else cfg.crew_probs_standard
        )
        crew_size = 1 + _choice_index(rng, crew_probs)

        callout_fee = round(
            float(
                cfg.callout_fee_base[priority]
                * (cfg.callout_cross_state_factor if cross_state else 1.0)
                * rng.uniform(0.9, 1.1)
            ),
            2,
        )

        if is_completed:
            duration_hours = float(
                np.clip(
                    rng.lognormal(np.log(cfg.duration_mean_hours[wo_type]), cfg.duration_sigma),
                    0.5,
                    24.0,
                )
            )
            duration_hours = round(duration_hours * 2) / 2  # half-hour steps
            if cfg.p_validated > rng.random():
                v = np.busday_offset(
                    completed,
                    int(rng.integers(cfg.validated_busdays[0], cfg.validated_busdays[1] + 1)),
                    roll="forward",
                )
                validated = v if v <= end else None

        # ── lines (D1, E2, A3) ───────────────────────────────────────────────
        wo_lines = []
        if started is not None:
            plo, phi = cfg.part_lines_range[wo_type]
            n_part_lines = int(rng.integers(plo, phi + 1))
            if not is_completed:
                n_part_lines //= 2  # work in progress: partial parts, no labor yet
            for _ in range(n_part_lines):
                part_id = part_ids[int(rng.integers(0, len(part_ids)))]
                quantity = int(min(rng.geometric(cfg.quantity_geometric_p), cfg.quantity_cap))
                amount = round(quantity * price_by_part[part_id] * rng.uniform(0.95, 1.10), 2)
                wo_lines.append(("PART", part_id, quantity, None, amount))
            if is_completed:
                billed_total = duration_hours * crew_size * rng.uniform(*cfg.billed_utilization)
                rate = cfg.labor_rate_by_seniority[seniority_by_tech[technician]]
                rate *= cfg.labor_priority_multiplier[priority]
                two_lines = rng.random() < (
                    cfg.p_two_labor_lines if crew_size >= 2 else cfg.p_split_solo_labor
                )
                shares = [rng.uniform(0.4, 0.6)] if two_lines else [1.0]
                if two_lines:
                    shares.append(1.0 - shares[0])
                for share in shares:
                    hours = round(billed_total * share, 2)
                    wo_lines.append(("LABOR", None, None, hours, round(hours * rate, 2)))
        for line_no, (kind, part_id, qty, hours, amount) in enumerate(wo_lines, start=1):
            line_rows.append(
                {
                    "work_order_id": wo_id,
                    "line_number": line_no,
                    "line_kind": kind,
                    "part_id": part_id,
                    "quantity": qty,
                    "billed_hours": hours,
                    "line_amount": amount,
                }
            )

        # ── payments (A2): invoiced on completion, settled with a lag ───────
        if is_completed:
            invoice_total = round(sum(line[4] for line in wo_lines) + callout_fee, 2)
            n_pay = 1 + _choice_index(rng, cfg.n_payments_probs)
            splits = rng.dirichlet(np.ones(n_pay) * 4) if n_pay > 1 else np.array([1.0])
            lag = int(
                np.clip(
                    rng.normal(cfg.payment_lag_mean, cfg.payment_lag_sd),
                    *cfg.payment_lag_clip,
                )
            )
            remaining = invoice_total
            for seq in range(1, n_pay + 1):
                amount = (
                    round(float(invoice_total * splits[seq - 1]), 2)
                    if seq < n_pay
                    else round(remaining, 2)
                )
                remaining = round(remaining - amount, 2)
                paid = completed + np.timedelta64(lag, "D")
                lag += int(rng.integers(*cfg.extra_payment_lag))
                if paid > end:  # not yet collected within the window
                    continue
                payment_rows.append(
                    {
                        "work_order_id": wo_id,
                        "payment_sequence": seq,
                        "payment_method": rng.choice(
                            list(cfg.payment_method_probs),
                            p=list(cfg.payment_method_probs.values()),
                        ),
                        "paid_date": paid,
                        "payment_amount": amount,
                    }
                )

        # ── surveys (D3): unhappy clients get re-surveyed ────────────────────
        if is_completed and rng.random() < cfg.p_survey_response:
            late = int(np.busday_count(promised, completed)) > 2
            score = int(
                np.clip(
                    round(
                        rng.normal(
                            cfg.score_mean - (cfg.late_score_penalty if late else 0.0),
                            cfg.score_sd,
                        )
                    ),
                    1,
                    10,
                )
            )
            responded = completed + np.timedelta64(int(rng.integers(*cfg.survey_lag_days)), "D")
            responses = [(responded, score)]
            p_resurvey = (
                cfg.p_resurvey_low if score <= cfg.low_score_max else cfg.p_resurvey_high
            )
            if rng.random() < p_resurvey:
                boost = (
                    rng.normal(cfg.resurvey_low_boost_mean, cfg.resurvey_low_boost_sd)
                    if score <= cfg.low_score_max
                    else rng.normal(0.0, 1.0)
                )
                second_date = responded + np.timedelta64(
                    int(rng.integers(*cfg.resurvey_lag_days)), "D"
                )
                responses.append((second_date, int(np.clip(round(score + boost), 1, 10))))
            for seq, (resp_date, resp_score) in enumerate(responses, start=1):
                if resp_date > end:
                    continue
                survey_rows.append(
                    {
                        "work_order_id": wo_id,
                        "response_sequence": seq,
                        "responded_date": resp_date,
                        "satisfaction_score": resp_score,
                    }
                )

        wo_rows.append(
            {
                "work_order_id": wo_id,
                "site_id": site["site_id"],
                "technician_id": technician,
                "work_order_type": wo_type,
                "priority": priority,
                "crew_size": crew_size,
                "opened_date": opened,
                "promised_date": promised,
                "scheduled_date": scheduled,
                "started_date": started,
                "completed_date": completed,
                "validated_date": validated,
                "duration_hours": duration_hours,
                "call_out_fee": callout_fee,
            }
        )

    frames = {
        "work_orders": pd.DataFrame(wo_rows),
        "work_order_lines": pd.DataFrame(line_rows),
        "work_order_servicing": pd.DataFrame(servicing_rows),
        "payments": pd.DataFrame(payment_rows),
        "surveys": pd.DataFrame(survey_rows),
    }
    for name, frame in frames.items():
        for col in frame.columns:
            if col.endswith("_date"):
                frames[name][col] = pd.to_datetime(frame[col])
    # nullable integer (avoids "1.0" in the CSV for columns holding NULLs)
    frames["work_order_lines"]["quantity"] = frames["work_order_lines"]["quantity"].astype("Int64")
    return frames
