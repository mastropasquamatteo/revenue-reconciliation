"""
Generate a synthetic dataset for a fictional B2B equipment vendor.

Three systems describe the same sales from different angles:
  - CRM  (opportunities, what sales says was won)
  - ERP  (orders, what was actually invoiced)
  - DWH  (bookings, what the reporting layer shows)

A known set of problems is injected on purpose and written to
data/injected_issues.csv, so the reconciliation can be checked
against a ground truth instead of being eyeballed.

Everything here is invented. Run:  python generate_data.py
"""

from datetime import date, timedelta
from pathlib import Path
import calendar

import numpy as np
import pandas as pd

SEED = 42
N_ACCOUNTS = 120
N_OPPORTUNITIES = 600
N_ORDERS_WITHOUT_CRM = 12
YEAR = 2025

DATA_DIR = Path(__file__).parent / "data"

# Share of Closed Won opportunities that receive each injected issue.
# Each opportunity gets at most one issue, so the ground truth stays clean.
ISSUE_WEIGHTS = {
    "none": 0.62,
    "missing_order": 0.04,       # won in CRM, never ordered in ERP
    "amount_mismatch": 0.05,     # discount applied in ERP after the deal closed
    "period_shift": 0.05,        # closed on the last days of a month, ordered next month
    "ref_format": 0.07,          # CRM reference typed badly in ERP (case, spaces, underscore)
    "ref_missing": 0.04,         # CRM reference left empty in ERP
    "currency_invoiced": 0.05,   # CRM in USD/GBP, ERP invoiced in EUR: not an error
    "dwh_duplicate": 0.04,       # order loaded twice in the DWH
    "dwh_missing": 0.04,         # order never loaded in the DWH
    "split_order": 0.03,         # one deal invoiced as two ERP orders
}

CURRENCIES = ["EUR", "USD", "GBP"]
CURRENCY_P = [0.70, 0.20, 0.10]


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def build_fx(rng: np.random.Generator) -> pd.DataFrame:
    """Monthly average rates to EUR with a small random walk."""
    rows = []
    usd, gbp = 0.92, 1.17
    for m in range(1, 13):
        usd *= 1 + rng.normal(0, 0.012)
        gbp *= 1 + rng.normal(0, 0.008)
        key = f"{YEAR}-{m:02d}"
        rows += [
            {"month": key, "currency": "EUR", "rate_to_eur": 1.0},
            {"month": key, "currency": "USD", "rate_to_eur": round(usd, 4)},
            {"month": key, "currency": "GBP", "rate_to_eur": round(gbp, 4)},
        ]
    return pd.DataFrame(rows)


def build_accounts(rng: np.random.Generator) -> pd.DataFrame:
    regions = ["North", "South", "Central", "Export"]
    return pd.DataFrame(
        {
            "account_id": [f"C{n:04d}" for n in range(1, N_ACCOUNTS + 1)],
            "region": rng.choice(regions, N_ACCOUNTS),
            "currency": rng.choice(CURRENCIES, N_ACCOUNTS, p=CURRENCY_P),
        }
    )


def messy_ref(opp_id: str, rng: np.random.Generator) -> str:
    """Typical ways a reference gets mangled when typed by hand."""
    variant = rng.integers(0, 4)
    if variant == 0:
        return opp_id.lower()
    if variant == 1:
        return f" {opp_id} "
    if variant == 2:
        return opp_id.replace("-", "_")
    return opp_id.lower().replace("-", "_") + " "


