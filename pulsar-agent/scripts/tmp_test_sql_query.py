from __future__ import annotations

import argparse
import json
import sys

from pulsar_agent.cube_sql_client import CubeSqlClient, CubeSqlQueryError, CubeSqlServiceError


DEFAULT_SQL = "SELECT COUNT(*) AS order_count FROM adv_orders"


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporary Cube SQL API smoke-test script.")
    parser.add_argument(
        "sql",
        nargs="?",
        default=DEFAULT_SQL,
        help=f"SQL query to execute. Defaults to: {DEFAULT_SQL}",
    )
    parser.add_argument("--max-rows", type=int, default=20)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()

    try:
        client = CubeSqlClient.from_settings()
        result = client.execute(args.sql, max_rows=args.max_rows, timeout_s=args.timeout_s)
    except ValueError as exc:
        print(f"Configuration or argument error: {exc}", file=sys.stderr)
        return 2
    except CubeSqlQueryError as exc:
        print(json.dumps({"error": str(exc), "sqlstate": exc.sqlstate, "sql": exc.sql}, indent=2), file=sys.stderr)
        return 3
    except CubeSqlServiceError as exc:
        print(f"Cube SQL service error: {exc}", file=sys.stderr)
        return 4

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
