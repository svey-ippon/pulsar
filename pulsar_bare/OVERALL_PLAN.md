# Snowflake Agent SQL Execution Without a Native Semantic View

## 1. Goal

We want to build an agent that can generate and execute raw SQL against a governed Snowflake gold layer.

The goal is not to force every query through a Snowflake Semantic View or another strict semantic-query abstraction. Instead, we want to prove that an agent can work directly with Snowflake tables, provided that it has enough metadata, guidance, and execution constraints.

The initial target is:

```text
User question
  → Agent
  → Metadata discovery tools
  → Agent generates SQL
  → execute_sql(sql)
  → Snowflake executes the query
  → Agent explains the result
```

The gold layer is assumed to be well-defined and curated. It contains facts, dimensions, bridges, and possibly aggregate tables.

Example:

```text
PROD.GOLD
  ├── FACT_ORDERS
  ├── FACT_INVOICES
  ├── DIM_CUSTOMER
  ├── DIM_PRODUCT
  ├── DIM_DATE
  ├── DIM_ACCOUNT
  ├── BRIDGE_CUSTOMER_ACCOUNT
  └── AGG_MONTHLY_SALES
```

The agent should not query arbitrary Snowflake objects. It should query only an explicitly allowed analytical surface.

The long-term solution is composed of four parts:

```text
1. A semantic metadata definition, authored as YAML.
2. Metadata describe tools exposed to the agent.
3. A Snowflake-hosted metadata catalog for production.
4. A controlled execute_sql() tool using Snowflake-managed SQL execution.
```

The first implementation should be very simple: one YAML file, one describe tool, and one read-only SQL execution tool.

The later implementation should progressively add richer metadata, catalog storage in Snowflake, RBAC, validation, query safety, and evaluation.

---

# 2. Design principle

The agent is allowed to generate raw SQL, but it must not work blindly.

The agent needs a structured representation of the gold layer:

```text
Tables
Columns
Descriptions
Primary keys
Foreign keys
Table grain
Join paths
Bridge behavior
Metric definitions
Default filters
Fanout risks
Aggregation rules
Query examples
Forbidden patterns
```

This metadata is not exactly a semantic view. It is an agent-facing semantic contract.

The distinction is important:

```text
Snowflake Semantic View approach:
  The semantic layer constrains query generation and execution.

This approach:
  The agent still generates raw SQL,
  but it receives rich metadata and is executed through a controlled tool.
```

This gives more flexibility than a strict semantic layer, while still reducing hallucinations and dangerous SQL patterns.

---

# 3. The perfect semantic YAML definition

## 3.1 Purpose

The YAML file is the first source of truth for the agent-facing metadata.

At the beginning, this YAML can be loaded directly by the agent’s describe tool and returned “as is” or almost “as is”.

Later, the same YAML can be loaded into Snowflake catalog tables.

The YAML should describe:

```text
The domain
The allowed schema
The tables
The columns
The table grains
The relationships
The bridges
The metrics
The allowed query patterns
The forbidden query patterns
Examples
Warnings
```

The YAML is not meant to be a full replacement for Snowflake metadata. Snowflake already knows physical metadata such as types and comments. But the YAML describes the business and analytical meaning that Snowflake cannot infer reliably.

---

## 3.2 Example YAML

