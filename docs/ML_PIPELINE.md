# KrishiSetu — AI/ML Pipeline

Two problems from the problem statement are solved with real, trained models:

1. **Demand forecasting** — "Uses AI for demand forecasting"
2. **Route optimization** — "…and route optimization"

---

## 1. Data generation (`ml/generate_data.py`)

The prototype trains on a synthetic-but-realistic corpus because live mandi feeds are
out of scope for a hackathon demo. For each of **12 crops** (tomato, onion, potato, carrot,
spinach, green chilli, wheat, rice, mango, banana, grapes, mosambi) it generates **730 days** of:

| Field | How it's modelled |
|---|---|
| `market_price` (mandi-retail ₹/kg) | base × seasonal factor (peak/low months) × slow drift × lognormal noise |
| `farmgate_price` (what farmer gets on platform) | market × U(0.72, 0.83) — the intermediary margin removed |
| `demand_kg` (city demand/day) | base × season × weekday factor (Fri/weekend ↑, Tue ↓) × **festival boost (+38%)** × lognormal noise |

Total: **8,760 rows** in `price_history`. Seeded RNG → fully reproducible.

## 2. Models (`ml/train_models.py`)

Per crop, two `RandomForestRegressor`s (180 trees, depth 12, min-leaf 3):

**Price model** — predicts today's mandi price from *only past information*:
month, weekday, festival flag, demand lags (t−1, t−7, 7-day mean), price lags (t−1, t−7, 7-day mean).

**Demand model** — predicts today's demand using the same lags **plus today's price**
(known historically; *predicted* when forecasting).

### Validation
Last **60 days** held out (one-step-ahead):

| Model | Mean MAPE across 12 crops | Meaning |
|---|---|---|
| Price | **≈ 5.6%** | e.g. predicts a ₹32 tomato to within ±₹1.8 |
| Demand | **≈ 13.8%** | daily retail demand is noisy; weekly aggregates are far tighter |

Per-crop metrics are printed at training time and persisted to `ml/models/metrics.json`
(surfaced on the farmer insights page and admin board).

### Forecasting (recursive, 14 days)
Starting tomorrow: predict price for day *t* → feed it into the demand model for day *t* →
append predictions to the history → repeat. This yields coherent joint price-demand
trajectories instead of independent daily guesses. Outputs land in
`demand_forecast` (crop, date, kg) and `price_forecast` (crop, date, mandi pred, **suggested farm-gate price**).

**Suggested price rule:** `suggested = 0.84 × forecast_mandi` — the farmer prices *above*
what agents would pay, yet buyers still pay ~16% below mandi-retail. Both sides win; this
is the number shown across the AI Insights page.

### How the app consumes the models
- **Farmer AI Insights** — 30-day actuals + 14-day forecast on one chart (bridge series),
  demand outlook badge (±8% thresholds → high/stable/low vs trailing week), per-crop advice
  ("you can raise price ~9%").
- **Landing page** — today's demand outlook chips for staples.
- **Admin** — forecast board with suggested prices & outlook per staple.
- **JSON API** — `GET /api/forecast/<crop>`.

## 3. Route optimization (`ml/optimizer.py`)

Each vehicle's live stops (excluding delivered) form a tour **hub → stops → hub**.

| Step | Method |
|---|---|
| Distance | Haversine great-circle km between stops |
| Construction | **Nearest neighbour** from the hub |
| Improvement | **2-opt** local search (segment reversal until no improving move) |
| Reporting | km & minutes before/after (26 km/h avg urban speed + 6 min service/stop) |

Applied live from the logistics console: *Scramble (demo reset)* → *Optimize with AI*.
Typical demo result on the seeded Pune route: **~15–25% distance saved**.
The ordered sequence is written back to `deliveries.seq` and re-renders the numbered SVG map.

> Production upgrade path: replace haversine with OSRM/Google road distances and swap
> 2-opt for OR-Tools VRP with time windows, capacity and load-bearing constraints.

## 4. Reproducibility

```bash
python seed/seed_db.py       # schema + demo data
python ml/generate_data.py   # 8,760-row training corpus
python ml/train_models.py    # train → validate → forecast → persist
```
All steps are deterministic (fixed seeds) — judges can regenerate identical results.
