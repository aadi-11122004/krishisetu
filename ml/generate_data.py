"""KrishiSetu — synthetic market data generator.

Creates ~2 years of daily, per-crop records:
  * mandi (APMC) retail price        -> what consumers pay via middlemen
  * farm-gate price on KrishiSetu    -> what farmers get on our platform
  * city demand in kg                -> retail demand with weekly cycle

Injected with seasonality, weekly cycles, festival spikes, price drift and
noise — realistic enough to train the forecasting models on.
"""

import os
import sqlite3
import sys

import numpy as np
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from ml.cropspec import CROP_SPEC, DOW_FACTOR, is_festival  # noqa: E402

DB = os.path.join(BASE, "krishisetu.db")
rng = np.random.default_rng(42)
DAYS = 730  # 2 years


def main():
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM price_history")

    start = date.today() - timedelta(days=DAYS - 1)
    rows = []
    for name, _emoji, _cat, _unit, base_p, base_d, peak, low in CROP_SPEC:
        drift_p = rng.uniform(-0.00008, 0.00035)   # slow price trend
        drift_d = rng.uniform(0.00005, 0.00040)    # demand growth
        for i in range(DAYS):
            d = start + timedelta(days=i)
            season = 1.28 if d.month in peak else (0.82 if d.month in low else 1.0)
            fest = 1.38 if is_festival(d) else 1.0
            trend_p = 1 + drift_p * i
            trend_d = 1 + drift_d * i

            market = base_p * season * trend_p * float(rng.lognormal(0, 0.055))
            farmgate = market * float(rng.uniform(0.72, 0.83))
            demand = (base_d * season * DOW_FACTOR[d.weekday()] * fest
                      * trend_d * float(rng.lognormal(0, 0.16)))

            rows.append((name, d.isoformat(), round(market, 2),
                         round(farmgate, 2), round(float(demand))))

    con.executemany(
        "INSERT INTO price_history(crop,date,market_price,farmgate_price,demand_kg) "
        "VALUES(?,?,?,?,?)", rows)
    con.commit()
    con.close()
    print(f"[generate_data] inserted {len(rows)} rows into price_history "
          f"({len(CROP_SPEC)} crops x {DAYS} days)")


if __name__ == "__main__":
    main()