```yaml
version: 1

domain:
  id: sales
  name: Sales Analytics
  description: >
    Certified gold-layer domain for sales analytics.
    It covers orders, invoices, customers, products, accounts, and revenue metrics.
  database: PROD
  schema: GOLD
  default_timezone: Europe/Paris
  owner: finance_analytics
  trust_level: certified

query_surface:
  allowed_database: PROD
  allowed_schema: GOLD
  allowed_object_types:
    - TABLE
    - VIEW
  default_warehouse: AGENT_QUERY_WH
  max_result_rows: 1000
  default_limit_for_detail_queries: 100
  forbidden:
    - SELECT_STAR
    - CROSS_JOIN_WITHOUT_REASON
    - FACT_TO_FACT_DIRECT_JOIN
    - RAW_SCHEMA_ACCESS
    - STAGING_SCHEMA_ACCESS

tables:
  - id: fact_orders
    name: FACT_ORDERS
    qualified_name: PROD.GOLD.FACT_ORDERS
    type: FACT
    business_name: Orders
    description: >
      Order-line fact table. Use this table for order volume, revenue,
      product, customer, and order-date analysis.
    grain: One row per order line.
    primary_key:
      - ORDER_LINE_ID
    default_date_column: ORDER_DATE_KEY
    recommended_alias: fo
    trust_level: certified
    queryable: true
    warnings:
      - Do not join directly to another fact table unless an approved join path exists.
      - Use IS_CANCELLED = FALSE for standard revenue analysis unless cancellations are explicitly requested.
    example_questions:
      - What is net revenue by month?
      - Which products generated the most revenue?
      - How many orders were placed by customer segment?

    columns:
      - name: ORDER_LINE_ID
        type: NUMBER
        role: PRIMARY_KEY
        description: Unique identifier for an order line.
        queryable: true
        filterable: true
        groupable: false

      - name: ORDER_ID
        type: NUMBER
        role: DEGENERATE_DIMENSION
        description: Business order identifier. Multiple order lines may share the same ORDER_ID.
        queryable: true
        filterable: true
        groupable: true

      - name: CUSTOMER_KEY
        type: NUMBER
        role: FOREIGN_KEY
        references:
          table: dim_customer
          column: CUSTOMER_KEY
        description: Foreign key to DIM_CUSTOMER.
        queryable: true
        filterable: true
        groupable: false

      - name: PRODUCT_KEY
        type: NUMBER
        role: FOREIGN_KEY
        references:
          table: dim_product
          column: PRODUCT_KEY
        description: Foreign key to DIM_PRODUCT.
        queryable: true
        filterable: true
        groupable: false

      - name: ORDER_DATE_KEY
        type: NUMBER
        role: DATE_KEY
        references:
          table: dim_date
          column: DATE_KEY
        description: Preferred date key for order-based revenue analysis.
        queryable: true
        filterable: true
        groupable: true

      - name: NET_REVENUE
        type: NUMBER(18,2)
        role: MEASURE
        description: Net revenue after discounts, before tax.
        queryable: true
        aggregatable: true
        default_aggregation: SUM
        synonyms:
          - revenue
          - sales
          - turnover
          - net sales
        warnings:
          - Prefer the certified metric total_net_revenue instead of directly aggregating this column.

      - name: GROSS_MARGIN
        type: NUMBER(18,2)
        role: MEASURE
        description: Gross margin amount.
        queryable: true
        aggregatable: true
        default_aggregation: SUM

      - name: IS_CANCELLED
        type: BOOLEAN
        role: FILTER
        description: Indicates whether the order line was cancelled.
        queryable: true
        filterable: true
        groupable: true

  - id: dim_customer
    name: DIM_CUSTOMER
    qualified_name: PROD.GOLD.DIM_CUSTOMER
    type: DIMENSION
    business_name: Customers
    description: Customer dimension.
    grain: One row per customer.
    primary_key:
      - CUSTOMER_KEY
    recommended_alias: dc
    trust_level: certified
    queryable: true
    columns:
      - name: CUSTOMER_KEY
        type: NUMBER
        role: PRIMARY_KEY
        description: Unique customer surrogate key.
        queryable: true

      - name: CUSTOMER_ID
        type: VARCHAR
        role: BUSINESS_KEY
        description: Business customer identifier.
        queryable: true
        filterable: true
        groupable: true

      - name: CUSTOMER_NAME
        type: VARCHAR
        role: DIMENSION
        description: Customer display name.
        queryable: true
        filterable: true
        groupable: true

      - name: CUSTOMER_SEGMENT
        type: VARCHAR
        role: DIMENSION
        description: Commercial customer segment.
        queryable: true
        filterable: true
        groupable: true
        synonyms:
          - segment
          - market segment

  - id: dim_product
    name: DIM_PRODUCT
    qualified_name: PROD.GOLD.DIM_PRODUCT
    type: DIMENSION
    business_name: Products
    description: Product dimension.
    grain: One row per product.
    primary_key:
      - PRODUCT_KEY
    recommended_alias: dp
    trust_level: certified
    queryable: true
    columns:
      - name: PRODUCT_KEY
        type: NUMBER
        role: PRIMARY_KEY
        description: Unique product surrogate key.

      - name: PRODUCT_NAME
        type: VARCHAR
        role: DIMENSION
        description: Product display name.
        queryable: true
        filterable: true
        groupable: true

      - name: PRODUCT_CATEGORY
        type: VARCHAR
        role: DIMENSION
        description: Product category.
        queryable: true
        filterable: true
        groupable: true

  - id: dim_date
    name: DIM_DATE
    qualified_name: PROD.GOLD.DIM_DATE
    type: DIMENSION
    business_name: Date
    description: Calendar date dimension.
    grain: One row per calendar date.
    primary_key:
      - DATE_KEY
    recommended_alias: dd
    trust_level: certified
    queryable: true
    columns:
      - name: DATE_KEY
        type: NUMBER
        role: PRIMARY_KEY
        description: Date surrogate key in YYYYMMDD format.

      - name: DATE
        type: DATE
        role: DATE
        description: Calendar date.
        queryable: true
        filterable: true
        groupable: true

      - name: MONTH
        type: VARCHAR
        role: DIMENSION
        description: Calendar month.
        queryable: true
        filterable: true
        groupable: true

      - name: YEAR
        type: NUMBER
        role: DIMENSION
        description: Calendar year.
        queryable: true
        filterable: true
        groupable: true

  - id: dim_account
    name: DIM_ACCOUNT
    qualified_name: PROD.GOLD.DIM_ACCOUNT
    type: DIMENSION
    business_name: Accounts
    description: Account dimension.
    grain: One row per account.
    primary_key:
      - ACCOUNT_KEY
    recommended_alias: da
    trust_level: certified
    queryable: true

  - id: bridge_customer_account
    name: BRIDGE_CUSTOMER_ACCOUNT
    qualified_name: PROD.GOLD.BRIDGE_CUSTOMER_ACCOUNT
    type: BRIDGE
    business_name: Customer Account Bridge
    description: >
      Bridge table connecting customers to accounts.
      A customer can belong to multiple accounts.
    grain: One row per customer-account relationship.
    primary_key:
      - CUSTOMER_KEY
      - ACCOUNT_KEY
    recommended_alias: bca
    trust_level: certified
    queryable: true
    warnings:
      - Joining through this bridge can duplicate customer-level measures.
      - Use allocation weight when aggregating customer-level measures by account.
      - Use COUNT(DISTINCT CUSTOMER_KEY) when counting customers after joining this bridge.
    columns:
      - name: CUSTOMER_KEY
        type: NUMBER
        role: FOREIGN_KEY
        references:
          table: dim_customer
          column: CUSTOMER_KEY

      - name: ACCOUNT_KEY
        type: NUMBER
        role: FOREIGN_KEY
        references:
          table: dim_account
          column: ACCOUNT_KEY

      - name: ALLOCATION_WEIGHT
        type: NUMBER(18,6)
        role: ALLOCATION_WEIGHT
        description: Weight used to allocate customer-level measures across accounts.

relationships:
  - id: fact_orders__dim_customer
    from_table: fact_orders
    from_columns:
      - CUSTOMER_KEY
    to_table: dim_customer
    to_columns:
      - CUSTOMER_KEY
    type: MANY_TO_ONE
    recommended_join_type: LEFT
    default: true
    fanout_risk: LOW
    description: Each order line belongs to one customer.
    join_sql_template: >
      LEFT JOIN PROD.GOLD.DIM_CUSTOMER dc
        ON fo.CUSTOMER_KEY = dc.CUSTOMER_KEY

  - id: fact_orders__dim_product
    from_table: fact_orders
    from_columns:
      - PRODUCT_KEY
    to_table: dim_product
    to_columns:
      - PRODUCT_KEY
    type: MANY_TO_ONE
    recommended_join_type: LEFT
    default: true
    fanout_risk: LOW
    description: Each order line belongs to one product.
    join_sql_template: >
      LEFT JOIN PROD.GOLD.DIM_PRODUCT dp
        ON fo.PRODUCT_KEY = dp.PRODUCT_KEY

  - id: fact_orders__dim_date
    from_table: fact_orders
    from_columns:
      - ORDER_DATE_KEY
    to_table: dim_date
    to_columns:
      - DATE_KEY
    type: MANY_TO_ONE
    recommended_join_type: LEFT
    default: true
    fanout_risk: LOW
    description: Join orders to the calendar date dimension.
    join_sql_template: >
      LEFT JOIN PROD.GOLD.DIM_DATE dd
        ON fo.ORDER_DATE_KEY = dd.DATE_KEY

  - id: dim_customer__bridge_customer_account
    from_table: dim_customer
    from_columns:
      - CUSTOMER_KEY
    to_table: bridge_customer_account
    to_columns:
      - CUSTOMER_KEY
    type: ONE_TO_MANY
    recommended_join_type: LEFT
    default: true
    fanout_risk: HIGH
    description: Customers can belong to multiple accounts.
    warning: This join can duplicate customer-level rows.

  - id: bridge_customer_account__dim_account
    from_table: bridge_customer_account
    from_columns:
      - ACCOUNT_KEY
    to_table: dim_account
    to_columns:
      - ACCOUNT_KEY
    type: MANY_TO_ONE
    recommended_join_type: LEFT
    default: true
    fanout_risk: LOW
    description: Each bridge row belongs to one account.

join_paths:
  - id: fact_orders_to_dim_account
    from_table: fact_orders
    to_table: dim_account
    intermediate_tables:
      - dim_customer
      - bridge_customer_account
    relationships:
      - fact_orders__dim_customer
      - dim_customer__bridge_customer_account
      - bridge_customer_account__dim_account
    fanout_risk: HIGH
    description: >
      Use this path to analyze order activity by account through the customer-account bridge.
    warnings:
      - This path may multiply rows if a customer belongs to multiple accounts.
      - For revenue by account, confirm whether allocation is required.
      - For customer counts, use COUNT(DISTINCT dc.CUSTOMER_KEY).
    join_sql_template: >
      LEFT JOIN PROD.GOLD.DIM_CUSTOMER dc
        ON fo.CUSTOMER_KEY = dc.CUSTOMER_KEY
      LEFT JOIN PROD.GOLD.BRIDGE_CUSTOMER_ACCOUNT bca
        ON dc.CUSTOMER_KEY = bca.CUSTOMER_KEY
      LEFT JOIN PROD.GOLD.DIM_ACCOUNT da
        ON bca.ACCOUNT_KEY = da.ACCOUNT_KEY

metrics:
  - id: total_net_revenue
    name: Total net revenue
    description: Sum of net revenue after discounts, before tax.
    base_table: fact_orders
    expression_sql: SUM(fo.NET_REVENUE)
    default_filter_sql: fo.IS_CANCELLED = FALSE
    additive_type: ADDITIVE
    default_date_column: ORDER_DATE_KEY
    allowed_dimensions:
      - dim_date
      - dim_customer
      - dim_product
      - dim_account
    synonyms:
      - revenue
      - sales
      - net sales
      - turnover
    format: currency
    trust_level: certified
    warnings:
      - Prefer this metric over direct SUM(NET_REVENUE).

  - id: order_count
    name: Order count
    description: Number of distinct orders.
    base_table: fact_orders
    expression_sql: COUNT(DISTINCT fo.ORDER_ID)
    default_filter_sql: fo.IS_CANCELLED = FALSE
    additive_type: NON_ADDITIVE
    allowed_dimensions:
      - dim_date
      - dim_customer
      - dim_product
    synonyms:
      - orders
      - number of orders
      - order volume
    format: integer
    trust_level: certified

  - id: gross_margin_rate
    name: Gross margin rate
    description: Gross margin divided by net revenue.
    base_table: fact_orders
    expression_sql: >
      SUM(fo.GROSS_MARGIN) / NULLIF(SUM(fo.NET_REVENUE), 0)
    default_filter_sql: fo.IS_CANCELLED = FALSE
    additive_type: NON_ADDITIVE
    allowed_dimensions:
      - dim_date
      - dim_customer
      - dim_product
    synonyms:
      - margin rate
      - gross margin percentage
      - margin percentage
    format: percentage
    trust_level: certified
    warnings:
      - Do not compute this as AVG(row_level_margin_rate).
      - Always compute as ratio of aggregates.

sql_generation_rules:
  - id: use_certified_metrics
    severity: HIGH
    rule: >
      Prefer certified metric definitions over direct aggregation of measure columns.

  - id: no_select_star
    severity: HIGH
    rule: >
      Do not use SELECT *. Select only the necessary columns.

  - id: no_fact_to_fact_direct_join
    severity: HIGH
    rule: >
      Do not join fact tables directly unless an approved join path explicitly allows it.

  - id: bridge_distinct_count
    severity: HIGH
    rule: >
      After joining through a bridge table, use COUNT(DISTINCT ...) when counting entities from the many side.

  - id: ratio_metric_rule
    severity: HIGH
    rule: >
      Ratio metrics must be computed as ratios of aggregate expressions, not as averages of row-level ratios.

  - id: standard_revenue_filter
    severity: MEDIUM
    rule: >
      For standard revenue questions, apply fo.IS_CANCELLED = FALSE unless the user explicitly asks for cancelled orders.

examples:
  - question: What is net revenue by month?
    expected_tables:
      - fact_orders
      - dim_date
    expected_metrics:
      - total_net_revenue
    sql: >
      SELECT
        dd.YEAR,
        dd.MONTH,
        SUM(fo.NET_REVENUE) AS total_net_revenue
      FROM PROD.GOLD.FACT_ORDERS fo
      LEFT JOIN PROD.GOLD.DIM_DATE dd
        ON fo.ORDER_DATE_KEY = dd.DATE_KEY
      WHERE fo.IS_CANCELLED = FALSE
      GROUP BY dd.YEAR, dd.MONTH
      ORDER BY dd.YEAR, dd.MONTH;

  - question: Which customer segments generated the most revenue?
    expected_tables:
      - fact_orders
      - dim_customer
    expected_metrics:
      - total_net_revenue
    sql: >
      SELECT
        dc.CUSTOMER_SEGMENT,
        SUM(fo.NET_REVENUE) AS total_net_revenue
      FROM PROD.GOLD.FACT_ORDERS fo
      LEFT JOIN PROD.GOLD.DIM_CUSTOMER dc
        ON fo.CUSTOMER_KEY = dc.CUSTOMER_KEY
      WHERE fo.IS_CANCELLED = FALSE
      GROUP BY dc.CUSTOMER_SEGMENT
      ORDER BY total_net_revenue DESC
      LIMIT 20;
```

