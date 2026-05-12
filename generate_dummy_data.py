"""
Generate realistic dummy bank data for portfolio demonstration.
Run once:  python generate_dummy_data.py
Produces Bank1/ (xlsx per year), Bank2/ (xlsx 25-col), Bank3/ (csv).
"""
import calendar
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
random.seed(42)
BASE = Path(__file__).parent

# ── Merchant lists ────────────────────────────────────────────────────────────
M = {
    "supermarket":     ["City Supermarket", "Fresh Market", "Green Grocers",
                        "Daily Foods", "Market Plus", "Intl Supermarket"],
    "restaurant":      ["The Bistro", "City Burger", "Local Kitchen",
                        "Corner Café", "The Grill House", "Sakura Restaurant"],
    "bakery":          ["Morning Bakery", "City Patisserie", "The Bread Shop",
                        "Sweet Corner Bakery"],
    "pharmacy":        ["Central Pharmacy", "Health Plus Pharmacy"],
    "fuel":            ["Highway Fuel", "City Gas Station", "Express Petrol",
                        "Motorway Petrol"],
    "amazon":          ["Amazon.com", "Amazon Prime", "Amazon Marketplace"],
    "parking":         ["City Parking", "Central Car Park", "Station Parking",
                        "Mall Car Park"],
    "toll":            ["Highway Toll A1", "North Motorway", "City Bypass Toll",
                        "East Toll Road"],
    "internet-mobile": ["TeleCom Mobile", "NetConnect Home"],
    "diy":             ["BuildRight", "Home Depot", "Tool Store", "Paint Express"],
    "sports":          ["SportZone", "Gym Central", "Active Life Club"],
    "hotel":           ["City Hotel", "Grand Suites", "The Lodge",
                        "Seaside Hotel", "Airport Hotel"],
    "flight":          ["Air Connect", "Euro Airways", "Budget Airlines"],
    "taxi":            ["City Taxi", "QuickCab", "Airport Taxi"],
    "dept. store":     ["The Mall", "City Department Store"],
    "atm":             ["ATM Cash Withdrawal"],
    "utilities":       ["City Electric Co.", "Water Services", "Gas Supply Co."],
    "rent":            ["Property Management Co."],
    "rental income":   ["Tenant Monthly Payment"],
    "salary":          ["Employer Corp S.A."],
    "refund":          ["Amazon Refund", "Store Refund"],
    "loan":            ["Bank Loan Payment"],
    "investment":      ["Interactive Brokers"],
    "own-b2":          ["Transfer to Bank2"],
    "own-b3":          ["Transfer to Bank3"],
    "topup":           ["Payment from Bank Account"],
    "transfer-out":    ["Transfer to Bank Account"],
    "card-intl":       ["Airport Bistro", "Holiday Restaurant", "Beach Café",
                        "Travel Grocery", "Holiday Pharmacy"],
}


def pick(cat: str) -> str:
    return random.choice(M[cat])


