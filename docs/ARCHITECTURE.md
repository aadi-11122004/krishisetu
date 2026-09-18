# KrishiSetu — Architecture

## 1. System overview

```
                        ┌──────────────────────────────────────────────┐
                        │                Flask app (app.py)            │
  Browser  ── HTTP ──▶  │  ┌─────────┐  ┌──────────┐  ┌─────────────┐  │
                        │  │ Views / │  │ Session  │  │ Role-based  │  │
  (consumer, farmer,    │  │ routes  │  │ auth     │  │ access      │  │
   buyer, logistics,    │  └────┬────┘  └──────────┘  └─────────────┘  │
   admin)               │       │ SQL (sqlite3)                        │
                        │  ┌────▼──────────────────────────────────┐   │
                        │  │          SQLite  krishisetu.db        │   │
                        │  │  users farms crops listings orders    │   │
                        │  │  order_items deliveries vehicles      │   │
                        │  │  quotes price_history                 │   │
                        │  │  demand_forecast price_forecast       │   │
                        │  └────▲───────────────────▲────────────────┘   │
                        │       │                   │                    │
                        │  ┌────┴────────┐   ┌──────┴──────────┐         │
                        │  │ ML pipeline │   │ Route optimizer │         │
                        │  │ ml/*.py     │   │ ml/optimizer.py │         │
                        │  └─────────────┘   └─────────────────┘         │
                        └──────────────────────────────────────────────┘
```

**Design goal for the prototype:** a *single-process, zero-dependency-service* stack
(Flask + SQLite + filesystem) that runs anywhere — including air-gapped demo laptops —
while keeping every architectural seam (auth, roles, ML store, optimizer API) where a
production build would need it.

## 2. Roles & access

| Role | Capabilities |
|---|---|
| `farmer` / FPO | Listings CRUD (pause/activate), order confirmation → packing, AI insights, quotes inbox |
| `consumer` | Retail marketplace, cart, checkout, order history, live tracking |
| `buyer` | Everything a consumer has + wholesale min-order listings + bulk quote requests + spend analytics |
| `logistics` | Delivery console: vehicle rounds, route optimization, mark-off, unassigned pool |
| `admin` | Platform KPIs, GMV/volume charts, AI forecast board, model accuracy |

Passwords are hashed with Werkzeug (`scrypt`); sessions are signed Flask cookies.
`login_required(*roles)` guards private routes; the marketplace and tracking are public.

## 3. Data model (11 tables)

- **users** — one row per person; `role` drives the UI; consumers/buyers carry a delivery lat/lng
- **farms** — farmer/FPO profile; `is_fpo` marks producer organisations (FPO aggregation)
- **crops** — catalogue with mandi base price & emoji/category for UI
- **listings** — produce for sale: qty, farm-gate price, *mandi reference price*, grade, organic, min_order (wholesale trigger), status
- **orders / order_items** — order header (buyer, status, money, savings, slot, address, payment) + line items snapshot (price frozen at purchase, farmer_id for payout routing)
- **deliveries** — one row per stop: order, vehicle, geo, slot, `seq` (route position), status
- **vehicles** — fleet at the hub with capacity & live status
- **quotes** — bulk/contract requests from buyers, surfaced to farmers/FPOs
- **price_history** — the ML training corpus (2 years × 12 crops: mandi price, farm-gate price, city demand)
- **demand_forecast / price_forecast** — model outputs consumed by the app (written only by `train_models.py`)

## 4. Order lifecycle (state machine)

```
placed ──▶ confirmed ──▶ packed ──▶ in_transit ──▶ delivered
 (buyer)    (farmer)      (farmer)    (logistics)    (logistics mark-off)
```

- Consumer checkout creates the order **and** an unassigned `deliveries` row for the next day's slot.
- The logistics console assigns stops to vehicles; `seq` is the route order.
- Marking a stop delivered advances its order; an empty vehicle flips to `idle`.

## 5. Money flow (demo logic)

- Listing `price` = farm-gate + platform margin; `market_price` = mandi-retail reference.
- Order stores `savings = Σ (market − price) × qty` → consumer savings KPI.
- Farmer dashboard aggregates `order_items.amount` (their realisation) — no commission agent in between.
- Delivery fee ₹29, free above ₹499 (retail); wholesale is hub-to-business.

## 6. Frontend architecture

- Server-rendered Jinja templates; **no CDNs, no external JS/CSS** — fully offline-capable.
- `charts.py` renders multi-series SVG line charts (with forecast bridging via None-gaps)
  and horizontal bar charts — all generated server-side.
- `route_map()` projects stop lat/lng onto an inline SVG map with a dashed tour polyline.
- `static/js/main.js` is progressive enhancement only: toast auto-dismiss, filter auto-apply,
  and an animated vehicle dot using SVG `getPointAtLength()` on the tracking page.

## 7. Key seams for productionisation

| Prototype | Production swap |
|---|---|
| SQLite | PostgreSQL (+ PostGIS for geo queries) |
| Session auth | OTP/phone auth, JWT, RBAC service |
| Demo UPI | PG + escrow payout on delivery confirmation |
| Synthetic history | Agmarknet/eNAM price feeds + order telemetry |
| Single hub | Multi-hub assignment problem (VRP), 3rd-party fleet APIs |
| Inline SVG maps | Mapbox/MapML with real road network (OSRM for routing) |