---

# 4. First iteration: load the YAML into the agent describe tool

## 4.1 Objective

The first iteration should prove the basic hypothesis:

```text
Can an agent generate useful SQL if we give it a rich YAML description of the gold layer?
```

Do not start by building the perfect Snowflake catalog. That would slow down the first proof of value.

The first version can be extremely simple:

```text
semantic.yaml
  → describe_domain()
  → agent receives YAML or compact JSON
  → agent generates SQL
  → execute_sql()
```

The describe tool can initially return the YAML “as is”.

This is not optimal, but it is useful because it validates:

```text
The metadata structure
The agent prompting
The table descriptions
The metric definitions
The join guidance
The SQL quality
The execution flow
```

## 4.2 First describe tool

The first tool can be:

```text
describe_domain(domain_id: string) -> string | json
```

For the first version, it can return:

```json
{
  "domain_id": "sales",
  "semantic_yaml": "<full YAML content>"
}
```

Or, preferably:

```json
{
  "domain_id": "sales",
  "metadata": {
    "tables": [],
    "relationships": [],
    "join_paths": [],
    "metrics": [],
    "sql_generation_rules": [],
    "examples": []
  }
}
```

The first version does not need dynamic filtering.

The agent can receive the full domain metadata for a small gold layer.

## 4.3 First execute tool

