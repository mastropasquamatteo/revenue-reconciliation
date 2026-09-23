-- 02_match_crm_erp.sql
-- Pair CRM opportunities with ERP orders.
--   Step 1: exact match on the normalised reference.
--   Step 2: for orders with no reference, suggest a match on
--           same customer + amount within 1% (in EUR) + dates within 30 days,
--           accepted only when the candidate is unique on both sides.

DROP TABLE IF EXISTS match_by_ref;
CREATE TABLE match_by_ref AS
SELECT c.opp_id, e.order_id, 'REFERENCE' AS match_method
FROM stg_crm c
JOIN stg_erp e ON e.opp_ref = c.opp_id;

DROP TABLE IF EXISTS match_candidates;
CREATE TABLE match_candidates AS
SELECT c.opp_id, e.order_id
FROM stg_erp e
JOIN stg_crm c
  ON  c.account_id = e.customer_code
 AND  c.stage = 'Closed Won'
 AND  abs(e.amount_eur - c.amount_eur) <= 0.01 * c.amount_eur
 AND  abs(julianday(e.order_date) - julianday(c.close_date)) <= 30
WHERE e.opp_ref IS NULL
  AND c.opp_id NOT IN (SELECT opp_id FROM match_by_ref);

DROP TABLE IF EXISTS match_suggested;
CREATE TABLE match_suggested AS
SELECT opp_id, order_id, 'SUGGESTED' AS match_method
FROM match_candidates
WHERE order_id IN (SELECT order_id FROM match_candidates GROUP BY order_id HAVING count(*) = 1)
  AND opp_id   IN (SELECT opp_id   FROM match_candidates GROUP BY opp_id   HAVING count(*) = 1);

DROP TABLE IF EXISTS crm_erp_pairs;
CREATE TABLE crm_erp_pairs AS
SELECT * FROM match_by_ref
UNION ALL
SELECT * FROM match_suggested;
