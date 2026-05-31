"""Check that key Gold tables exist in Snowflake ECOMMERCE_DB.GOLD."""
from __future__ import annotations

import base64
import os
import sys

import snowflake.connector
from cryptography.hazmat.primitives.serialization import load_der_private_key


def get_private_key_bytes(b64_key: str, passphrase: str) -> bytes:
    der_bytes = base64.b64decode(b64_key)
    private_key = load_der_private_key(
        der_bytes,
        password=passphrase.encode("utf-8"),
    )
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    return private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )


def main() -> int:
    account = os.environ["DEV_SNOWFLAKE_ACCOUNT"]
    user = os.environ["DEV_SNOWFLAKE_USER"]
    private_key_b64 = os.environ["DEV_SNOWFLAKE_USER_PRIVATE_KEY"]
    passphrase = os.environ["DEV_SNOWFLAKE_USER_PRIVATE_KEY_PASSPHRASE"]
    role = os.environ.get("DEV_DBT_SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    warehouse = os.environ.get("DEV_DBT_SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    private_key_der = get_private_key_bytes(private_key_b64, passphrase)

    tables_to_check = [
        "ECOMMERCE_DB.GOLD.FCT_ORDERS",
        "ECOMMERCE_DB.GOLD.FCT_ORDER_ITEMS",
        "ECOMMERCE_DB.GOLD.MART_SELLER_SCORECARD",
    ]

    print(f"Connecting to Snowflake account={account} user={user} role={role}")
    with snowflake.connector.connect(
        account=account,
        user=user,
        private_key=private_key_der,
        role=role,
        warehouse=warehouse,
        database="ECOMMERCE_DB",
        schema="GOLD",
    ) as conn:
        with conn.cursor() as cur:
            missing = []
            for full_table in tables_to_check:
                parts = full_table.split(".")
                db, schema, tbl = parts
                cur.execute(
                    f"SELECT COUNT(*) FROM {db}.INFORMATION_SCHEMA.TABLES "
                    f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{tbl}'"
                )
                (count,) = cur.fetchone()
                status = "EXISTS" if count > 0 else "MISSING"
                print(f"  {full_table}: {status}")
                if count == 0:
                    missing.append(full_table)

    if missing:
        print(f"\nMISSING TABLES: {missing}")
        print("Run: cd transformations && uv run dbt build --project-dir dbt --profiles-dir dbt_profiles")
        return 1

    print("\nAll key Gold tables exist. Gold layer is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