The first execution tool should be:

```text
execute_sql(sql: string) -> result | error
```

At first, it should only enforce:

```text
Single SQL statement
SELECT or WITH only
No DDL
No DML
No CALL
No COPY
No CREATE
No ALTER
No DROP
No DELETE
No UPDATE
No INSERT
No MERGE
```

This is not semantic validation yet. It is only a basic safety gate.

The first version should also force execution through a restricted Snowflake role that only has access to the allowed gold schema or, preferably, to an agent-facing view schema.

---

# 5. Perfect Snowflake catalog for later

## 5.1 Objective

Once the YAML approach works, the metadata should be loaded into Snowflake.

The long-term catalog should live in Snowflake because:

```text
Snowflake becomes the runtime source of truth.
RBAC can control who can read which metadata.
Metadata can be queried, versioned, audited, and joined with native Snowflake metadata.
Stored procedures can expose curated metadata to the agent.
The catalog can evolve independently from the agent runtime.
```

The catalog should not replace Snowflake native metadata. It should enrich it.

Snowflake already provides:

```text
Databases
Schemas
Tables
Columns
Types
Comments
Constraints
Object privileges
```

The agent catalog should provide:

```text
Business meaning
Table grain
Join rules
Metric definitions
Bridge semantics
Fanout risks
Certified query patterns
Forbidden query patterns
```

---

## 5.2 Proposed catalog schemas

Create a dedicated governance database and schema:

```sql
CREATE DATABASE IF NOT EXISTS GOVERNANCE;
CREATE SCHEMA IF NOT EXISTS GOVERNANCE.AGENT_CATALOG;
```

Recommended catalog tables:

```text
AGENT_CATALOG.DOMAINS
AGENT_CATALOG.TABLES
AGENT_CATALOG.COLUMNS
AGENT_CATALOG.RELATIONSHIPS
AGENT_CATALOG.JOIN_PATHS
AGENT_CATALOG.BRIDGES
AGENT_CATALOG.METRICS
AGENT_CATALOG.SQL_GENERATION_RULES
AGENT_CATALOG.EXAMPLES
AGENT_CATALOG.ALLOWED_OBJECTS
AGENT_CATALOG.DOMAIN_ROLE_ACCESS
AGENT_CATALOG.CATALOG_VERSIONS
```

---

## 5.3 DOMAINS

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.DOMAINS (
  DOMAIN_ID STRING PRIMARY KEY,
  DOMAIN_NAME STRING NOT NULL,
  DESCRIPTION STRING,
  DATABASE_NAME STRING NOT NULL,
  SCHEMA_NAME STRING NOT NULL,
  DEFAULT_WAREHOUSE STRING,
  DEFAULT_TIMEZONE STRING,
  OWNER_ROLE STRING,
  TRUST_LEVEL STRING,
  IS_ACTIVE BOOLEAN DEFAULT TRUE,
  CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
  UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP
);
```

Purpose:

```text
Defines an analytical domain such as sales, finance, support, product, or marketing.
```

---

## 5.4 TABLES

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.TABLES (
  DOMAIN_ID STRING NOT NULL,
  TABLE_ID STRING NOT NULL,
  DATABASE_NAME STRING NOT NULL,
  SCHEMA_NAME STRING NOT NULL,
  TABLE_NAME STRING NOT NULL,
  QUALIFIED_NAME STRING NOT NULL,
  TABLE_TYPE STRING NOT NULL,
  BUSINESS_NAME STRING,
  DESCRIPTION STRING,
  GRAIN STRING NOT NULL,
  PRIMARY_KEY_COLUMNS ARRAY,
  DEFAULT_DATE_COLUMN STRING,
  RECOMMENDED_ALIAS STRING,
  TRUST_LEVEL STRING,
  IS_QUERYABLE BOOLEAN DEFAULT TRUE,
  QUERY_PRIORITY NUMBER DEFAULT 100,
  WARNINGS ARRAY,
  EXAMPLE_QUESTIONS ARRAY,
  PRIMARY KEY (DOMAIN_ID, TABLE_ID)
);
```