def main() -> None:
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(exist_ok=True)

    fx = build_fx(rng)
    rate = {(r.month, r.currency): r.rate_to_eur for r in fx.itertuples()}
    accounts = build_accounts(rng)

    opps, orders, bookings, issues = [], [], [], []
    order_seq = 0

    def next_order_id() -> str:
        nonlocal order_seq
        order_seq += 1
        return f"SO-{order_seq:05d}"

    issue_names = list(ISSUE_WEIGHTS)
    issue_p = np.array(list(ISSUE_WEIGHTS.values()))
    issue_p = issue_p / issue_p.sum()

    for n in range(1, N_OPPORTUNITIES + 1):
        opp_id = f"OPP-{n:05d}"
        acc = accounts.iloc[rng.integers(0, N_ACCOUNTS)]
        stage = rng.choice(["Closed Won", "Closed Lost", "Open"], p=[0.70, 0.20, 0.10])
        month = int(rng.integers(1, 13))
        last_day = calendar.monthrange(YEAR, month)[1]
        close = date(YEAR, month, int(rng.integers(1, last_day + 1)))
        amount = round(float(rng.lognormal(mean=10.2, sigma=0.7)), 2)
        currency = acc.currency

        issue = "none"
        if stage == "Closed Won":
            issue = rng.choice(issue_names, p=issue_p)
            # Keep each issue unambiguous:
            # a month shift on a non-EUR deal would also move the FX rate,
            # and FX invoicing only makes sense for non-EUR deals.
            if issue == "period_shift" and currency != "EUR":
                issue = "none"
            if issue == "currency_invoiced" and currency == "EUR":
                issue = "none"
            if issue == "period_shift":
                close = date(YEAR, month, last_day - int(rng.integers(0, 3)))
                if month == 12:  # keep everything inside the year
                    issue = "none"

        opps.append(
            {
                "opp_id": opp_id,
                "account_id": acc.account_id,
                "region": acc.region,
                "stage": stage,
                "close_date": close.isoformat(),
                "amount": amount,
                "currency": currency,
            }
        )

        if stage != "Closed Won":
            continue

        if issue != "none":
            issues.append({"issue_type": issue, "opp_id": opp_id, "order_id": None})

        if issue == "missing_order":
            continue

        order_id = next_order_id()
        if issue != "none":
            issues[-1]["order_id"] = order_id

        # Default: ordered in the same month as the close, same amount and currency.
        days_left = calendar.monthrange(YEAR, close.month)[1] - close.day
        order_date = close + timedelta(days=int(rng.integers(0, days_left + 1)))
        net = amount
        inv_currency = currency
        ref = opp_id

        if issue == "amount_mismatch":
            net = round(amount * (1 - rng.uniform(0.03, 0.15)), 2)
        elif issue == "period_shift":
            order_date = close + timedelta(days=int(rng.integers(3, 10)))
        elif issue == "ref_format":
            ref = messy_ref(opp_id, rng)
        elif issue == "ref_missing":
            ref = ""
        elif issue == "currency_invoiced":
            net = round(amount * rate[(month_key(close), currency)], 2)
            inv_currency = "EUR"

        order_lines = [(order_id, net)]
        if issue == "split_order":
            first = round(net * rng.uniform(0.4, 0.7), 2)
            order_lines = [(order_id, first), (next_order_id(), round(net - first, 2))]

        for oid, part in order_lines:
            orders.append(
                {
                    "order_id": oid,
                    "crm_opp_ref": ref,
                    "customer_code": acc.account_id,
                    "order_date": order_date.isoformat(),
                    "net_amount": part,
                    "currency": inv_currency,
                }
            )

        if issue == "dwh_missing":
            continue
        copies = 2 if issue == "dwh_duplicate" else 1
        for oid, part in order_lines:
            amount_eur = round(part * rate[(month_key(order_date), inv_currency)], 2)
            for _ in range(copies):
                bookings.append(
                    {
                        "source_order_id": oid,
                        "booking_month": month_key(order_date),
                        "amount_eur": amount_eur,
                    }
                )

    # Orders with no CRM opportunity at all (spare parts, service calls...).
    for _ in range(N_ORDERS_WITHOUT_CRM):
        acc = accounts.iloc[rng.integers(0, N_ACCOUNTS)]
        month = int(rng.integers(1, 13))
        d = date(YEAR, month, int(rng.integers(1, calendar.monthrange(YEAR, month)[1] + 1)))
        net = round(float(rng.lognormal(mean=8.0, sigma=0.6)), 2)
        order_id = next_order_id()
        orders.append(
            {
                "order_id": order_id,
                "crm_opp_ref": "",
                "customer_code": acc.account_id,
                "order_date": d.isoformat(),
                "net_amount": net,
                "currency": acc.currency,
            }
        )
        bookings.append(
            {
                "source_order_id": order_id,
                "booking_month": month_key(d),
                "amount_eur": round(net * rate[(month_key(d), acc.currency)], 2),
            }
        )
        issues.append({"issue_type": "no_crm_opportunity", "opp_id": None, "order_id": order_id})

    bookings_df = pd.DataFrame(bookings).sample(frac=1, random_state=SEED).reset_index(drop=True)
    bookings_df.insert(0, "booking_id", [f"BK-{i:06d}" for i in range(1, len(bookings_df) + 1)])

    pd.DataFrame(opps).to_csv(DATA_DIR / "crm_opportunities.csv", index=False)
    pd.DataFrame(orders).to_csv(DATA_DIR / "erp_orders.csv", index=False)
    bookings_df.to_csv(DATA_DIR / "dwh_bookings.csv", index=False)
    fx.to_csv(DATA_DIR / "fx_rates.csv", index=False)
    pd.DataFrame(issues).to_csv(DATA_DIR / "injected_issues.csv", index=False)

    print(f"CRM opportunities: {len(opps)}")
    print(f"ERP orders:        {len(orders)}")
    print(f"DWH bookings:      {len(bookings_df)}")
    print(f"Injected issues:   {len(issues)}")
    print(pd.DataFrame(issues)["issue_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
