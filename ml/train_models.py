"""KrishiSetu — ML training pipeline.

Trains TWO real models per crop on the synthetic 2-year market history:
  1. PRICE model   : RandomForestRegressor -> next-day mandi price
                     (features: calendar, festival, recent demand & price lags)
  2. DEMAND model  : RandomForestRegressor -> next-day city demand (kg)
                     (uses the predicted price for future days = recursive forecast)

Then produces a recursive 14-DAY FORECAST for every crop and persists:
  * ml/models/models.pkl   all trained models
  * ml/models/metrics.json hold-out accuracy (MAE / MAPE)
  * demand_forecast table  (crop, date, pred_kg)
  * price_forecast  table  (crop, date, market_pred, suggested_price)
"""

import json
import os
import sqlite3
import sys
from datetime import date, timedelta

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from ml.cropspec import is_festival  # noqa: E402

DB = os.path.join(BASE, "krishisetu.db")
MODELS_DIR = os.path.join(BASE, "ml", "models")
HORIZON = 14
TEST_DAYS = 60


def load_series():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT crop,date,market_price,demand_kg FROM price_history ORDER BY crop,date"
    ).fetchall()
    con.close()
    series = {}
    for crop, d, mkt, dem in rows:
        s = series.setdefault(crop, {"dates": [], "mkt": [], "dem": []})
        s["dates"].append(d)
        s["mkt"].append(float(mkt))
        s["dem"].append(float(dem))
    return series


def cal_feats(dstr):
    d = date.fromisoformat(dstr)
    return d.month, d.weekday(), is_festival(d)


def price_feats(month, dow, fest, dem, mkt, t):
    """Features for predicting market price on day t (only uses info <= t-1)."""
    return [month, dow, fest,
            dem[t - 1], dem[t - 7], float(np.mean(dem[t - 7:t])),
            mkt[t - 1], mkt[t - 7], float(np.mean(mkt[t - 7:t]))]


def demand_feats(month, dow, fest, dem, mkt_t, mkt, t):
    """Features for demand on day t; includes SAME-day price (known in training,
    predicted during recursive forecasting)."""
    return [month, dow, fest,
            dem[t - 1], dem[t - 7], float(np.mean(dem[t - 7:t])),
            mkt_t, mkt[t - 1], float(np.mean(mkt[t - 7:t]))]


def train_one(crop, s):
    n = len(s["mkt"])
    months, dows, fests = [], [], []
    for dstr in s["dates"]:
        m, dw, f = cal_feats(dstr)
        months.append(m); dows.append(dw); fests.append(f)

    Xp, yp, Xd, yd = [], [], [], []
    for t in range(14, n):
        m, dw, f = months[t], dows[t], fests[t]
        Xp.append(price_feats(m, dw, f, s["dem"], s["mkt"], t))
        yp.append(s["mkt"][t])
        Xd.append(demand_feats(m, dw, f, s["dem"], s["mkt"][t], s["mkt"], t))
        yd.append(s["dem"][t])
    Xp, yp, Xd, yd = map(np.array, (Xp, yp, Xd, yd))

    split = len(yp) - TEST_DAYS
    rf_price = RandomForestRegressor(n_estimators=180, max_depth=12,
                                     min_samples_leaf=3, random_state=0, n_jobs=-1)
    rf_dem = RandomForestRegressor(n_estimators=180, max_depth=12,
                                   min_samples_leaf=3, random_state=0, n_jobs=-1)

    # hold-out evaluation (one-step)
    rf_price.fit(Xp[:split], yp[:split])
    p_pred = rf_price.predict(Xp[split:])
    price_mae = float(np.mean(np.abs(p_pred - yp[split:])))
    price_mape = float(np.mean(np.abs(p_pred - yp[split:]) / yp[split:]) * 100)

    rf_dem.fit(Xd[:split], yd[:split])
    d_pred = rf_dem.predict(Xd[split:])
    dem_mae = float(np.mean(np.abs(d_pred - yd[split:])))
    dem_mape = float(np.mean(np.abs(d_pred - yd[split:]) / yd[split:]) * 100)

    # final models trained on ALL data for forecasting
    rf_price.fit(Xp, yp)
    rf_dem.fit(Xd, yd)
    return rf_price, rf_dem, {
        "price_mae": round(price_mae, 2), "price_mape": round(price_mape, 1),
        "demand_mae": round(dem_mae), "demand_mape": round(dem_mape, 1),
    }


def recursive_forecast(crop, s, rf_price, rf_dem):
    """14-day recursive price + demand forecast starting tomorrow."""
    dem_h, mkt_h = list(s["dem"]), list(s["mkt"])
    last_date = date.fromisoformat(s["dates"][-1])
    out_dem, out_price = [], []
    for k in range(1, HORIZON + 1):
        d = last_date + timedelta(days=k)
        month, dow, fest = d.month, d.weekday(), is_festival(d)

        fp = [month, dow, fest,
              dem_h[-1], dem_h[-7], float(np.mean(dem_h[-7:])),
              mkt_h[-1], mkt_h[-7], float(np.mean(mkt_h[-7:]))]
        p = float(rf_price.predict([fp])[0])

        fd = [month, dow, fest,
              dem_h[-1], dem_h[-7], float(np.mean(dem_h[-7:])),
              p, mkt_h[-1], float(np.mean(mkt_h[-7:]))]
        dm = float(rf_dem.predict([fd])[0])

        mkt_h.append(p); dem_h.append(dm)
        out_dem.append((crop, d.isoformat(), round(dm)))
        out_price.append((crop, d.isoformat(), round(p, 2),
                          round(p * 0.84 * 2) / 2))  # suggested farm-gate price
    return out_dem, out_price


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    series = load_series()
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM demand_forecast")
    con.execute("DELETE FROM price_forecast")

    models_price, models_dem, metrics = {}, {}, {}
    ins_dem, ins_price = [], []
    for crop, s in series.items():
        rf_price, rf_dem, met = train_one(crop, s)
        models_price[crop], models_dem[crop] = rf_price, rf_dem
        metrics[crop] = met
        d_rows, p_rows = recursive_forecast(crop, s, rf_price, rf_dem)
        ins_dem += d_rows
        ins_price += p_rows
        print(f"[train] {crop:<22} price MAE ₹{met['price_mae']:<5} "
              f"({met['price_mape']}%)  demand MAE {met['demand_mae']} kg "
              f"({met['demand_mape']}%)")

    con.executemany("INSERT INTO demand_forecast(crop,date,pred_kg) VALUES(?,?,?)", ins_dem)
    con.executemany("INSERT INTO price_forecast(crop,date,market_pred,suggested_price) "
                    "VALUES(?,?,?,?)", ins_price)
    con.commit()

    joblib.dump({"price": models_price, "demand": models_dem},
                os.path.join(MODELS_DIR, "models.pkl"))
    overall = {
        "price_mae": round(float(np.mean([m["price_mae"] for m in metrics.values()])), 2),
        "price_mape": round(float(np.mean([m["price_mape"] for m in metrics.values()])), 1),
        "demand_mape": round(float(np.mean([m["demand_mape"] for m in metrics.values()])), 1),
        "n_crops": len(metrics), "horizon_days": HORIZON,
    }
    with open(os.path.join(MODELS_DIR, "metrics.json"), "w") as f:
        json.dump({"overall": overall, "per_crop": metrics}, f, indent=2)
    con.close()
    print(f"[train] done — {len(ins_dem)} demand forecast rows, "
          f"{len(ins_price)} price forecast rows. Overall: {overall}")


if __name__ == "__main__":
    main()