Purpose:

```text
Tells the agent what the table means, what its grain is, and how it should be used.
```

---

## 5.5 COLUMNS

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.COLUMNS (
  DOMAIN_ID STRING NOT NULL,
  TABLE_ID STRING NOT NULL,
  COLUMN_NAME STRING NOT NULL,
  DATA_TYPE STRING,
  BUSINESS_NAME STRING,
  DESCRIPTION STRING,
  COLUMN_ROLE STRING,
  IS_QUERYABLE BOOLEAN DEFAULT TRUE,
  IS_FILTERABLE BOOLEAN DEFAULT TRUE,
  IS_GROUPABLE BOOLEAN DEFAULT TRUE,
  IS_AGGREGATABLE BOOLEAN DEFAULT FALSE,
  DEFAULT_AGGREGATION STRING,
  REFERENCES_TABLE_ID STRING,
  REFERENCES_COLUMN_NAME STRING,
  SYNONYMS ARRAY,
  EXAMPLES ARRAY,
  SENSITIVITY STRING,
  FORMAT_HINT STRING,
  WARNINGS ARRAY,
  PRIMARY KEY (DOMAIN_ID, TABLE_ID, COLUMN_NAME)
);
```

Purpose:

```text
Controls which columns the agent can use and how it should interpret them.
```

---

## 5.6 RELATIONSHIPS

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.RELATIONSHIPS (
  DOMAIN_ID STRING NOT NULL,
  RELATIONSHIP_ID STRING NOT NULL,
  FROM_TABLE_ID STRING NOT NULL,
  FROM_COLUMNS ARRAY NOT NULL,
  TO_TABLE_ID STRING NOT NULL,
  TO_COLUMNS ARRAY NOT NULL,
  RELATIONSHIP_TYPE STRING NOT NULL,
  RECOMMENDED_JOIN_TYPE STRING DEFAULT 'LEFT',
  IS_DEFAULT BOOLEAN DEFAULT FALSE,
  IS_ACTIVE BOOLEAN DEFAULT TRUE,
  FANOUT_RISK STRING,
  DESCRIPTION STRING,
  JOIN_SQL_TEMPLATE STRING,
  WARNING STRING,
  PRIMARY KEY (DOMAIN_ID, RELATIONSHIP_ID)
);
```

Purpose:

```text
Defines the curated join graph.
```

This is one of the most important parts of the system.

The agent should not infer all joins from column names. It should prefer curated relationships.

---

## 5.7 JOIN_PATHS

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.JOIN_PATHS (
  DOMAIN_ID STRING NOT NULL,
  PATH_ID STRING NOT NULL,
  FROM_TABLE_ID STRING NOT NULL,
  TO_TABLE_ID STRING NOT NULL,
  INTERMEDIATE_TABLE_IDS ARRAY,
  RELATIONSHIP_IDS ARRAY NOT NULL,
  FANOUT_RISK STRING,
  DESCRIPTION STRING,
  JOIN_SQL_TEMPLATE STRING NOT NULL,
  WARNINGS ARRAY,
  PRIMARY KEY (DOMAIN_ID, PATH_ID)
);
```

Purpose:

```text
Provides approved multi-hop joins, especially through bridge tables.
```

This prevents the agent from inventing incorrect join paths.

---

## 5.8 BRIDGES

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.BRIDGES (
  DOMAIN_ID STRING NOT NULL,
  BRIDGE_TABLE_ID STRING NOT NULL,
  LEFT_TABLE_ID STRING NOT NULL,
  RIGHT_TABLE_ID STRING NOT NULL,
  LEFT_KEY_COLUMNS ARRAY NOT NULL,
  RIGHT_KEY_COLUMNS ARRAY NOT NULL,
  ALLOCATION_COLUMN STRING,
  BRIDGE_GRAIN STRING NOT NULL,
  DESCRIPTION STRING,
  MEASURE_HANDLING_RULE STRING,
  WARNINGS ARRAY,
  PRIMARY KEY (DOMAIN_ID, BRIDGE_TABLE_ID)
);
```

Purpose:

```text
Explains many-to-many relationships and how measures should be handled through bridges.
```

This is essential for preventing duplicated measures.

---

## 5.9 METRICS

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.METRICS (
  DOMAIN_ID STRING NOT NULL,
  METRIC_ID STRING NOT NULL,
  BUSINESS_NAME STRING NOT NULL,
  DESCRIPTION STRING,
  BASE_TABLE_ID STRING NOT NULL,
  EXPRESSION_SQL STRING NOT NULL,
  DEFAULT_FILTER_SQL STRING,
  DEFAULT_DATE_COLUMN STRING,
  ADDITIVE_TYPE STRING,
  ALLOWED_DIMENSIONS ARRAY,
  DISALLOWED_DIMENSIONS ARRAY,
  REQUIRED_JOIN_PATHS ARRAY,
  SYNONYMS ARRAY,
  FORMAT_HINT STRING,
  TRUST_LEVEL STRING,
  WARNINGS ARRAY,
  EXAMPLE_SQL STRING,
  PRIMARY KEY (DOMAIN_ID, METRIC_ID)
);
```

Purpose:

```text
Provides certified metric logic while still allowing the agent to generate raw SQL.
```

This is where you prevent errors like:

```sql
AVG(GROSS_MARGIN_RATE)
```

when the correct metric is:

```sql
SUM(GROSS_MARGIN) / NULLIF(SUM(NET_REVENUE), 0)
```

---

## 5.10 SQL_GENERATION_RULES

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.SQL_GENERATION_RULES (
  DOMAIN_ID STRING NOT NULL,
  RULE_ID STRING NOT NULL,
  SEVERITY STRING NOT NULL,
  RULE_TEXT STRING NOT NULL,
  EXAMPLE_BAD_SQL STRING,
  EXAMPLE_GOOD_SQL STRING,
  IS_ACTIVE BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (DOMAIN_ID, RULE_ID)
);
```

Purpose:

```text
Provides explicit SQL generation guidance and later validation rules.
```

---

