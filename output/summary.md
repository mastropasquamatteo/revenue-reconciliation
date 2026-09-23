# Reconciliation summary

## Status by check

| check_name | status | n_records | abs_diff_eur |
|---|---|---|---|
| CRM vs ERP | MATCHED | 305 | 0.00 |
| CRM vs ERP | REFERENCE_NORMALISED | 39 | 0.00 |
| CRM vs ERP | AMOUNT_MISMATCH | 29 | 94,839.59 |
| CRM vs ERP | SUGGESTED_MATCH | 19 | 0.00 |
| CRM vs ERP | MISSING_IN_ERP | 12 | 340,567.36 |
| CRM vs ERP | NO_CRM_OPPORTUNITY | 12 | 39,509.58 |
| CRM vs ERP | SPLIT_ORDER | 11 | 0.00 |
| CRM vs ERP | PERIOD_MISMATCH | 6 | 0.00 |
| CRM vs ERP | FX_EXPLAINED | 2 | 0.00 |
| ERP vs DWH | MATCHED | 399 | 0.00 |
| ERP vs DWH | MISSING_IN_DWH | 21 | 540,820.87 |
| ERP vs DWH | DWH_DUPLICATE | 14 | 424,694.81 |

## Detection check against injected issues

| injected_issue | expected_status | injected | detected | missed | false_alarms |
|---|---|---|---|---|---|
| missing_order | MISSING_IN_ERP | 12 | 12 | 0 | 0 |
| amount_mismatch | AMOUNT_MISMATCH | 29 | 29 | 0 | 0 |
| period_shift | PERIOD_MISMATCH | 6 | 6 | 0 | 0 |
| ref_format | REFERENCE_NORMALISED | 39 | 39 | 0 | 0 |
| ref_missing | SUGGESTED_MATCH | 19 | 19 | 0 | 0 |
| currency_invoiced | FX_EXPLAINED | 2 | 2 | 0 | 0 |
| split_order | SPLIT_ORDER | 11 | 11 | 0 | 0 |
| no_crm_opportunity | NO_CRM_OPPORTUNITY | 12 | 12 | 0 | 0 |
| dwh_duplicate | DWH_DUPLICATE | 14 | 14 | 0 | 0 |
| dwh_missing | MISSING_IN_DWH | 21 | 21 | 0 | 0 |
