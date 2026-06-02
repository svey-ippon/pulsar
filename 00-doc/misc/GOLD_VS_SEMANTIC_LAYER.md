# Gold vs Semantic Layer Separation

This document defines the separation rule for the Olist Snowflake Intelligence POC.

## Principle

Gold owns reusable analytical data structures. The semantic layer owns business-facing meaning and
metric exposure.

Do not use the semantic layer as a replacement for data modeling. If a calculation requires a
stable grain, deduplication, attribution, ranking, cohorting, customer segmentation, distance
calculation, or multi-stage aggregation, model it in Gold first. Then expose it through the semantic
layer with precise names, descriptions, relationships, filters, and verified queries.

## What Gold Should Own

Gold should contain business-ready views or tables with explicit grains.

Gold owns:

- conformed dimensions such as customers, products, sellers, categories, and geography;
- atomic fact views such as orders, order items, payments, and reviews;
- stable grain declarations through one row per business event or entity;
- reusable derived facts such as `delay_days`, `approval_delay_days`, `item_revenue`,
  `freight_value`, `payment_value`, and `seller_customer_distance_km`;
- fan-out-safe bridges such as order/category membership and order/category/review attribution;
- reusable analytical marts such as customer cohorts, repeat-customer segments, RFM, seller
  delivery performance, basket summaries, category Pareto, and seller scorecards;
- transformations that need window functions, `HAVING`, `NTILE`, `RANK`, `LAG`, or multi-step CTEs;
- business transformations that must be audited independently from AI-generated SQL;
- performance-sensitive or high-risk logic that should not be regenerated differently for each
  natural-language question.

Gold should be documented with:

- the grain of every model;
- the reason the model exists;
- the source tables used;
- the business conventions embedded in the model;
- any attribution choice, especially when facts cross grains;
- whether revenue means merchandise revenue or collected payment value;
- whether a delivered-order filter is applied.

## What The Semantic Layer Should Own

The semantic layer should expose Gold through business concepts.

The semantic layer owns:

- logical tables/entities mapped to Gold models;
- relationships between entities;
- metrics and their aggregation behavior;
- dimensions available for slicing and filtering;
- facts used to build metrics;
- derived metrics that are simple combinations of governed metrics;
- descriptions, labels, synonyms, and examples that guide business users and AI agents;
- business filters such as delivered orders, late deliveries, repeat customers, or top categories;
- verified queries used as examples and evaluation ground truth;
- ambiguity handling guidance such as "best sellers requires a KPI" or "customers means physical
  customers unless stated otherwise";
- access exposure: what should be visible to business users and what should remain internal.

The semantic layer should not own:

- raw table cleanup;
- deduplication across source grains;
- review-to-category attribution;
- customer-level cohort construction;
- repeat-customer segmentation before revenue aggregation;
- distance calculations from latitude/longitude;
- complex ranking or distribution preparation when the result is a reusable analytical object;
- large SQL helpers whose correctness should be tested outside the semantic model.

## Decision Rules

Use Gold when:

- the logic has a reusable grain;
- the logic joins tables with different grains;
- a wrong join can duplicate facts;
- the logic requires a window function or multi-step aggregation;
- the logic is likely to be reused by several questions or dashboards;
- the result needs independent validation or cost optimization.

Use the semantic layer when:

- the logic is a metric definition over a Gold grain;
- the logic is a simple ratio of governed metrics;
- the logic is a label, synonym, description, or business alias;
- the logic tells tools which dimensions are valid for a metric;
- the logic provides examples or verified queries for natural-language generation.

## References

- [Kimball Group, "Grain"](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/grain/):
  dimensional design starts by declaring the grain, and different grains should not be mixed in the
  same fact table.
- [Databricks, "What is the medallion lakehouse architecture?"](https://docs.databricks.com/aws/en/lakehouse/medallion):
  Gold is the enriched layer for dimensional modeling and aggregation for business users.
- [Snowflake, "Overview of semantic views"](https://docs.snowflake.com/en/user-guide/views-semantic/overview):
  semantic views store business concepts, metrics, entities, relationships, dimensions, and facts
  as metadata over physical data.
- [dbt, "Semantic models"](https://docs.getdbt.com/docs/build/semantic-models):
  semantic models define entities, dimensions, and metric building blocks over existing data
  models.
