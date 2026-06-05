"""fieldops-eval-build: materialize and verify the eval expected answers.

Reads the authored items (benchmark/eval/items/*.yml) and the conventions
registry, executes every certified SQL and every naive-signature SQL against
PULSAR_DB.FIELDOPS_GOLD via the `snow` CLI, then:

1. validates the item set (unique ids, control/convention references, F pairs);
2. asserts every certified/signature pair DIVERGES beyond the item's tolerance
   — the authoritative version of the generator's pre-flight checks
   (benchmark/DIVERGENCE_CHECKS.md);
3. writes benchmark/eval/answers.yml (generated artifact, lockfile pattern).

Re-run after any dataset regeneration: stale answers fail loudly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

Row = dict[str, Any]
Answer = float | int | str | list[Row]


# ── loading ──────────────────────────────────────────────────────────────────


def find_eval_dir(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        eval_dir = candidate / "benchmark" / "eval"
        if (eval_dir / "items").is_dir():
            return eval_dir
    return None


@dataclass
class Item:
    id: str
    family: str
    kind: str
    question: str
    pass_criterion: str
    raw: dict[str, Any]
    certified_sql: str | None = None
    tolerance: dict[str, Any] = field(default_factory=lambda: {"mode": "exact"})
    naive_signatures: list[dict[str, Any]] = field(default_factory=list)
    control_id: str | None = None
    requires_conventions: list[str] = field(default_factory=list)
    requires_instructions: list[str] = field(default_factory=list)


def load_items(eval_dir: Path) -> list[Item]:
    items: list[Item] = []
    for path in sorted((eval_dir / "items").glob("*.yml")):
        doc = yaml.safe_load(path.read_text())
        for raw in doc["items"]:
            items.append(
                Item(
                    id=raw["id"],
                    family=raw["family"],
                    kind=raw["kind"],
                    question=raw["question"],
                    pass_criterion=raw["pass_criterion"],
                    certified_sql=raw.get("certified_sql"),
                    tolerance=raw.get("tolerance", {"mode": "exact"}),
                    naive_signatures=raw.get("naive_signatures", []),
                    control_id=raw.get("control_id"),
                    requires_conventions=raw.get("requires_conventions", []),
                    requires_instructions=raw.get("requires_instructions", []),
                    raw=raw,
                )
            )
    return items


def load_conventions(eval_dir: Path) -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((eval_dir / "conventions.yml").read_text())
    return {c["id"]: c for c in doc["conventions"]}


def load_instructions(eval_dir: Path) -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((eval_dir / "instructions.yml").read_text())
    return {i["id"]: i for i in doc["instructions"]}


# ── validation ───────────────────────────────────────────────────────────────


def validate(
    items: list[Item],
    conventions: dict[str, dict[str, Any]],
    instructions: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        errors.append("duplicate item ids")
    id_set = set(ids)
    for item in items:
        if item.control_id and item.control_id not in id_set:
            errors.append(f"{item.id}: unknown control_id {item.control_id}")
        for conv in item.requires_conventions:
            if conv not in conventions:
                errors.append(f"{item.id}: unknown convention {conv}")
        for instr in item.requires_instructions:
            if instr not in instructions:
                errors.append(f"{item.id}: unknown instruction {instr}")
        if item.pass_criterion == "numeric" and not item.certified_sql:
            errors.append(f"{item.id}: numeric item without certified_sql")
        if item.pass_criterion == "behavioural" and not item.raw.get("expected_behaviour"):
            errors.append(f"{item.id}: behavioural item without expected_behaviour")
        if item.kind == "trap" and item.pass_criterion == "numeric" and not item.naive_signatures:
            errors.append(f"{item.id}: numeric trap without naive_signatures")
    return errors


# ── SQL execution (snow CLI) ─────────────────────────────────────────────────


def _coerce(value: Any) -> Any:
    if isinstance(value, str):
        try:
            f = float(value)
            return int(f) if f.is_integer() else f
        except ValueError:
            return value
    return value


def run_sql(sql: str) -> Answer:
    proc = subprocess.run(
        ["snow", "sql", "-q", sql, "--format", "json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"snow sql failed: {proc.stderr.strip()[:500]}")
    rows: list[Row] = [
        {k.lower(): _coerce(v) for k, v in row.items()} for row in json.loads(proc.stdout)
    ]
    if len(rows) == 1 and len(rows[0]) == 1:
        return next(iter(rows[0].values()))
    return rows


# ── divergence ───────────────────────────────────────────────────────────────


def _primary_numeric(answer: Answer) -> float | None:
    if isinstance(answer, (int, float)):
        return float(answer)
    if isinstance(answer, list) and answer:
        for value in reversed(list(answer[0].values())):
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _ranking_keys(answer: Answer) -> list[Any] | None:
    if isinstance(answer, list) and answer:
        return [next(iter(row.values())) for row in answer]
    return None


def diverges(certified: Answer, signature: Answer, tolerance: dict[str, Any]) -> bool:
    """True when the two answers are distinguishable beyond the item tolerance."""
    cert_keys, sig_keys = _ranking_keys(certified), _ranking_keys(signature)
    if cert_keys is not None and sig_keys is not None and cert_keys != sig_keys:
        return True
    a, b = _primary_numeric(certified), _primary_numeric(signature)
    if a is None or b is None:
        return certified != signature
    mode = tolerance.get("mode", "exact")
    if mode == "exact":
        return a != b
    threshold = float(tolerance["value"])
    if mode == "relative":
        return abs(a - b) / max(abs(a), 1e-9) > threshold
    return abs(a - b) > threshold  # absolute


# ── build ────────────────────────────────────────────────────────────────────


def build(eval_dir: Path, verify_only: bool) -> int:
    items = load_items(eval_dir)
    errors = validate(items, load_conventions(eval_dir), load_instructions(eval_dir))
    if errors:
        print("Item validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"{len(items)} items validated.")

    answers: dict[str, Any] = {}
    failures: list[str] = []
    for item in items:
        if item.pass_criterion != "numeric":
            continue
        expected = run_sql(item.certified_sql)
        entry: dict[str, Any] = {"expected_answer": expected, "signatures": []}
        for sig in item.naive_signatures:
            value = run_sql(sig["sql"])
            ok = diverges(expected, value, item.tolerance)
            entry["signatures"].append(
                {
                    "indicates": sig["indicates"],
                    "description": sig["description"],
                    "value": value,
                    "diverges": ok,
                }
            )
            status = "ok" if ok else "NO DIVERGENCE"
            print(f"  {item.id} vs [{sig['indicates']}] {status}")
            if not ok:
                failures.append(f"{item.id}: signature [{sig['indicates']}] does not diverge")
        answers[item.id] = entry
        print(f"[{item.id}] expected = {expected}")

    if failures:
        print("\nAUTHORITATIVE DIVERGENCE CHECK FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    out_path = eval_dir / "answers.yml"
    document = {
        "generated_by": "fieldops-eval-build — DO NOT EDIT (see eval/README.md)",
        "built_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gold": "PULSAR_DB.FIELDOPS_GOLD",
        "answers": answers,
    }
    if verify_only:
        if out_path.exists():
            current = yaml.safe_load(out_path.read_text())
            if current.get("answers") == json.loads(json.dumps(answers)):
                print("\nVerify-only: answers.yml is up to date.")
                return 0
            print("\nVerify-only: answers.yml is STALE (recomputed answers differ).")
            return 1
        print("\nVerify-only: answers.yml does not exist.")
        return 1
    out_path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    print(f"\nAnswers written to {out_path} — all divergences verified.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-dir", type=Path, default=None)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="recompute and compare against answers.yml without writing",
    )
    args = parser.parse_args(argv)
    eval_dir = args.eval_dir or find_eval_dir(Path.cwd())
    if eval_dir is None:
        parser.error("could not locate benchmark/eval — pass --eval-dir")
    return build(eval_dir, verify_only=args.verify_only)


if __name__ == "__main__":
    sys.exit(main())
