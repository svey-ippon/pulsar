USE ROLE ACCOUNTADMIN;

-- 1. Rôle d'administration du projet
CREATE ROLE IF NOT EXISTS PULSAR_ADM;

-- 2. Hiérarchie : PULSAR_ADM sous SYSADMIN (visibilité conservée)
GRANT ROLE PULSAR_ADM TO ROLE SYSADMIN;

-- 3. Warehouse dédié
--    OWNERSHIP donné à PULSAR_ADM => le rôle détient implicitement TOUS les
--    privilèges sur le warehouse (USAGE, OPERATE, MONITOR, MODIFY) sans grant
--    explicite. Donc tout user portant PULSAR_ADM peut l'utiliser (USAGE),
--    le piloter (OPERATE : resume/suspend), suivre sa conso et ses requêtes
--    (MONITOR) et le reconfigurer (MODIFY : resize, auto_suspend…).
CREATE WAREHOUSE IF NOT EXISTS PULSAR_WH
  WAREHOUSE_SIZE      = 'XSMALL'
  AUTO_SUSPEND        = 60
  AUTO_RESUME         = TRUE
  INITIALLY_SUSPENDED = TRUE;
GRANT OWNERSHIP ON WAREHOUSE PULSAR_WH TO ROLE PULSAR_ADM;

-- 4. Base de données, transférée en ownership à PULSAR_ADM
CREATE DATABASE IF NOT EXISTS PULSAR_DB;
GRANT OWNERSHIP ON DATABASE PULSAR_DB          TO ROLE PULSAR_ADM;
GRANT OWNERSHIP ON ALL SCHEMAS IN DATABASE PULSAR_DB TO ROLE PULSAR_ADM;
