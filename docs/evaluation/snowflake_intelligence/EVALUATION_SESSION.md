before: current_timestamp()
2026-06-01 05:41:16.606 -0700

after: current_timestamp()
2026-06-01 06:29:30.213 -0700

Compute total credits, comme pour cube-core, on estime le temps warehouse ~10 minutes -> 0,50€
Snowflake Intelligence : 1.25 crédits / estimation 3$/crédits -> 3.75$

# Snowflake intelligence costs

- pas possible de faire du monitoring fin sur les couts SNOWFLAKE_INTELLIGENCE (c'est niveau compte)
- 

```sql
    SELECT
      service_type,
      start_time,
      end_time,
      credits_used
  FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_HISTORY
  WHERE service_type = 'SNOWFLAKE_INTELLIGENCE'
    AND start_time >= '2026-06-01 05:41:16 -0700'
  ORDER BY start_time;
```

-> 1.25 credits
