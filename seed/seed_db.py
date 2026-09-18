"""KrishiSetu — database schema + demo data seeder (Pune region).

Creates krishisetu.db with users (farmers/FPO/consumers/bulk buyers/
logistics/admin), farms, listings, orders, deliveries, vehicles and quotes.
All demo accounts share the password: demo123
"""

import os
import random
import sqlite3
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys  # noqa: E402
sys.path.insert(0, BASE)
from ml.cropspec import CROP_SPEC  # noqa: E402

DB = os.path.join(BASE, "krishisetu.db")
random.seed(7)
PW = generate_password_hash("demo123")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN
    ('farmer','consumer','buyer','logistics','admin')),
  phone TEXT, address TEXT, lat REAL, lng REAL,
  created_at TEXT DEFAULT (date('now')));
CREATE TABLE IF NOT EXISTS farms(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id),
  name TEXT NOT NULL, fpo_name TEXT, is_fpo INTEGER DEFAULT 0,
  village TEXT, district TEXT DEFAULT 'Pune', lat REAL, lng REAL,
  organic INTEGER DEFAULT 0, area_acres REAL, rating REAL DEFAULT 4.5);
CREATE TABLE IF NOT EXISTS crops(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, emoji TEXT,
  category TEXT, unit TEXT DEFAULT 'kg', base_price REAL);
CREATE TABLE IF NOT EXISTS listings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id INTEGER REFERENCES farms(id),
  crop_id INTEGER REFERENCES crops(id), qty_available REAL, price REAL,
  market_price REAL, unit TEXT DEFAULT 'kg', grade TEXT DEFAULT 'A',
  organic INTEGER DEFAULT 0, min_order REAL DEFAULT 1,
  harvested_days_ago INTEGER DEFAULT 1, status TEXT DEFAULT 'active',
  rating REAL DEFAULT 4.6);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER REFERENCES users(id),
  buyer_type TEXT DEFAULT 'retail', status TEXT DEFAULT 'placed',
  subtotal REAL, savings REAL, delivery_fee REAL, total REAL,
  payment_mode TEXT DEFAULT 'UPI (demo)', address TEXT, lat REAL, lng REAL,
  slot TEXT, placed_on TEXT DEFAULT (date('now')),
  created_ts TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS order_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER REFERENCES orders(id),
  listing_id INTEGER REFERENCES listings(id), farmer_id INTEGER,
  crop_id INTEGER, crop_name TEXT, qty REAL, price REAL, amount REAL);
CREATE TABLE IF NOT EXISTS vehicles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, vtype TEXT,
  capacity_kg REAL, hub TEXT, hub_lat REAL, hub_lng REAL, status TEXT DEFAULT 'idle');
CREATE TABLE IF NOT EXISTS deliveries(
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER REFERENCES orders(id),
  vehicle_id INTEGER REFERENCES vehicles(id), stop_name TEXT, address TEXT,
  lat REAL, lng REAL, slot TEXT, ddate TEXT, seq INTEGER DEFAULT 0,
  status TEXT DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS quotes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_name TEXT, org TEXT, crop_name TEXT,
  qty_kg REAL, contact TEXT, note TEXT, status TEXT DEFAULT 'open',
  created_at TEXT DEFAULT (date('now')));
CREATE TABLE IF NOT EXISTS price_history(
  crop TEXT, date TEXT, market_price REAL, farmgate_price REAL, demand_kg REAL);
CREATE TABLE IF NOT EXISTS demand_forecast(crop TEXT, date TEXT, pred_kg REAL);
CREATE TABLE IF NOT EXISTS price_forecast(crop TEXT, date TEXT, market_pred REAL,
  suggested_price REAL);
