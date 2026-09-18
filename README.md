# 🌱 KrishiSetu — Farm to Fork, Direct

**A full-stack digital marketplace connecting farmers & FPOs directly with consumers and bulk buyers — with end-to-end logistics, AI demand forecasting and route optimization.**

> Built as a working prototype for **Smart India Hackathon**
> *Problem Statement: "Multiple intermediaries reduce farmers' earnings and increase consumer prices"*
> Ministry of Consumer Affairs, Food & Public Distribution · Dept. of Consumer Affairs (DoCA)
> Theme: Agriculture, FoodTech & Rural Development · Category: Software

---

## 🎯 The problem → the solution

| Traditional chain | KrishiSetu |
|---|---|
| Farmer → agent → mandi wholesaler → secondary wholesaler → retailer → consumer | Farmer/FPO → collection hub → consumer/bulk buyer |
| 4–6 intermediary margins (8–25% each) | Single small platform + logistics fee |
| Farmers get 25–35% of consumer rupee | Farmers realise **~20% more per kg** (live KPI) |
| Consumers pay mandi-linked retail | Consumers save **~19% on average** (live KPI) |
| Over/under-supply by guesswork | **14-day AI demand forecast** per crop |
| Inefficient delivery rounds | **NN + 2-opt route optimization** engine |

## 🚀 Quick start

```bash
cd krishisetu
pip install -r requirements.txt

# 1) create the database + demo data (Pune region)
python seed/seed_db.py
# 2) generate 2 years of synthetic market history
python ml/generate_data.py
# 3) train the ML models & build 14-day forecasts
python ml/train_models.py
# 4) run
python app.py          # -> http://localhost:8000
```

**Demo accounts** (password: `demo123`) — one-click buttons on the login page:

| Account | Email | What to try |
|---|---|---|
| Farmer | `ramesh@ks.in` | Confirm orders, add listing, **AI Insights** page |
| FPO | `fpo@ks.in` | Aggregated listings, bulk quotes dashboard |
| Consumer | `consumer@ks.in` | Shop → cart → checkout → **live tracking** |
| Bulk buyer | `buyer@ks.in` | Wholesale listings, bulk quote requests, spend analytics |
| Logistics | `logistics@ks.in` | **Route optimization** (scramble → optimize demo!), mark stops delivered |
| Admin | `admin@ks.in` | Platform KPIs, GMV charts, model accuracy |

## ✨ Feature map (against the problem statement)

**1. Connects farmers/FPOs directly with consumers & bulk buyers**
- Farmer/FPO listings with grade, harvest date, organic/FPO badges, farm traceability
- Retail storefront (search, filters, cart, checkout with demo UPI/COD)
- Wholesale mode: min-order quantities + **bulk/contract quote requests** (buyer ↔ FPO)
- Role dashboards for farmers, FPOs, consumers, bulk buyers, logistics, admin
- Order lifecycle: placed → farmer confirms → packed → hub pickup → out for delivery → delivered

**2. Provides logistics support**
- Collection-hub model (Zunn Hub, Hadapsar), vehicle fleet, delivery slots
- **Route sequencing engine** (Nearest Neighbour + 2-opt, haversine distances)
- Live route map (SVG), animated vehicle on the order tracking page
- Delivery mark-off flow: hub → stops → delivered (auto-updates order status)

**3. Uses AI for demand forecasting & route optimization**
- Real **RandomForest models** (scikit-learn) trained per crop on 2 years of data
  - Price model: **~5.6% MAPE** · Demand model: **~13.8% MAPE** (hold-out)
- **Recursive 14-day forecasts** for price & demand for all 12 crops
- Farmer **AI Insights**: demand outlook (high/stable/low), AI-suggested farm-gate price,
  actionable advice ("demand up — you can raise price ~9%")
- Route optimization: km & minutes saved, shown before/after applying

## 🧱 Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Python Flask 3** | 30+ routes, session auth, role-based access |
| Database | **SQLite** (stdlib `sqlite3`) | 11 tables, zero external services |
| ML | **scikit-learn RandomForest** + numpy | models persisted with joblib |
| Optimization | Pure-Python NN + 2-opt TSP heuristics | `ml/optimizer.py` |
| Frontend | Server-rendered **Jinja2** + custom CSS/JS | zero CDNs — works fully offline/air-gapped |
| Charts/Maps | Hand-rolled inline **SVG generators** | no external JS libs |

## 📁 Project structure

```
krishisetu/
├── app.py                  # Flask app — all routes & helpers
├── charts.py               # SVG line/bar chart builders
├── requirements.txt
├── seed/seed_db.py         # schema + Pune-region demo data
├── ml/
│   ├── cropspec.py         # shared crop/calendar spec
│   ├── generate_data.py    # 2-yr synthetic mandi + demand history
│   ├── train_models.py     # RF training, validation, 14-day recursive forecast
│   ├── optimizer.py        # haversine + nearest neighbour + 2-opt
│   └── models/             # models.pkl, metrics.json (generated)
├── templates/              # 17 Jinja templates (all roles)
├── static/                 # CSS theme, JS, hero image
└── krishisetu.db           # generated database
```

## 🔌 API (samples)

```
GET /api/forecast/Tomato     # 14-day demand + price forecast, outlook
```

## 🧠 ML pipeline in one minute

1. `generate_data.py` — 12 crops × 730 days of prices & demand with seasonality,
   weekly cycles, festival spikes, drift and noise.
2. `train_models.py` — feature engineering (calendar, festival, lag-1/7/14, rolling means),
   60-day hold-out validation, RandomForest price & demand models per crop,
   then **recursive 14-day forecasting** (predicted price feeds the demand model).
3. Forecasts land in `demand_forecast` / `price_forecast` tables → farmer insights,
   admin board, landing chips and the JSON API all read from them.
4. `optimizer.py` — tour length (haversine), NN construction, 2-opt improvement;
   applied to each vehicle's live stop list.

## 🔭 Production roadmap

- Real payments (UPI + PG) with **escrow payouts to farmers** on delivery confirmation
- GPS-integrated tracking, driver app, push/SMS alerts in Marathi/Hindi
- Quality grading at hubs (photo AI), cold-chain for perishables
- FPO aggregation tools: crop planning from forecasts, warehouse receipts
- Weather + soil data integration for advisories; government price-buffer integration