## 5.11 EXAMPLES

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.EXAMPLES (
  DOMAIN_ID STRING NOT NULL,
  EXAMPLE_ID STRING NOT NULL,
  QUESTION STRING NOT NULL,
  EXPECTED_TABLES ARRAY,
  EXPECTED_METRICS ARRAY,
  EXPECTED_JOIN_PATHS ARRAY,
  SQL_TEXT STRING NOT NULL,
  NOTES STRING,
  TRUST_LEVEL STRING,
  PRIMARY KEY (DOMAIN_ID, EXAMPLE_ID)
);
```

Purpose:

```text
Provides few-shot examples and later test cases for evaluation.
```

---

# 6. Managing rights on the catalog

## 6.1 Separate metadata access from data access

There are two different permissions:

```text
Can the user read the metadata?
Can the user query the underlying data?
```

A user may be allowed to see that a domain exists without being allowed to query all its tables.

The roles should be separated:

```text
AGENT_METADATA_READER
AGENT_SALES_READER
AGENT_FINANCE_READER
AGENT_CATALOG_ADMIN
```

Example:

```sql
CREATE ROLE AGENT_METADATA_READER;
CREATE ROLE AGENT_SALES_READER;
CREATE ROLE AGENT_CATALOG_ADMIN;
```

Metadata grants:

```sql
GRANT USAGE ON DATABASE GOVERNANCE TO ROLE AGENT_METADATA_READER;
GRANT USAGE ON SCHEMA GOVERNANCE.AGENT_CATALOG TO ROLE AGENT_METADATA_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA GOVERNANCE.AGENT_CATALOG TO ROLE AGENT_METADATA_READER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA GOVERNANCE.AGENT_CATALOG TO ROLE AGENT_METADATA_READER;
```

Gold-layer grants:

```sql
GRANT USAGE ON DATABASE PROD TO ROLE AGENT_SALES_READER;
GRANT USAGE ON SCHEMA PROD.GOLD TO ROLE AGENT_SALES_READER;
GRANT SELECT ON ALL TABLES IN SCHEMA PROD.GOLD TO ROLE AGENT_SALES_READER;
```

Catalog administration grants:

```sql
GRANT INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA GOVERNANCE.AGENT_CATALOG
TO ROLE AGENT_CATALOG_ADMIN;
```

---

## 6.2 Domain-level metadata visibility

Later, add a table that maps domains to roles.

```sql
CREATE TABLE GOVERNANCE.AGENT_CATALOG.DOMAIN_ROLE_ACCESS (
  DOMAIN_ID STRING NOT NULL,
  ROLE_NAME STRING NOT NULL,
  CAN_DESCRIBE BOOLEAN DEFAULT TRUE,
  CAN_QUERY BOOLEAN DEFAULT FALSE,
  CAN_USE_METRICS ARRAY,
  CAN_USE_TABLES ARRAY,
  PRIMARY KEY (DOMAIN_ID, ROLE_NAME)
);
```

Example:

```sql
INSERT INTO GOVERNANCE.AGENT_CATALOG.DOMAIN_ROLE_ACCESS
VALUES
  ('sales', 'AGENT_SALES_READER', TRUE, TRUE, NULL, NULL),
  ('sales', 'AGENT_METADATA_READER', TRUE, FALSE, NULL, NULL);