def md(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def clamp(year: int, month: int, day) -> int:
    return min(int(day), md(year, month))


# ── Bank1: main current account (xlsx, one file per year) ────────────────────
def gen_bank1() -> None:
    out = BASE / "Bank1"
    out.mkdir(exist_ok=True)

    balance = 1_500.0

    for year in range(2020, 2027):
        rows = []
        entry = 1
        months = range(1, 6) if year == 2026 else range(1, 13)

        for month in months:
            mdays = md(year, month)
            txns: list[tuple] = []  # (day, description, amount)

            # Fixed monthly
            txns.append((1,  pick("salary"),         round(float(rng.uniform(3200, 3500)), 2)))
            txns.append((3,  pick("rental income"),   800.0))
            txns.append((5,  pick("rent"),           -850.0))
            txns.append((8,  pick("utilities"),      -round(float(rng.uniform(100, 180)), 2)))
            txns.append((10, pick("internet-mobile"),-round(float(rng.uniform(50, 65)), 2)))

            # Monthly topup to Bank3
            txns.append((int(rng.integers(1, 6)), pick("own-b3"),
                         -round(float(rng.uniform(350, 500)), 2)))

            # Occasional savings transfer to Bank2
            if rng.random() < 0.45 and year >= 2021:
                txns.append((int(rng.integers(15, 25)), pick("own-b2"),
                             -round(float(rng.uniform(500, 2000)), 2)))

            # Supermarket 8-12×
            for _ in range(int(rng.integers(8, 13))):
                txns.append((random.randint(1, mdays), pick("supermarket"),
                             -round(float(rng.uniform(30, 120)), 2)))
            # Restaurant 5-9×
            for _ in range(int(rng.integers(5, 10))):
                txns.append((random.randint(1, mdays), pick("restaurant"),
                             -round(float(rng.uniform(15, 60)), 2)))
            # Bakery 8-14×
            for _ in range(int(rng.integers(8, 15))):
                txns.append((random.randint(1, mdays), pick("bakery"),
                             -round(float(rng.uniform(3, 15)), 2)))
            # Fuel 2-4×
            for _ in range(int(rng.integers(2, 5))):
                txns.append((random.randint(1, mdays), pick("fuel"),
                             -round(float(rng.uniform(50, 80)), 2)))
            # Parking 3-7×
            for _ in range(int(rng.integers(3, 8))):
                txns.append((random.randint(1, mdays), pick("parking"),
                             -round(float(rng.uniform(2, 20)), 2)))
            # Toll 3-7×
            for _ in range(int(rng.integers(3, 8))):
                txns.append((random.randint(1, mdays), pick("toll"),
                             -round(float(rng.uniform(3, 15)), 2)))
            # Amazon 1-4×
            for _ in range(int(rng.integers(1, 5))):
                txns.append((random.randint(1, mdays), pick("amazon"),
                             -round(float(rng.uniform(10, 150)), 2)))
            # Pharmacy 1-3×
            for _ in range(int(rng.integers(1, 4))):
                txns.append((random.randint(1, mdays), pick("pharmacy"),
                             -round(float(rng.uniform(10, 40)), 2)))
            # ATM 1-2×
            for _ in range(int(rng.integers(1, 3))):
                txns.append((random.randint(1, mdays), pick("atm"),
                             -round(float(rng.uniform(100, 200)), 2)))

            # Occasional
            if rng.random() < 0.35:
                txns.append((random.randint(1, mdays), pick("diy"),
                             -round(float(rng.uniform(20, 250)), 2)))
            if rng.random() < 0.50:
                txns.append((random.randint(1, mdays), pick("sports"),
                             -round(float(rng.uniform(10, 50)), 2)))
            if rng.random() < 0.20:
                txns.append((random.randint(1, mdays), pick("hotel"),
                             -round(float(rng.uniform(80, 300)), 2)))
            if rng.random() < 0.12:
                txns.append((random.randint(1, mdays), pick("flight"),
                             -round(float(rng.uniform(80, 350)), 2)))
            if rng.random() < 0.35:
                txns.append((random.randint(1, mdays), pick("taxi"),
                             -round(float(rng.uniform(10, 35)), 2)))
            if rng.random() < 0.25:
                txns.append((random.randint(1, mdays), pick("dept. store"),
                             -round(float(rng.uniform(20, 150)), 2)))
            if rng.random() < 0.15:
                txns.append((random.randint(1, mdays), pick("refund"),
                              round(float(rng.uniform(5, 100)), 2)))

            txns.sort(key=lambda x: x[0])

            for day, desc, amount in txns:
                dt = date(year, month, clamp(year, month, day))
                balance = round(balance + amount, 2)
                rows.append({
                    "Date": dt,
                    "Value Date": dt,
                    "Description": desc,
                    "Amount": round(amount, 2),
                    "Balance": balance,
                    "Entry No.": entry,
                })
                entry += 1

        df = (pd.DataFrame(rows)
              .sort_values("Date", ascending=False)
              .reset_index(drop=True))
        df.to_excel(out / f"{year}.xlsx", sheet_name="movements", index=False)
        print(f"  Bank1/{year}.xlsx   {len(df):4d} rows   balance {balance:>10,.2f} €")


# ── Bank2: savings account (25-column xlsx, 2024-2026) ───────────────────────
def gen_bank2() -> None:
    out = BASE / "Bank2"
    out.mkdir(exist_ok=True)

    # Build transaction list
    txns: list[tuple] = []  # (date, description, income, expense)

    txns.append((date(2024, 6, 5),  "Account Opening",        20.0,     0.0))
    txns.append((date(2024, 7, 1),  "Property Sale Proceeds", 80_000.0, 0.0))

    cur = date(2024, 7, 1)
    end = date(2026, 5, 12)
    while cur <= end:
        y, m = cur.year, cur.month
        mdays = md(y, m)

        # Monthly loan repayment
        txns.append((date(y, m, 1), pick("loan"), 0.0, 790.94))

        # Transfer in from Bank1
        d_in = clamp(y, m, int(rng.integers(3, 8)))
        txns.append((date(y, m, d_in), "Transfer from Bank1",
                     round(float(rng.uniform(500, 1500)), 2), 0.0))

        # Occasional expense
        if rng.random() < 0.5:
            d_ex = random.randint(1, mdays)
            txns.append((date(y, m, d_ex), pick("utilities"),
                         0.0, round(float(rng.uniform(30, 120)), 2)))
        if rng.random() < 0.25:
            d_inv = random.randint(1, mdays)
            txns.append((date(y, m, d_inv), pick("investment"),
                         0.0, round(float(rng.uniform(100, 500)), 2)))

        cur = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)

    txns = [t for t in txns if t[0] <= end]
    txns.sort(key=lambda x: x[0])

    # Build running balance and data rows
    balance = 0.0
    data_rows = []
    for dt, desc, income, expense in txns:
        balance = round(balance + income - expense, 2)
        data_rows.append([
            None, "1234 5678 90 0100000001", "0001", "EUR",
            dt, dt,
            income if income > 0 else None,
            expense if expense > 0 else None,
            balance if balance >= 0 else None,
            abs(balance) if balance < 0 else None,
            "01", "001", "000000000000", None,
            desc, None, None,
            None, None, None, None, None, None, None, None,
        ])

    col25 = [
        None, "Account Number", "Branch", "Currency",
        "Operation Date", "Value Date",
        "Income (+)", "Expense (-)",
        "Balance (+)", "Balance (-)",
        "Category", "Sub-category", "Reference 1", "Reference 2",
        "Description 1", "Description 2", "Description 3",
        "Description 4", "Description 5", "Description 6",
        "Description 7", "Description 8", "Description 9",
        "Description 10", None,
    ]

    all_rows = [
        [None] * 25,
        [None, "MOVEMENTS FROM: 01/06/2024 TO: 12/05/2026"] + [None] * 23,
        [None] * 25,
        col25,
        *data_rows,
    ]

    pd.DataFrame(all_rows).to_excel(
        out / "2024-2026.xlsx", index=False, header=False
    )
    print(f"  Bank2/2024-2026.xlsx  {len(data_rows):4d} rows   balance {balance:>10,.2f} €")