"""

# ---------------------------------------------------------------- seed data
USERS = [
    # farmers
    dict(name="Ramesh Patil", email="ramesh@ks.in", role="farmer", phone="98220 11223",
         address="Patil Shetkari Farms, Baramati", lat=18.1514, lng=74.5771),
    dict(name="Sunita Shinde", email="sunita@ks.in", role="farmer", phone="98220 44556",
         address="Shinde Organic Farm, Junnar", lat=19.2100, lng=73.8700),
    dict(name="Vijay Jadhav", email="vijay@ks.in", role="farmer", phone="98220 77889",
         address="Jadhav Farms, Narayangaon", lat=19.2830, lng=73.8830),
    dict(name="Sahyadri FPO (Mangal Pawar)", email="fpo@ks.in", role="farmer",
         phone="98220 99001", address="Sahyadri FPO Collection Centre, Mulshi",
         lat=18.5100, lng=73.6400),
    dict(name="Mangal Pawar", email="mangal@ks.in", role="farmer", phone="98220 33445",
         address="Pawar Mala, Saswad", lat=18.3450, lng=73.8500),
    # consumers
    dict(name="Ananya Kulkarni", email="consumer@ks.in", role="consumer", phone="90280 11223",
         address="Flat 12, Shreeji Residency, Kothrud, Pune", lat=18.5074, lng=73.8077),
    dict(name="Priya Deshmukh", email="priya@ks.in", role="consumer", phone="90280 33445",
         address="Nagar Road, Viman Nagar, Pune", lat=18.5679, lng=73.9143),
    dict(name="Rohan Kadam", email="rohan@ks.in", role="consumer", phone="90280 55667",
         address="Kharadi Bypass Rd, Kharadi, Pune", lat=18.5510, lng=73.9420),
    dict(name="Amit Joshi", email="amit@ks.in", role="consumer", phone="90280 77889",
         address="Baner Road, Baner, Pune", lat=18.5590, lng=73.7868),
    dict(name="Neha Verma", email="neha@ks.in", role="consumer", phone="90280 99001",
         address="Phase 2, Hinjewadi, Pune", lat=18.5913, lng=73.7389),
    dict(name="Kiran Bhosale", email="kiran@ks.in", role="consumer", phone="90280 22334",
         address="Wagholi, Pune", lat=18.5814, lng=73.9523),
    dict(name="Meera Rane", email="meera@ks.in", role="consumer", phone="90280 44556",
         address="Karve Nagar, Pune", lat=18.4890, lng=73.8220),
    # bulk buyers
    dict(name="Chef Vikram Khanna", email="buyer@ks.in", role="buyer", phone="91110 11223",
         address="Hotel Green Leaf, Koregaon Park, Pune", lat=18.5362, lng=73.8939),
    dict(name="Daily Basket Retail Pvt Ltd", email="dailybasket@ks.in", role="buyer",
         phone="91110 33445", address="Daily Basket Store, Aundh, Pune",
         lat=18.5636, lng=73.8077),
    dict(name="Annapurna Mess & Caterers", email="annapurna@ks.in", role="buyer",
         phone="91110 55667", address="Annapurna Mess, Swargate, Pune",
         lat=18.5010, lng=73.8600),
    # staff
    dict(name="Sunil Gaikwad (Zunn Logistics)", email="logistics@ks.in", role="logistics",
         phone="90000 11223", address="Zunn Hub, Hadapsar, Pune", lat=18.5018, lng=73.9260),
    dict(name="Platform Admin", email="admin@ks.in", role="admin", phone="90000 00000",
         address="KrishiSetu HQ, Pune", lat=18.5204, lng=73.8567),
]

FARMS = [
    # (user_email, name, fpo_name, is_fpo, village, lat, lng, organic, acres, rating)
    ("ramesh@ks.in", "Patil Shetkari Farms", None, 0, "Baramati", 18.1514, 74.5771, 0, 12.5, 4.7),
    ("sunita@ks.in", "Shinde Organic Farm", None, 0, "Junnar", 19.2100, 73.8700, 1, 6.0, 4.9),
    ("vijay@ks.in", "Jadhav Farms", None, 0, "Narayangaon", 19.2830, 73.8830, 0, 9.0, 4.6),
    ("fpo@ks.in", "Sahyadri Farmer Producer Co.", "Sahyadri FPO", 1, "Mulshi", 18.5100, 73.6400, 0, 140.0, 4.8),
    ("mangal@ks.in", "Pawar Mala", None, 0, "Saswad", 18.3450, 73.8500, 0, 4.5, 4.5),
    (None, "MoreMala Agro", None, 0, "Indapur", 18.1130, 74.9300, 0, 15.0, 4.4),
    (None, "Bhor Valley Collective", "Bhor FPO", 1, "Bhor", 18.0450, 73.8450, 1, 55.0, 4.8),
    (None, "Kamshet Greens", None, 0, "Kamshet", 18.7600, 73.5450, 0, 7.5, 4.5),
]

# farm name -> [(crop_name, qty, grade, min_order, harvested_days_ago)]
FARM_CROPS = {
    "Patil Shetkari Farms": [("Tomato", 850, "A", 1, 1), ("Onion", 2400, "A", 5, 3),
                             ("Green Chilli", 320, "A", 1, 1)],
    "Shinde Organic Farm": [("Spinach", 180, "A", 1, 0), ("Carrot", 260, "A", 1, 1),
                            ("Tomato", 340, "A", 1, 1)],
    "Jadhav Farms": [("Grapes (Thompson)", 900, "A", 2, 2), ("Tomato", 520, "B", 1, 1),
                     ("Onion", 1100, "B", 5, 4)],
    "Sahyadri Farmer Producer Co.": [("Rice (Sona Masoori)", 3200, "A", 25, 6),
                                     ("Wheat", 2800, "A", 25, 12), ("Onion", 1800, "A", 25, 5)],
    "Pawar Mala": [("Mosambi (Sweet Lime)", 640, "A", 2, 2), ("Alphonso Mango", 210, "A", 2, 1)],
    "MoreMala Agro": [("Potato", 1900, "A", 5, 4), ("Onion", 1500, "B", 5, 6)],
    "Bhor Valley Collective": [("Spinach", 220, "A", 1, 0), ("Carrot", 300, "A", 1, 1)],
    "Kamshet Greens": [("Banana (Elaichi)", 780, "A", 2, 1), ("Rice (Sona Masoori)", 950, "B", 10, 9)],
}

VEHICLES = [
    ("MH-12-AB-1234", "Tata Ace (Tempo)", 800, "Zunn Hub, Hadapsar", 18.5018, 73.9260, "on_route"),
    ("MH-12-CD-5678", "Mahindra Jeeto", 500, "Zunn Hub, Hadapsar", 18.5018, 73.9260, "idle"),
    ("MH-12-EF-9012", "E-loader (Piaggio)", 300, "Zunn Hub, Hadapsar", 18.5018, 73.9260, "idle"),
]


def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    # ---- crops
    crop_ids = {}
    for name, emoji, cat, unit, base_p, *_ in CROP_SPEC:
        cur = con.execute(
            "INSERT INTO crops(name,emoji,category,unit,base_price) VALUES(?,?,?,?,?)",
            (name, emoji, cat, unit, base_p))
        crop_ids[name] = cur.lastrowid

    # ---- users
    user_ids = {}
    for u in USERS:
        cur = con.execute(
            "INSERT INTO users(name,email,password_hash,role,phone,address,lat,lng) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (u["name"], u["email"], PW, u["role"], u["phone"], u["address"],
             u.get("lat"), u.get("lng")))
        user_ids[u["email"]] = cur.lastrowid

    # ---- farms + listings
    farm_ids, listing_pool = {}, []
    for email, name, fpo, isfpo, village, lat, lng, organic, acres, rating in FARMS:
        uid = user_ids.get(email)
        cur = con.execute(
            "INSERT INTO farms(user_id,name,fpo_name,is_fpo,village,district,lat,lng,"
            "organic,area_acres,rating) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (uid, name, fpo, isfpo, village, "Pune", lat, lng, organic, acres, rating))
        farm_ids[name] = cur.lastrowid
        base_by_name = {c[0]: c[4] for c in CROP_SPEC}
        for crop_name, qty, grade, min_order, hdays in FARM_CROPS[name]:
            base = base_by_name[crop_name]
            organic_c = 1 if organic else 0
            price = round(base * random.uniform(0.76, 0.83) * (1.12 if organic_c else 1.0), 1)
            cur = con.execute(
                "INSERT INTO listings(farm_id,crop_id,qty_available,price,market_price,"
                "unit,grade,organic,min_order,harvested_days_ago,status,rating) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (farm_ids[name], crop_ids[crop_name], qty, price, base, "kg", grade,
                 organic_c, min_order, hdays, "active", round(random.uniform(4.3, 4.9), 1)))
            listing_pool.append(dict(
                id=cur.lastrowid, farm=name, crop=crop_name, price=price, market=base,
                farmer_uid=uid, crop_id=crop_ids[crop_name], min_order=min_order))

    consumers = [u for u in USERS if u["role"] == "consumer"]
    buyers = [u for u in USERS if u["role"] == "buyer"]
    buyer_type = {"consumer": "retail", "buyer": "bulk"}

    # ---- historical orders (last 30 days)
    today = date.today()
    n_orders = 0
    for days_back in range(30, 0, -1):
        d = today - timedelta(days=days_back)
        for _ in range(random.randint(3, 6)):
            buyer = random.choice(consumers + buyers)
            items = random.sample(listing_pool, random.randint(1, 3))
            subtotal = savings = 0.0
            rows = []
            for it in items:
                qty = random.randint(20, 160) if buyer["role"] == "buyer" else random.randint(1, 6)
                amt = round(qty * it["price"], 2)
                subtotal += amt
                savings += round((it["market"] - it["price"]) * qty, 2)
                rows.append((it, qty, amt))
            fee = 0 if subtotal >= 499 else 29
            ts = f"{d} {random.randint(8, 20):02d}:{random.randint(0, 59):02d}:00"
            cur = con.execute(
                "INSERT INTO orders(buyer_id,buyer_type,status,subtotal,savings,delivery_fee,"
                "total,payment_mode,address,lat,lng,slot,placed_on,created_ts) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user_ids[buyer["email"]], buyer_type[buyer["role"]], "delivered",
                 round(subtotal, 2), round(savings, 2), fee, round(subtotal + fee, 2),
                 random.choice(["UPI (demo)", "UPI (demo)", "Cash on delivery"]),
                 buyer["address"], buyer.get("lat"), buyer.get("lng"),
                 random.choice(["9–11 AM", "11 AM–1 PM", "4–7 PM"]),
                 d.isoformat(), ts))
            oid = cur.lastrowid
            for it, qty, amt in rows:
                con.execute(
                    "INSERT INTO order_items(order_id,listing_id,farmer_id,crop_id,crop_name,"
                    "qty,price,amount) VALUES(?,?,?,?,?,?,?,?)",
                    (oid, it["id"], it["farmer_uid"], it["crop_id"], it["crop"],
                     qty, it["price"], amt))
            n_orders += 1

    # ---- today's live orders (demo flow: placed -> confirmed -> packed -> in_transit)
    live = [
        ("placed", "priya@ks.in"), ("placed", "amit@ks.in"), ("confirmed", "rohan@ks.in"),
        ("confirmed", "consumer@ks.in"), ("packed", "neha@ks.in"), ("packed", "kiran@ks.in"),
        ("in_transit", "meera@ks.in"), ("in_transit", "buyer@ks.in"),
        ("in_transit", "priya@ks.in"),
    ]
    v1_stops = []  # vehicle 1 route for the live in_transit orders
    for i, (status, email) in enumerate(live):
        buyer = next(u for u in USERS if u["email"] == email)
        items = random.sample(listing_pool, random.randint(1, 3))
        subtotal = savings = 0.0
        rows = []
        for it in items:
            qty = random.randint(30, 120) if buyer["role"] == "buyer" else random.randint(1, 6)
            amt = round(qty * it["price"], 2)
            subtotal += amt
            savings += round((it["market"] - it["price"]) * qty, 2)
            rows.append((it, qty, amt))
        fee = 0 if subtotal >= 499 else 29
        ts = f"{today} {random.randint(7, 10):02d}:{random.randint(0, 59):02d}:00"
        cur = con.execute(
            "INSERT INTO orders(buyer_id,buyer_type,status,subtotal,savings,delivery_fee,"
            "total,payment_mode,address,lat,lng,slot,placed_on,created_ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_ids[email], buyer_type[buyer["role"]], status, round(subtotal, 2),
             round(savings, 2), fee, round(subtotal + fee, 2),
             random.choice(["UPI (demo)", "Cash on delivery"]),
             buyer["address"], buyer.get("lat"), buyer.get("lng"),
             random.choice(["9–11 AM", "11 AM–1 PM", "4–7 PM"]), today.isoformat(), ts))
        oid = cur.lastrowid
        for it, qty, amt in rows:
            con.execute(
                "INSERT INTO order_items(order_id,listing_id,farmer_id,crop_id,crop_name,"
                "qty,price,amount) VALUES(?,?,?,?,?,?,?,?)",
                (oid, it["id"], it["farmer_uid"], it["crop_id"], it["crop"],
                 qty, it["price"], amt))
        if status == "in_transit":
            v1_stops.append((oid, buyer))

    # ---- vehicles + today's deliveries
    veh_ids = {}
    for code, vtype, cap, hub, hlat, hlng, st in VEHICLES:
        cur = con.execute(
            "INSERT INTO vehicles(code,vtype,capacity_kg,hub,hub_lat,hub_lng,status) "
            "VALUES(?,?,?,?,?,?,?)", (code, vtype, cap, hub, hlat, hlng, st))
        veh_ids[code] = cur.lastrowid

    # vehicle 1: live route — intentionally SCRAMBLED seq so route optimization
    # shows a visible win in the demo
    for seq, (oid, buyer) in enumerate(reversed(v1_stops)):
        area = buyer["address"].split(",")[-2].strip() if "," in buyer["address"] else buyer["address"]
        con.execute(
            "INSERT INTO deliveries(order_id,vehicle_id,stop_name,address,lat,lng,slot,"
            "ddate,seq,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (oid, veh_ids["MH-12-AB-1234"], area, buyer["address"], buyer.get("lat"),
             buyer.get("lng"), random.choice(["9–11 AM", "11 AM–1 PM", "4–7 PM"]),
             today.isoformat(), seq, "in_transit"))

    # vehicle 2: finished morning round (delivered)
    done = [("Kothrud", "Flat 12, Shreeji Residency, Kothrud, Pune", 18.5074, 73.8077),
            ("Swargate", "Annapurna Mess, Swargate, Pune", 18.5010, 73.8600),
            ("Karve Nagar", "Karve Nagar, Pune", 18.4890, 73.8220)]
    for seq, (area, addr, lat, lng) in enumerate(done):
        con.execute(
            "INSERT INTO deliveries(order_id,vehicle_id,stop_name,address,lat,lng,slot,"
            "ddate,seq,status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (None, veh_ids["MH-12-CD-5678"], area, addr, lat, lng, "9–11 AM",
             today.isoformat(), seq, "delivered"))

    # ---- bulk quotes
    con.execute("INSERT INTO quotes(buyer_name,org,crop_name,qty_kg,contact,note,status) "
                "VALUES(?,?,?,?,?,?,?)",
                ("Chef Vikram Khanna", "Hotel Green Leaf", "Tomato", 500, "buyer@ks.in",
                 "Weekly contract, Grade A only", "open"))
    con.execute("INSERT INTO quotes(buyer_name,org,crop_name,qty_kg,contact,note,status) "
                "VALUES(?,?,?,?,?,?,?)",
                ("Annapurna Mess & Caterers", "Annapurna", "Onion", 300, "annapurna@ks.in",
                 "Monthly supply", "open"))

    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("users", "farms", "crops", "listings", "orders",
                        "order_items", "deliveries", "vehicles", "quotes")}
    con.close()
    print(f"[seed] krishisetu.db ready: {counts}")
    print("[seed] demo logins (password: demo123): ramesh@ks.in (farmer), "
          "fpo@ks.in (FPO), consumer@ks.in, buyer@ks.in, logistics@ks.in, admin@ks.in")


if __name__ == "__main__":
    main()