```

The describe tools can use this table to filter what they return.

The execution rights are still enforced by Snowflake RBAC. This catalog-level access table is not a replacement for Snowflake RBAC. It is a metadata filtering layer.

---

## 6.3 Recommended production model

For production, the ideal model is:

```text
User connects with a Snowflake role.
The metadata tools return only domains and objects visible for that role.
execute_sql() runs with the same effective role.
Snowflake RBAC enforces actual data access.
```

Avoid a single overpowered service role for all users.

If a service role is required, it should be scoped per tenant, domain, or persona.

Example:

```text
AGENT_TENANT_A_SALES_ROLE
AGENT_TENANT_A_FINANCE_ROLE
AGENT_TENANT_B_SALES_ROLE
```

---

# 7. Describe tools for the agent

The agent should not receive the entire database schema blindly.

It should discover metadata progressively.

The minimum toolset is:

```text
discover_domains()
describe_domain(domain_id)
describe_tables(domain_id, table_ids)
get_metric_definitions(domain_id, metric_terms)
get_join_paths(domain_id, table_ids)
```

Later, add:

```text
search_metadata(domain_id, query)
get_examples(domain_id, question)
get_table_profile(domain_id, table_id)
```

---

## 7.1 discover_domains()

Purpose:

```text
Tell the agent which analytical domains exist.
```

Example response:

```json
{
  "domains": [
    {
      "domain_id": "sales",
      "name": "Sales Analytics",
      "description": "Certified gold-layer sales analytics domain.",
      "database": "PROD",
      "schema": "GOLD"
    }
  ]
}
```

Why it matters:

```text
The agent should select a bounded domain before generating SQL.
```

---

## 7.2 describe_domain(domain_id)

Purpose:

```text
Return a compact overview of the domain.
```

It should include:

```text
Tables
Table types
Table grains
Main metrics
Main relationships
Important warnings
SQL generation rules
Examples
```

This is the most important first tool.

First iteration:

```text
Return the YAML as is.
```

Later:

```text
Return only a compact JSON summary generated from Snowflake catalog tables.
```

---

## 7.3 describe_tables(domain_id, table_ids)

Purpose:

```text
Return detailed metadata for selected tables.
```

It should include:

```text
Columns
Column roles
Types
Descriptions
Primary keys
Foreign keys
Queryable/filterable/groupable flags
Warnings
```

Why it matters:

```text
The agent should not need the full catalog for every query.
```

---

## 7.4 get_metric_definitions(domain_id, metric_terms)

Purpose:

```text
Resolve business terms such as “revenue”, “orders”, or “margin rate” into certified metric SQL expressions.
```

Example:

```json
{
  "metric_id": "gross_margin_rate",
  "expression_sql": "SUM(fo.GROSS_MARGIN) / NULLIF(SUM(fo.NET_REVENUE), 0)",
  "warnings": [
    "Do not compute this as AVG(row_level_margin_rate)."
  ]
}
```

Why it matters:

```text
Metrics are where many raw SQL agents make serious mistakes.
```

---

## 7.5 get_join_paths(domain_id, table_ids)

Purpose:

```text
Return approved join paths between required tables.
```

Example:

```json
{
  "path_id": "fact_orders_to_dim_account",
  "join_sql_template": "LEFT JOIN ...",
  "fanout_risk": "HIGH",
  "warnings": [
    "This path may multiply rows.",
    "Use allocation weight if required."
  ]
}
```

Why it matters:

```text
The agent should not invent many-to-many joins.
```

---

## 7.6 search_metadata(domain_id, query)

Purpose:

```text
Let the agent search for relevant tables, columns, metrics, and examples.
```

Example:

```json
{
  "query": "customer churn revenue",
  "matches": [
    {
      "type": "table",
      "id": "dim_customer",
      "reason": "Contains customer segment and lifecycle fields."
    },
    {
      "type": "metric",
      "id": "total_net_revenue",
      "reason": "Revenue metric."
    }
  ]
}
```

This should be added once the domain becomes too large to pass completely to the model.

---

# 8. execute_sql() tool

## 8.1 Purpose

The `execute_sql()` tool receives SQL generated by the agent.

It is responsible for:

```text
Validating the SQL enough to protect the platform.
Executing the SQL if valid.
Returning an error if invalid.
Returning query results if valid.
```

The agent does not need a separate pre-validation tool at first.

The contract should be:

```text
execute_sql(sql: string) -> result | validation_error | execution_error
```

---

## 8.2 First implementation

The first version should be minimal.

Validation:

```text
Allow only SELECT or WITH queries.
Reject multiple statements.
Reject DDL.
Reject DML.
Reject CALL.
Reject COPY.
Reject commands that change session, role, warehouse, database, or schema.
```

Execution:

```text
Run through Snowflake-managed MCP SYSTEM_EXECUTE_SQL.
Use read_only mode.
Use a restricted warehouse.
Use a restricted role.
Apply a query timeout.
```

The tool should return:

```json
{
  "status": "success",
  "columns": [],
  "rows": [],
  "row_count": 42
}
```

Or:

```json
{
  "status": "error",
  "error_type": "VALIDATION_ERROR",
  "message": "Only SELECT and WITH queries are allowed."
}
```

---

## 8.3 Later implementation

Later, `execute_sql()` should perform semantic validation before execution.

Checks:

```text
Only allowed databases and schemas.
Only allowed tables or views.
No SELECT *.
No direct fact-to-fact joins unless approved.
No bridge join without required aggregation strategy.
Required metric filters are present.
LIMIT exists for detail queries.
No suspicious SQL comments.
No expensive unbounded detail scan.
No disallowed functions.
No access to INFORMATION_SCHEMA unless explicitly allowed.
No access to ACCOUNT_USAGE unless explicitly allowed.
```

The output should distinguish validation errors from Snowflake execution errors.

Example:

```json
{
  "status": "error",
  "error_type": "VALIDATION_ERROR",
  "issues": [
    {
      "rule_id": "no_fact_to_fact_direct_join",
      "severity": "HIGH",
      "message": "FACT_ORDERS and FACT_INVOICES cannot be joined directly."
    }
  ]
}
```

---

# 9. MCP server shape

The MCP server should expose a small set of tools.

First version:

```text
describe_domain
execute_sql
```

Improved version:

```text
discover_domains
describe_domain
describe_tables
get_metric_definitions
get_join_paths
execute_sql
```

Later version:

```text
discover_domains
search_metadata
describe_domain
describe_tables
get_metric_definitions
get_join_paths
get_examples
execute_sql
```

Example target MCP shape:

```yaml
tools:
  - name: describe_domain
    title: Describe analytics domain
    type: GENERIC
    identifier: GOVERNANCE.AGENT_CATALOG.DESCRIBE_DOMAIN
    description: Returns metadata for a governed analytical domain.

  - name: get_metric_definitions
    title: Get metric definitions
    type: GENERIC
    identifier: GOVERNANCE.AGENT_CATALOG.GET_METRIC_DEFINITIONS
    description: Returns certified metric SQL expressions and usage rules.

  - name: get_join_paths
    title: Get join paths
    type: GENERIC
    identifier: GOVERNANCE.AGENT_CATALOG.GET_JOIN_PATHS
    description: Returns approved joins between gold-layer tables.

  - name: execute_sql
    title: Execute SQL
    type: SYSTEM_EXECUTE_SQL
    description: Executes read-only SQL against the governed gold layer.
    config:
      read_only: true
      query_timeout: 120
      warehouse: AGENT_QUERY_WH
