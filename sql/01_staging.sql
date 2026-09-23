-- 01_staging.sql
-- Clean and standardise each source before any matching.
-- Every amount is converted to EUR with the average rate of its own month.

DROP VIEW IF EXISTS stg_crm;
CREATE VIEW stg_crm AS
SELECT
    o.opp_id,
    o.account_id,
    o.region,
    o.stage,
    o.close_date,
    substr(o.close_date, 1, 7)          AS close_month,
    o.amount,
    o.currency,
    round(o.amount * fx.rate_to_eur, 2) AS amount_eur
FROM crm_opportunities o
JOIN fx_rates fx
  ON fx.month = substr(o.close_date, 1, 7)
 AND fx.currency = o.currency;

-- The CRM reference in ERP is typed by hand.
-- Normalisation: trim spaces, upper case, underscore -> hyphen.
DROP VIEW IF EXISTS stg_erp;
CREATE VIEW stg_erp AS
SELECT
    e.order_id,
    e.crm_opp_ref                                              AS opp_ref_raw,
    nullif(upper(replace(trim(coalesce(e.crm_opp_ref, '')), '_', '-')), '') AS opp_ref,
    e.customer_code,
    e.order_date,
    substr(e.order_date, 1, 7)          AS order_month,
    e.net_amount,
    e.currency,
    round(e.net_amount * fx.rate_to_eur, 2) AS amount_eur
FROM erp_orders e
JOIN fx_rates fx
  ON fx.month = substr(e.order_date, 1, 7)
 AND fx.currency = e.currency;