# ── Bank3: digital card account (csv, 2022-2026) ──────────────────────────────
def gen_bank3() -> None:
    out = BASE / "Bank3"
    out.mkdir(exist_ok=True)

    # Bank3 is a travel/digital card — used mainly while travelling, not daily.
    # Topup is demand-driven: triggered when balance falls below 200€.
    rows = []
    balance = 500.0
    current = date(2022, 12, 31)
    end = date(2026, 5, 11)

    # Travel-oriented card: ~18% chance of a transaction on any given day
    DAILY_PROB = 0.18
    TRAVEL_CATS = [
        "restaurant", "bakery", "pharmacy", "amazon",
        "hotel", "flight", "taxi", "card-intl",
    ]

    while current <= end:
        y, m = current.year, current.month

        # Top up whenever balance drops below 200 €
        if balance < 200.0:
            amount = round(float(rng.uniform(400, 600)), 2)
            balance = round(balance + amount, 2)
            rows.append({
                "Type": "Topup", "Product": "Current",
                "Started Date": f"{current} 09:00:00",
                "Completed Date": f"{current} 09:15:00",
                "Description": pick("topup"),
                "Amount": amount, "Fee": 0.0,
                "Currency": "EUR", "State": "COMPLETED",
                "Balance": balance,
            })

        # Card transaction
        if rng.random() < DAILY_PROB:
            cat = random.choice(TRAVEL_CATS)
            merchant = pick(cat) if cat != "card-intl" else pick("card-intl")
            amount = -round(float(rng.uniform(8, 100)), 2)
            fee = round(float(rng.uniform(0, 0.8)), 2) if rng.random() < 0.12 else 0.0
            balance = round(balance + amount, 2)
            h, mn = int(rng.integers(8, 22)), int(rng.integers(0, 60))
            rows.append({
                "Type": "Card Payment", "Product": "Current",
                "Started Date": f"{current} {h:02d}:{mn:02d}:00",
                "Completed Date": f"{current + timedelta(days=1)} 14:00:00",
                "Description": merchant,
                "Amount": amount, "Fee": fee,
                "Currency": "EUR", "State": "COMPLETED",
                "Balance": balance,
            })

        # ATM: ~once per quarter abroad
        if rng.random() < 0.006:
            amount = -round(float(rng.uniform(80, 250)), 2)
            balance = round(balance + amount, 2)
            rows.append({
                "Type": "ATM", "Product": "Current",
                "Started Date": f"{current} 14:00:00",
                "Completed Date": f"{current} 14:05:00",
                "Description": "Cash Withdrawal at International ATM",
                "Amount": amount, "Fee": round(abs(amount) * 0.02, 2),
                "Currency": "EUR", "State": "COMPLETED",
                "Balance": balance,
            })

        # Occasional transfer out (~twice a year)
        if rng.random() < 0.002:
            amount = -round(float(rng.uniform(100, 300)), 2)
            balance = round(balance + amount, 2)
            rows.append({
                "Type": "Transfer", "Product": "Current",
                "Started Date": f"{current} 10:00:00",
                "Completed Date": f"{current} 10:00:00",
                "Description": pick("transfer-out"),
                "Amount": amount, "Fee": 0.0,
                "Currency": "EUR", "State": "COMPLETED",
                "Balance": balance,
            })

        current += timedelta(days=1)

    pd.DataFrame(rows).to_csv(out / "all.csv", index=False)
    print(f"  Bank3/all.csv         {len(rows):4d} rows   balance {balance:>10,.2f} €")


if __name__ == "__main__":
    print("Generating dummy bank data…\n")
    gen_bank1()
    gen_bank2()
    gen_bank3()
    print("\nDone.")