```

---

# 10. Iteration plan

## Iteration 0 — Hardcoded proof of concept

Goal:

```text
Prove that an agent can generate and execute a basic SQL query against the gold layer.
```

Implementation:

```text
One prompt contains a small schema description.
One execute_sql() tool.
No describe tool yet.
Read-only SQL only.
```

Scope:

```text
One fact table.
One or two dimensions.
One or two metrics.
```

Success criteria:

```text
The agent can answer simple questions such as:
- Revenue by month
- Revenue by product category
- Orders by customer segment
```

Limitations:

```text
No dynamic metadata.
No validation beyond read-only.
No join-path intelligence.
No catalog.
```

---

## Iteration 1 — YAML loaded into describe_domain()

Goal:

```text
Move schema knowledge out of the prompt and into a YAML-backed describe tool.
```

Implementation:

```text
Create semantic.yaml.
Create describe_domain(domain_id).
The tool returns the YAML or a JSON representation of it.
Create execute_sql(sql).
execute_sql allows SELECT/WITH only.
```

Agent workflow:

```text
User asks question.
Agent calls describe_domain("sales").
Agent generates SQL.
Agent calls execute_sql(sql).
```

Success criteria:

```text
The agent can answer simple analytical questions using joins and metrics from the YAML.
```

This is the first real working agent.

---

## Iteration 2 — Better YAML structure and better prompt usage

Goal:

```text
Improve the semantic YAML so that SQL quality improves.
```

Add to YAML:

```text
Table grain
Recommended aliases
Column roles
Metric definitions
Default filters
Join SQL templates
Bridge warnings
Examples
SQL generation rules
```

Improve the agent instructions:

```text
Always use certified metric definitions when available.
Always check table grain.
Always use curated join paths.
Never use SELECT *.
Prefer aliases from metadata.
```

Success criteria:

```text
The generated SQL consistently uses correct joins, aliases, filters, and metric expressions.
```

---

## Iteration 3 — Split describe tools

Goal:

```text
Avoid giving the entire YAML to the agent for every question.
```

Add tools:

```text
discover_domains()
describe_tables(domain_id, table_ids)
get_metric_definitions(domain_id, metric_terms)
get_join_paths(domain_id, table_ids)
```

Agent workflow:

```text
User asks question.
Agent calls discover_domains().
Agent selects domain.
Agent calls describe_domain().
Agent calls get_metric_definitions().
Agent calls get_join_paths().
Agent generates SQL.
Agent calls execute_sql().
```

Success criteria:

```text
The agent retrieves only relevant metadata.
The approach scales beyond a tiny schema.
```

---

## Iteration 4 — First validation inside execute_sql()

Goal:

```text
Make execute_sql safer without building a full SQL validator.
```

Validation rules:

```text
Only SELECT/WITH.
Single statement only.
Reject SELECT *.
Require LIMIT for detail queries.
Restrict database and schema names.
Reject obvious DDL/DML keywords.
```

Success criteria:

```text
Dangerous or obviously bad queries are rejected.
The agent can recover from validation errors and generate corrected SQL.
```

---

## Iteration 5 — Load metadata into Snowflake catalog tables

Goal:

```text
Move runtime metadata from YAML files into Snowflake.
```

Implementation:

```text
Create GOVERNANCE.AGENT_CATALOG schema.
Create catalog tables.
Build loader from YAML to Snowflake tables.
Create stored procedures for describe tools.
Expose stored procedures as MCP GENERIC tools.
```

The YAML remains the authoring source.

Snowflake becomes the runtime metadata source.

Success criteria:

```text
describe_domain(), get_metric_definitions(), and get_join_paths() read from Snowflake catalog tables.
```

---

## Iteration 6 — Role-aware metadata

Goal:

```text
Return metadata based on the current user role.
```

Implementation:

```text
Add DOMAIN_ROLE_ACCESS.
Filter describe tools by role.
Use Snowflake RBAC for actual data execution.
Use restricted roles for execution.
```

Success criteria:

```text
A user only sees metadata for domains and objects they are allowed to use.
Snowflake still enforces actual table access.
```

---

## Iteration 7 — Semantic validation

Goal:

```text
Make execute_sql validate generated SQL against the catalog.
```

Validation rules:

```text
Only allowed objects.
Only approved joins.
No direct fact-to-fact joins.
Bridge joins require safe aggregation behavior.
Certified metrics must include required filters.
Ratio metrics must use correct aggregate expression.
No disallowed columns.
No PII columns unless allowed.
```

Implementation options:

```text
Use a SQL parser in the application layer.
Use a Snowflake Python stored procedure for some checks.
Use both.
```

Success criteria:

```text
execute_sql rejects semantically invalid SQL before Snowflake runs it.
```

---

## Iteration 8 — Query evaluation suite

Goal:

```text
Measure agent quality over time.
```

Create an evaluation dataset:

```text
Question
Expected tables
Expected joins
Expected metrics
Expected filters
Expected SQL pattern
Expected result snapshot
```

Run the suite whenever:

```text
The YAML changes.
The catalog changes.
The agent prompt changes.
The model changes.
The SQL validation logic changes.
```

Success criteria:

```text
You can quantify whether the agent is improving or regressing.
```

---

## Iteration 9 — Profiling and observability

Goal:

```text
Give the agent and the platform better operational awareness.
```

Add:

```text
Table row counts
Column null rates
Column cardinality
Freshness
Top values for low-cardinality columns
Query history
Query cost
Execution time
Validation failures
Most used metrics
Most failed questions
```

Success criteria:

```text
The system becomes easier to debug and improve.
```

---

# 11. Recommended first working version

The fastest useful implementation is:

```text
1. Create semantic.yaml for one domain.
2. Implement describe_domain(domain_id), returning the YAML as JSON.
3. Implement execute_sql(sql), restricted to SELECT/WITH.
4. Give the agent instructions to always call describe_domain before generating SQL.
5. Give the agent access only to the gold schema or, better, an agent-facing view schema.
6. Test with 20 representative analytical questions.
```

Minimum agent tools:

```text
describe_domain(domain_id)
execute_sql(sql)
```

Minimum YAML content:

```text
Domain
Tables
Columns
Table grains
Relationships
Metrics
Examples
Rules
```

Minimum safety:

```text
Read-only execution
Restricted role
Restricted warehouse
Query timeout
Single statement
SELECT/WITH only
No SELECT *
```

This version is intentionally simple, but it proves the full loop.

---

# 12. Final target architecture

```text
Authoring layer:
  YAML files in Git

Deployment layer:
  YAML loader
  Metadata validation
  Catalog table MERGE scripts

Runtime metadata layer:
  GOVERNANCE.AGENT_CATALOG tables
  Stored procedures for describe tools

Agent tool layer:
  discover_domains()
  describe_domain()
  describe_tables()
  get_metric_definitions()
  get_join_paths()
  execute_sql()

Execution layer:
  Snowflake-managed MCP SYSTEM_EXECUTE_SQL
  read_only = true
  restricted warehouse
  restricted role
  query timeout

Security layer:
  Snowflake RBAC
  domain-role metadata filtering
  row access policies
  masking policies
  query tags
  audit logs

Quality layer:
  validation rules
  evaluation dataset
  query history analysis
  regression tests
```

The key idea is:

```text
Start with YAML.
Prove that the agent can generate useful raw SQL.
Then move metadata into Snowflake.
Then make metadata role-aware.
Then make execute_sql semantically validating.
```

This keeps the first implementation small while leaving a clear path toward a production-grade Snowflake-native agent.
