create role if not exists ecommerce_reader;
grant usage, monitor on warehouse compute_wh to role ecommerce_reader;

grant role ecommerce_reader to user pulsar_dev;

GRANT USAGE ON DATABASE BRAZILIAN_ECOMMERCE TO ROLE ecommerce_reader;
GRANT USAGE ON ALL SCHEMAS IN DATABASE BRAZILIAN_ECOMMERCE TO ROLE ecommerce_reader;
GRANT USAGE ON FUTURE SCHEMAS IN DATABASE BRAZILIAN_ECOMMERCE TO ROLE ecommerce_reader;
GRANT SELECT ON ALL TABLES IN DATABASE BRAZILIAN_ECOMMERCE TO ROLE ecommerce_reader;
GRANT SELECT ON FUTURE TABLES IN DATABASE BRAZILIAN_ECOMMERCE TO ROLE ecommerce_reader;
