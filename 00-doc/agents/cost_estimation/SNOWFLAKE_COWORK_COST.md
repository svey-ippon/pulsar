# Snowflake CoWork (Snowflake Intelligence) costs

Compute credits: as for PULSAR_BARE, we estimate ~10 minutes of warehouse time -> 0.50 $
Snowflake Intelligence: 1.25 credits / est. 3 $/credit -> 3.75 $


NOTE: fine-grained cost monitoring is not possible for SNOWFLAKE_INTELLIGENCE (it is account-level).

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
