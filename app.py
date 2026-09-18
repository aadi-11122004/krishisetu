"""KrishiSetu — farm-to-consumer digital marketplace (SIH prototype).

Flask app: marketplace, logistics with route optimization, and an AI layer
(demand forecasting + price suggestion) powered by real trained models.
Run:  python app.py   ->  http://localhost:8000
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from charts import bar_chart, line_chart
from ml.optimizer import optimize_route, route_length_km

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "krishisetu.db")
HUB = dict(name="Zunn Hub, Hadapsar", lat=18.5018, lng=73.9260)
PUNE_CENTER = (18.5204, 73.8567)
DELIVERY_FEE, FREE_ABOVE = 29, 499
STEPS = [("placed", "Order placed"), ("confirmed", "Farmer confirmed"),
         ("packed", "Packed at collection centre"), ("in_transit", "Out for delivery"),
         ("delivered", "Delivered")]

app = Flask(__name__)
app.secret_key = "krishisetu-sih-demo-secret"


# ----------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def set_today():
    g.today = date.today()


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


LSEL = """SELECT l.*, c.name AS crop_name, c.emoji, c.category,
        f.name AS farm_name, f.village, f.district, f.is_fpo, f.organic AS farm_organic,
        f.rating AS farm_rating, u.name AS farmer_name,
        ROUND((l.market_price - l.price) / l.market_price * 100, 1) AS save_pct
        FROM listings l
        JOIN crops c ON c.id = l.crop_id
        JOIN farms f ON f.id = l.farm_id
        LEFT JOIN users u ON u.id = f.user_id"""


# ------------------------------------------------------------------ helpers
def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    if "cu" not in g:
        g.cu = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    return g.cu


def login_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                flash("Please log in to continue.", "warn")
                return redirect(url_for("login", next=request.path))
            if roles and u["role"] not in roles:
                flash("That page isn't available for your account.", "warn")
                return redirect(url_for("index"))
            return fn(*a, **kw)
        return wrapper
    return deco


def inr(v):
    """Indian-style rupee formatting: ₹1,23,456.00"""
    try:
        v = round(float(v), 2)
    except (TypeError, ValueError):
        return "₹0"
    s = f"{v:,.2f}"
    whole, _, frac = s.partition(".")
    whole = whole.replace(",", "")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"₹{whole}.{frac}"


app.template_filter("inr")(inr)


@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return dict(user=current_user(),
                cart_count=sum(cart.values()),
                today=date.today(),
                STEPS=STEPS)


def cart_rows():
    cart = session.get("cart", {})
    if not cart:
        return [], 0.0, 0.0
    ids = list(cart.keys())
    ph = ",".join("?" * len(ids))
    rows = [dict(r) for r in q(LSEL + f" WHERE l.id IN ({ph})", ids)]
    subtotal = savings = 0.0
    for r in rows:
        r["qty"] = float(cart[str(r["id"])])
        r["amount"] = round(r["price"] * r["qty"], 2)
        r["saved"] = round((r["market_price"] - r["price"]) * r["qty"], 2)
        subtotal += r["amount"]
        savings += r["saved"]
    return rows, round(subtotal, 2), round(savings, 2)


def forecast_chips():
    """AI demand outlook chips for the landing page."""
    min_d = q("SELECT MIN(date) AS d FROM demand_forecast", one=True)["d"]
    chips = []
    for name in ("Tomato", "Onion", "Potato", "Rice (Sona Masoori)"):
        pred = q("SELECT pred_kg FROM demand_forecast WHERE crop=? AND date=?",
                 (name, min_d), one=True)
        act = q("SELECT demand_kg FROM price_history WHERE crop=? "
                "ORDER BY date DESC LIMIT 1", (name,), one=True)
        emoji = q("SELECT emoji FROM crops WHERE name=?", (name,), one=True)
        if pred and act and act["demand_kg"]:
            pct = round((pred["pred_kg"] - act["demand_kg"]) / act["demand_kg"] * 100)
            chips.append(dict(name=name, emoji=emoji["emoji"] if emoji else "🌱", pct=pct))
    return chips


def crop_insight(crop_name):
    """Full AI insight bundle for one crop (history + forecasts + outlook)."""
    hist = [dict(r) for r in q(
        "SELECT date, demand_kg, market_price FROM price_history WHERE crop=? "
        "ORDER BY date DESC LIMIT 30", (crop_name,))][::-1]
    fc_d = [dict(r) for r in q(
        "SELECT date, pred_kg FROM demand_forecast WHERE crop=? ORDER BY date", (crop_name,))]
    fc_p = [dict(r) for r in q(
        "SELECT date, market_pred, suggested_price FROM price_forecast WHERE crop=? "
        "ORDER BY date", (crop_name,))]

    labels = [d["date"][5:] for d in hist] + [d["date"][5:] for d in fc_d]
    actual = [d["demand_kg"] for d in hist] + [None] * len(fc_d)
    bridge = ([None] * (len(hist) - 1)) + [hist[-1]["demand_kg"]] if hist else []
    fdem = bridge + [d["pred_kg"] for d in fc_d]

    phist = [d["market_price"] for d in hist]
    pfc = ([None] * (len(phist) - 1)) + [phist[-1]] + [d["market_pred"] for d in fc_p]

    last7 = [d["demand_kg"] for d in hist[-7:]]
    next7 = [d["pred_kg"] for d in fc_d[:7]]
    base = sum(last7) / len(last7) if last7 else 0
    outlook_pct = round((sum(next7) / len(next7) - base) / base * 100) if base else 0
    outlook = ("high" if outlook_pct >= 8 else "low" if outlook_pct <= -8 else "stable")

    return dict(crop=crop_name, labels=labels, actual=actual, fdem=fdem, pfc=pfc,
                fc_d=fc_d, fc_p=fc_p, outlook=outlook, outlook_pct=outlook_pct,
                suggested=fc_p[-1]["suggested_price"] if fc_p else None,
                mandi_pred=fc_p[-1]["market_pred"] if fc_p else None)


def route_map(depot, stops, w=700, h=360):
    """Inline SVG map of a delivery route (linear lat/lng projection)."""
    if not stops:
        return ""
    pad = 56
    lats = [s["lat"] for s in stops] + [depot["lat"]]
    lngs = [s["lng"] for s in stops] + [depot["lng"]]
    la0, la1 = min(lats) - 0.012, max(lats) + 0.012
    lo0, lo1 = min(lngs) - 0.012, max(lngs) + 0.012
    cw, ch = w - 2 * pad, h - 2 * pad

    def X(lng): return pad + (lng - lo0) / (lo1 - lo0) * cw
    def Y(lat): return pad + (la1 - lat) / (la1 - la0) * ch

    parts = [f"<rect x='0' y='0' width='{w}' height='{h}' rx='14' fill='#eef3e9'/>"]
    # subtle grid
    for k in range(1, 8):
        parts.append(f"<line x1='{pad + cw*k/8:.0f}' y1='10' x2='{pad + cw*k/8:.0f}' "
                     f"y2='{h-10}' stroke='#dce6d4' stroke-width='1'/>")
        parts.append(f"<line x1='10' y1='{pad + ch*k/8:.0f}' x2='{w-10}' "
                     f"y2='{pad + ch*k/8:.0f}' stroke='#dce6d4' stroke-width='1'/>")
    hx, hy = X(depot["lng"]), Y(depot["lat"])
    loop = " ".join(f"{X(s['lng']):.1f},{Y(s['lat']):.1f}" for s in stops)
    parts.append(f"<polyline points='{hx:.1f},{hy:.1f} {loop} {hx:.1f},{hy:.1f}' "
                 f"fill='none' stroke='#8fbf7f' stroke-width='2.2' stroke-dasharray='6 5'/>")
    parts.append(f"<rect x='{hx-9:.1f}' y='{hy-9:.1f}' width='18' height='18' rx='4' "
                 f"fill='#1b5e20'/><text x='{hx:.1f}' y='{hy+4:.1f}' text-anchor='middle' "
                 f"font-size='11' fill='#fff' font-weight='700'>H</text>")
    parts.append(f"<text x='{hx:.1f}' y='{hy+24:.1f}' text-anchor='middle' class='map-lab'>Hub</text>")
    for i, s in enumerate(stops, 1):
        x, y = X(s["lng"]), Y(s["lat"])
        done = s.get("status") == "delivered"
        col = "#9e9e9e" if done else "#f9a825"
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='11' fill='{col}' "
                     f"stroke='#fff' stroke-width='2'/>"
                     f"<text x='{x:.1f}' y='{y+3.5:.1f}' text-anchor='middle' "
                     f"font-size='10' font-weight='700' fill='#3e2723'>{i}</text>")
        parts.append(f"<text x='{x:.1f}' y='{y+24:.1f}' text-anchor='middle' "
                     f"class='map-lab'>{s['stop_name']}</text>")
    km = route_length_km(depot, list(range(len(stops))),
                         [{"lat": s["lat"], "lng": s["lng"]} for s in stops])
    parts.append(f"<text x='{w-14}' y='{h-14}' text-anchor='end' class='map-km'>"
                 f"route ≈ {km:.1f} km</text>")
    from markupsafe import Markup
    return Markup("".join(parts))


def timeline_for(order):
    if order["status"] == "cancelled":
        return []
    names = [s[0] for s in STEPS]
    try:
        idx = names.index(order["status"])
    except ValueError:
        idx = 0
    return [dict(key=k, label=lab, done=(i <= idx), current=(i == idx))
            for i, (k, lab) in enumerate(STEPS)]


# ------------------------------------------------------------------- public
@app.route("/")
def index():
    stats = dict(
        farmers=q("SELECT COUNT(*) AS n FROM users WHERE role IN ('farmer')", one=True)["n"],
        fpos=q("SELECT COUNT(*) AS n FROM farms WHERE is_fpo=1", one=True)["n"],
        listings=q("SELECT COUNT(*) AS n FROM listings WHERE status='active'", one=True)["n"],
        delivered=q("SELECT COUNT(*) AS n FROM orders WHERE status='delivered'", one=True)["n"],
        save_pct=q("SELECT ROUND(AVG(savings*100.0/subtotal),1) AS n FROM orders "
                   "WHERE subtotal>0", one=True)["n"],
    )
    featured = q(LSEL + " WHERE l.status='active' ORDER BY f.rating DESC, l.rating DESC LIMIT 6")
    return render_template("index.html", stats=stats, featured=featured, chips=forecast_chips())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = q("SELECT * FROM users WHERE email=?", (email,), one=True)
        if u and check_password_hash(u["password_hash"], pw):
            session["uid"] = u["id"]
            flash(f"Welcome back, {u['name']}!", "ok")
            nxt = request.args.get("next") or request.form.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for({"farmer": "farmer_dash", "buyer": "buyer_dash",
                                     "logistics": "logistics", "admin": "admin"}
                                    .get(u["role"], "marketplace")))
        flash("Invalid email or password.", "err")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        role = request.form.get("role", "consumer")
        if role not in ("farmer", "consumer", "buyer"):
            role = "consumer"
        if not name or not email or len(pw) < 4:
            flash("Please fill all fields (password ≥ 4 chars).", "err")
            return render_template("register.html")
        if q("SELECT id FROM users WHERE email=?", (email,), one=True):
            flash("That email is already registered.", "err")
            return render_template("register.html")
        cur = get_db().execute(
            "INSERT INTO users(name,email,password_hash,role,phone,address,lat,lng) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (name, email, generate_password_hash(pw), role,
             request.form.get("phone", ""), request.form.get("address", ""),
             PUNE_CENTER[0], PUNE_CENTER[1]))
        if role == "farmer":
            village = request.form.get("village", "Pune district")
            get_db().execute(
                "INSERT INTO farms(user_id,name,village,district,lat,lng,organic,"
                "area_acres,rating) VALUES(?,?,?,?,?,?,?,?,?)",
                (cur.lastrowid, f"{name}'s Farm", village, "Pune",
                 PUNE_CENTER[0], PUNE_CENTER[1], 0, 2.0, 4.5))
        get_db().commit()
        session["uid"] = cur.lastrowid
        flash("Welcome to KrishiSetu! 🌱", "ok")
        return redirect(url_for({"farmer": "farmer_dash", "buyer": "buyer_dash"}
                                .get(role, "marketplace")))
    return render_template("register.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("Logged out. See you soon!", "ok")
    return redirect(url_for("index"))


# --------------------------------------------------------------- marketplace
@app.route("/marketplace")
def marketplace():
    query = LSEL + " WHERE l.status='active'"
    args = []
    srch = request.args.get("q", "").strip()
    if srch:
        query += " AND (c.name LIKE ? OR f.name LIKE ? OR f.village LIKE ?)"
        args += [f"%{srch}%"] * 3
    cat = request.args.get("cat", "")
    if cat:
        query += " AND c.category=?"
        args.append(cat)
    if request.args.get("organic") == "1":
        query += " AND l.organic=1"
    if request.args.get("fpo") == "1":
        query += " AND f.is_fpo=1"
    sort = request.args.get("sort", "rating")
    query += {"price_asc": " ORDER BY l.price ASC", "price_desc": " ORDER BY l.price DESC",
              "saving": " ORDER BY save_pct DESC"}.get(sort, " ORDER BY f.rating DESC, l.rating DESC")
    items = q(query, args)
    cats = q("SELECT DISTINCT category FROM crops ORDER BY category")
    return render_template("marketplace.html", items=items, cats=cats,
                           srch=srch, cat=cat, sort=sort,
                           organic=request.args.get("organic") == "1",
                           fpo=request.args.get("fpo") == "1")


@app.route("/product/<int:lid>")
def product(lid):
    item = q(LSEL + " WHERE l.id=?", (lid,), one=True)
    if not item:
        flash("Listing not found.", "err")
        return redirect(url_for("marketplace"))
    farm_crops = q("SELECT c.name, c.emoji FROM listings l JOIN crops c ON c.id=l.crop_id "
                   "WHERE l.farm_id=? AND l.status='active' LIMIT 5", (item["farm_id"],))
    sug = q("SELECT suggested_price FROM price_forecast WHERE crop=? "
            "ORDER BY date DESC LIMIT 1", (item["crop_name"],), one=True)
    return render_template("product.html", item=item, farm_crops=farm_crops, sug=sug)


# ---------------------------------------------------------------------- cart
@app.post("/cart/add/<int:lid>")
def cart_add(lid):
    item = q("SELECT l.*, c.name FROM listings l JOIN crops c ON c.id=l.crop_id "
             "WHERE l.id=?", (lid,), one=True)
    if not item:
        flash("Listing not found.", "err")
        return redirect(url_for("marketplace"))
    cart = session.setdefault("cart", {})
    qty = request.form.get("qty", type=float) or item["min_order"]
    qty = max(qty, item["min_order"])
    qty = min(qty, item["qty_available"])
    cart[str(lid)] = round(qty, 1)
    session.modified = True
    flash(f"Added {qty:g} kg {item['name']} to cart. 🧺", "ok")
    return redirect(request.referrer or url_for("marketplace"))


@app.post("/cart/update")
def cart_update():
    cart = session.get("cart", {})
    for key, val in request.form.items():
        if key.startswith("qty_") and key[4:].isdigit():
            try:
                v = max(float(val), 0)
            except ValueError:
                continue
            if v == 0:
                cart.pop(key[4:], None)
            else:
                cart[key[4:]] = round(v, 1)
    session.modified = True
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:lid>")
def cart_remove(lid):
    cart = session.get("cart", {})
    cart.pop(str(lid), None)
    session.modified = True
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    rows, subtotal, savings = cart_rows()
    fee = DELIVERY_FEE if (rows and subtotal < FREE_ABOVE) else 0
    return render_template("cart.html", rows=rows, subtotal=subtotal,
                           savings=savings, fee=fee, total=subtotal + fee)


# ------------------------------------------------------------------ checkout
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    u = current_user()
    if not u:
        flash("Log in to place your order.", "warn")
        return redirect(url_for("login", next="/checkout"))
    if u["role"] not in ("consumer", "buyer"):
        flash("Only consumer/buyer accounts can place orders.", "warn")
        return redirect(url_for("marketplace"))
    rows, subtotal, savings = cart_rows()
    if not rows:
        flash("Your cart is empty.", "warn")
        return redirect(url_for("marketplace"))
    fee = 0 if subtotal >= FREE_ABOVE else DELIVERY_FEE
    if request.method == "POST":
        address = request.form.get("address", "").strip() or u["address"] or "Pune"
        slot = request.form.get("slot", "9–11 AM")
        pay = request.form.get("payment", "UPI (demo)")
        lat = u["lat"] or PUNE_CENTER[0]
        lng = u["lng"] or PUNE_CENTER[1]
        total = subtotal + fee
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        cur = get_db().execute(
            "INSERT INTO orders(buyer_id,buyer_type,status,subtotal,savings,delivery_fee,"
            "total,payment_mode,address,lat,lng,slot,placed_on,created_ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (u["id"], "bulk" if u["role"] == "buyer" else "retail", "placed",
             subtotal, savings, fee, total, pay, address, lat, lng, slot,
             g.today.isoformat(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        oid = cur.lastrowid
        for r in rows:
            get_db().execute(
                "INSERT INTO order_items(order_id,listing_id,farmer_id,crop_id,crop_name,"
                "qty,price,amount) VALUES(?,?,?,?,?,?,?,?)",
                (oid, r["id"], q("SELECT user_id FROM farms WHERE id=?",
                                 (r["farm_id"],), one=True)["user_id"],
                 r["crop_id"], r["crop_name"], r["qty"], r["price"], r["amount"]))
            get_db().execute("UPDATE listings SET qty_available = MAX(0, qty_available-?) "
                             "WHERE id=?", (r["qty"], r["id"]))
        get_db().execute(
            "INSERT INTO deliveries(order_id,vehicle_id,stop_name,address,lat,lng,slot,"
            "ddate,seq,status) VALUES(?,NULL,?,?,?,?,?,?,0,'pending')",
            (oid, address.split(",")[0][:24], address, lat, lng, slot, tomorrow))
        get_db().commit()
        session["cart"] = {}
        session.modified = True
        flash("Order placed successfully! 🎉", "ok")
        return redirect(url_for("order_success", oid=oid))
    return render_template("checkout.html", rows=rows, subtotal=subtotal,
                           savings=savings, fee=fee, total=subtotal + fee,
                           slots=["9–11 AM", "11 AM–1 PM", "4–7 PM"],
                           tomorrow=(date.today() + timedelta(days=1)).strftime("%a, %d %b"))


@app.route("/order/<int:oid>/success")
def order_success(oid):
    order = q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not order:
        return redirect(url_for("marketplace"))
    items = q("SELECT * FROM order_items WHERE order_id=?", (oid,))
    return render_template("order_success.html", order=order, items=items)


@app.route("/orders")
def orders():
    u = current_user()
    if not u:
        return redirect(url_for("login", next="/orders"))
    if u["role"] == "farmer":
        return redirect(url_for("farmer_dash"))
    if u["role"] == "logistics":
        return redirect(url_for("logistics"))
    my = q("SELECT * FROM orders WHERE buyer_id=? ORDER BY id DESC LIMIT 30", (u["id"],))
    items = q("SELECT oi.*, u.name AS farmer_name FROM order_items oi "
              "LEFT JOIN farms f ON f.id = (SELECT farm_id FROM listings WHERE id=oi.listing_id) "
              "LEFT JOIN users u ON u.id=f.user_id")
    by_order = {}
    for it in items:
        by_order.setdefault(it["order_id"], []).append(it)
    return render_template("orders.html", orders=my, items=by_order)


@app.route("/track/<int:oid>")
def track(oid):
    order = q("SELECT o.*, u.name AS buyer_name FROM orders o JOIN users u ON u.id=o.buyer_id "
              "WHERE o.id=?", (oid,), one=True)
    if not order:
        flash("Order not found.", "err")
        return redirect(url_for("marketplace"))
    items = q("SELECT * FROM order_items WHERE order_id=?", (oid,))
    dlv = q("SELECT d.*, v.code AS vehicle, v.vtype FROM deliveries d "
            "LEFT JOIN vehicles v ON v.id=d.vehicle_id WHERE d.order_id=? "
            "ORDER BY d.ddate DESC LIMIT 1", (oid,), one=True)
    stops, cur_stop = [], None
    if dlv and dlv["vehicle_id"] and dlv["status"] != "delivered":
        stops = q("SELECT * FROM deliveries WHERE vehicle_id=? AND ddate=? ORDER BY seq",
                  (dlv["vehicle_id"], dlv["ddate"]))
        cur_stop = next((s for s in stops if s["id"] == dlv["id"]), None)
    return render_template("track.html", order=order, items=items, dlv=dlv,
                           steps=timeline_for(order), stops=stops, cur_stop=cur_stop,
                           map=route_map(HUB, [dict(s) for s in stops]) if stops else "")


# -------------------------------------------------------------------- farmer
@app.route("/farmer")
@login_required("farmer")
def farmer_dash():
    u = current_user()
    farm = q("SELECT * FROM farms WHERE user_id=?", (u["id"],), one=True)
    listings = q(LSEL + " WHERE l.farm_id=? ORDER BY l.id DESC",
                 (farm["id"],)) if farm else []
    since30 = (date.today() - timedelta(days=30)).isoformat()
    earn30 = q("SELECT COALESCE(SUM(oi.amount),0) AS n FROM order_items oi "
               "JOIN orders o ON o.id=oi.order_id WHERE oi.farmer_id=? AND o.placed_on>=? "
               "AND o.status!='cancelled'", (u["id"], since30), one=True)["n"]
    earn_total = q("SELECT COALESCE(SUM(amount),0) AS n FROM order_items WHERE farmer_id=?",
                   (u["id"],), one=True)["n"]
    pending = q("SELECT DISTINCT o.* FROM orders o JOIN order_items oi ON oi.order_id=o.id "
                "WHERE oi.farmer_id=? AND o.status IN ('placed','confirmed','packed') "
                "ORDER BY o.id DESC", (u["id"],))
    recent = q("SELECT DISTINCT o.* FROM orders o JOIN order_items oi ON oi.order_id=o.id "
               "WHERE oi.farmer_id=? ORDER BY o.id DESC LIMIT 8", (u["id"],))
    # earnings last 14 days
    days = [(date.today() - timedelta(days=k)) for k in range(13, -1, -1)]
    raw = q("SELECT o.placed_on AS d, SUM(oi.amount) AS v FROM order_items oi "
            "JOIN orders o ON o.id=oi.order_id WHERE oi.farmer_id=? AND o.placed_on>=? "
            "GROUP BY o.placed_on", (u["id"], days[0].isoformat()))
    m = {r["d"]: r["v"] for r in raw}
    earn_chart = line_chart([d.strftime("%d %b") for d in days],
                            [("Earnings ₹", "#2e7d32", [m.get(d.isoformat(), 0) for d in days])],
                            unit="₹")
    quotes = q("SELECT * FROM quotes WHERE status='open' ORDER BY id DESC LIMIT 5")
    order_items = q("SELECT oi.*, o.status AS ostatus FROM order_items oi "
                    "JOIN orders o ON o.id=oi.order_id WHERE oi.farmer_id=?", (u["id"],))
    items_by_order = {}
    for it in order_items:
        items_by_order.setdefault(it["order_id"], []).append(it)
    return render_template("farmer/dashboard.html", farm=farm, listings=listings,
                           earn30=earn30, earn_total=earn_total, pending=pending,
                           recent=recent, earn_chart=earn_chart, quotes=quotes,
                           items=items_by_order)


@app.route("/farmer/listings")
@login_required("farmer")
def farmer_listings():
    u = current_user()
    farm = q("SELECT * FROM farms WHERE user_id=?", (u["id"],), one=True)
    listings = q(LSEL + " WHERE l.farm_id=? ORDER BY l.id DESC", (farm["id"],))
    crops = q("SELECT * FROM crops ORDER BY name")
    return render_template("farmer/listings.html", farm=farm, listings=listings, crops=crops)


@app.post("/farmer/listings/new")
@login_required("farmer")
def farmer_listing_new():
    u = current_user()
    farm = q("SELECT * FROM farms WHERE user_id=?", (u["id"],), one=True)
    crop_id = request.form.get("crop_id", type=int)
    qty = request.form.get("qty", type=float) or 100
    price = request.form.get("price", type=float) or 10
    organic = 1 if request.form.get("organic") else (farm["organic"] if farm else 0)
    crop = q("SELECT * FROM crops WHERE id=?", (crop_id,), one=True)
    if crop and farm:
        get_db().execute(
            "INSERT INTO listings(farm_id,crop_id,qty_available,price,market_price,unit,"
            "grade,organic,min_order,harvested_days_ago,status,rating) "
            "VALUES(?,?,?,?,?,'kg','A',?,?,0,'active',4.5)",
            (farm["id"], crop_id, max(qty, 1), price, crop["base_price"],
             organic, max(request.form.get("min_order", type=float) or 1, 1)))
        get_db().commit()
        flash(f"Listing created: {crop['name']} at {inr(price)}/kg. 🌾", "ok")
    return redirect(url_for("farmer_listings"))


@app.post("/farmer/listings/<int:lid>/toggle")
@login_required("farmer")
def farmer_listing_toggle(lid):
    u = current_user()
    get_db().execute(
        "UPDATE listings SET status = CASE WHEN status='active' THEN 'paused' ELSE 'active' END "
        "WHERE id=? AND farm_id=(SELECT id FROM farms WHERE user_id=?)", (lid, u["id"]))
    get_db().commit()
    flash("Listing updated.", "ok")
    return redirect(url_for("farmer_listings"))


@app.post("/farmer/orders/<int:oid>/advance")
@login_required("farmer")
def farmer_order_advance(oid):
    u = current_user()
    has = q("SELECT id FROM order_items WHERE order_id=? AND farmer_id=?", (oid, u["id"]), one=True)
    order = q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    nxt = {"placed": "confirmed", "confirmed": "packed"}.get(order["status"]) if order else None
    if has and nxt:
        get_db().execute("UPDATE orders SET status=? WHERE id=?", (nxt, oid))
        get_db().commit()
        flash(f"Order #{oid} → {nxt}.", "ok")
    return redirect(request.referrer or url_for("farmer_dash"))


@app.route("/farmer/insights")
@login_required("farmer")
def farmer_insights():
    u = current_user()
    farm = q("SELECT * FROM farms WHERE user_id=?", (u["id"],), one=True)
    my_crops = q("SELECT DISTINCT c.name, c.emoji FROM listings l JOIN crops c ON c.id=l.crop_id "
                 "WHERE l.farm_id=? AND l.status='active'", (farm["id"],)) if farm else []
    sel = request.args.get("crop", type=str) or (my_crops[0]["name"] if my_crops else "Tomato")
    ins = crop_insight(sel)
    demand_chart = line_chart(ins["labels"], [
        ("Actual demand (kg/day)", "#5b8c5a", ins["actual"]),
        ("AI forecast", "#f9a825", ins["fdem"])], unit="")
    price_chart = line_chart(ins["labels"], [
        ("Mandi price ₹/kg", "#8d6e63", ins["pfc"])], unit="₹")
    rows = []
    for c in my_crops:
        ci = crop_insight(c["name"])
        mine = q("SELECT MIN(price) AS p FROM listings WHERE farm_id=? AND crop_id="
                 "(SELECT id FROM crops WHERE name=?) AND status='active'",
                 (farm["id"], c["name"]), one=True)
        rows.append(dict(crop=c["name"], emoji=c["emoji"], outlook=ci["outlook"],
                         pct=ci["outlook_pct"], suggested=ci["suggested"],
                         mine=mine["p"] if mine else None))
    metrics = {}
    try:
        with open(os.path.join(BASE, "ml", "models", "metrics.json")) as f:
            metrics = json.load(f)["overall"]
    except Exception:
        pass
    return render_template("farmer/insights.html", my_crops=my_crops, sel=sel, ins=ins,
                           demand_chart=demand_chart, price_chart=price_chart,
                           rows=rows, metrics=metrics)


# --------------------------------------------------------------------- buyer
@app.route("/buyer")
@login_required("buyer")
def buyer_dash():
    u = current_user()
    since30 = (date.today() - timedelta(days=30)).isoformat()
    agg = q("SELECT COUNT(*) AS n_orders, COALESCE(SUM(total),0) AS spend, "
            "COALESCE(SUM(savings),0) AS saved FROM orders WHERE buyer_id=? AND placed_on>=?",
            (u["id"], since30), one=True)
    my = q("SELECT * FROM orders WHERE buyer_id=? ORDER BY id DESC LIMIT 10", (u["id"],))
    top = q("SELECT crop_name, SUM(qty) AS kg FROM order_items oi JOIN orders o ON o.id=oi.order_id "
            "WHERE o.buyer_id=? GROUP BY crop_name ORDER BY kg DESC LIMIT 6", (u["id"],))
    top_chart = bar_chart([r["crop_name"].split(" (")[0] for r in top],
                          [r["kg"] for r in top], "#66bb6a", unit=" kg")
    myquotes = q("SELECT * FROM quotes WHERE contact=? ORDER BY id DESC", (u["email"],))
    crops = q("SELECT name FROM crops ORDER BY name")
    return render_template("buyer/dashboard.html", agg=agg, orders=my,
                           top_chart=top_chart, quotes=myquotes, crops=crops)


@app.post("/buyer/quote")
@login_required("buyer")
def buyer_quote():
    u = current_user()
    get_db().execute(
        "INSERT INTO quotes(buyer_name,org,crop_name,qty_kg,contact,note) VALUES(?,?,?,?,?,?)",
        (u["name"], u["name"], request.form.get("crop", ""),
         request.form.get("qty", type=float) or 100, u["email"],
         request.form.get("note", "")))
    get_db().commit()
    flash("Bulk quote request sent to FPOs & farmers. 🤝", "ok")
    return redirect(url_for("buyer_dash"))


# ----------------------------------------------------------------- logistics
@app.route("/logistics")
@login_required("logistics", "admin")
def logistics():
    vid = request.args.get("v", type=int)
    vehicles = q("SELECT * FROM vehicles ORDER BY id")
    on_route = q("SELECT vehicle_id FROM deliveries WHERE ddate=? AND status!='delivered' "
                 "AND vehicle_id IS NOT NULL LIMIT 1", (g.today.isoformat(),), one=True)
    if not vid and on_route:
        vid = on_route["vehicle_id"]
    if not vid and vehicles:
        vid = vehicles[0]["id"]
    stops = [dict(s) for s in q(
        "SELECT d.*, o.status AS ostatus FROM deliveries d LEFT JOIN orders o ON o.id=d.order_id "
        "WHERE d.vehicle_id=? AND d.ddate=? ORDER BY d.seq", (vid, g.today.isoformat()))] if vid else []
    live = [s for s in stops if s["status"] != "delivered"]
    cur_km = opt = None
    if len(live) >= 2:
        pts = [{"lat": s["lat"], "lng": s["lng"]} for s in live]
        cur_km = route_length_km(HUB, list(range(len(pts))), pts)
        opt = optimize_route(HUB, pts)
    pending = q("SELECT d.* FROM deliveries d "
                "WHERE d.vehicle_id IS NULL AND d.status='pending' AND d.ddate>=?",
                (g.today.isoformat(),))
    kpi = dict(stops=len(stops), done=sum(1 for s in stops if s["status"] == "delivered"),
               vehicles=len([v for v in vehicles if v["status"] == "on_route"]))
    return render_template("logistics/dashboard.html", vehicles=vehicles, vid=vid,
                           stops=stops, live=live, cur_km=cur_km, opt=opt,
                           pending=pending, kpi=kpi, hub=HUB,
                           map=route_map(HUB, stops))


@app.post("/logistics/vehicle/<int:vid>/optimize")
@login_required("logistics", "admin")
def logistics_optimize(vid):
    stops = q("SELECT * FROM deliveries WHERE vehicle_id=? AND ddate=? AND status!='delivered' "
              "ORDER BY seq", (vid, g.today.isoformat()))
    if len(stops) >= 2:
        res = optimize_route(HUB, [{"lat": s["lat"], "lng": s["lng"]} for s in stops])
        for pos, idx in enumerate(res["order"]):
            get_db().execute("UPDATE deliveries SET seq=? WHERE id=?", (pos, stops[idx]["id"]))
        get_db().commit()
        flash(f"🚚 Route optimized with NN + 2-opt: saved {res['km_saved']} km "
              f"({res['pct_saved']}%) and ~{res['min_saved']} min drive time.", "ok")
    else:
        flash("Not enough live stops to optimize.", "warn")
    return redirect(url_for("logistics", v=vid))


@app.post("/logistics/vehicle/<int:vid>/scramble")
@login_required("logistics", "admin")
def logistics_scramble(vid):
    stops = q("SELECT * FROM deliveries WHERE vehicle_id=? AND ddate=? AND status!='delivered' "
              "ORDER BY seq DESC", (vid, g.today.isoformat()))
    for pos, s in enumerate(stops):
        get_db().execute("UPDATE deliveries SET seq=? WHERE id=?", (pos, s["id"]))
    get_db().commit()
    flash("Route scrambled (demo: unoptimized sequence).", "warn")
    return redirect(url_for("logistics", v=vid))


@app.post("/logistics/delivery/<int:did>/delivered")
@login_required("logistics", "admin")
def logistics_delivered(did):
    d = q("SELECT * FROM deliveries WHERE id=?", (did,), one=True)
    if d:
        get_db().execute("UPDATE deliveries SET status='delivered' WHERE id=?", (did,))
        get_db().execute("UPDATE orders SET status='delivered' WHERE id=?", (d["order_id"],))
        left = q("SELECT COUNT(*) AS n FROM deliveries WHERE vehicle_id=? AND ddate=? "
                 "AND status!='delivered'", (d["vehicle_id"], g.today.isoformat()), one=True)["n"]
        if left == 0:
            get_db().execute("UPDATE vehicles SET status='idle' WHERE id=?", (d["vehicle_id"],))
        get_db().commit()
        flash("Stop marked delivered ✅", "ok")
    return redirect(request.referrer or url_for("logistics"))


# --------------------------------------------------------------------- admin
@app.route("/admin")
@login_required("admin")
def admin():
    kpi = dict(
        farmers=q("SELECT COUNT(*) AS n FROM users WHERE role='farmer'", one=True)["n"],
        fpos=q("SELECT COUNT(*) AS n FROM farms WHERE is_fpo=1", one=True)["n"],
        consumers=q("SELECT COUNT(*) AS n FROM users WHERE role='consumer'", one=True)["n"],
        buyers=q("SELECT COUNT(*) AS n FROM users WHERE role='buyer'", one=True)["n"],
        orders=q("SELECT COUNT(*) AS n FROM orders", one=True)["n"],
        delivered=q("SELECT COUNT(*) AS n FROM orders WHERE status='delivered'", one=True)["n"],
        save_pct=q("SELECT ROUND(AVG(savings*100.0/subtotal),1) AS n FROM orders "
                   "WHERE subtotal>0", one=True)["n"],
        premium=q("SELECT ROUND(AVG((market_price-price)*100.0/market_price),1) AS n "
                  "FROM listings", one=True)["n"],
    )
    since30 = (date.today() - timedelta(days=30)).isoformat()
    kpi["gmv30"] = q("SELECT COALESCE(SUM(total),0) AS n FROM orders WHERE placed_on>=? "
                     "AND status!='cancelled'", (since30,), one=True)["n"]

    days = [(date.today() - timedelta(days=k)) for k in range(13, -1, -1)]
    raw = q("SELECT placed_on AS d, SUM(total) AS v FROM orders WHERE placed_on>=? "
            "AND status!='cancelled' GROUP BY placed_on", (days[0].isoformat(),))
    m = {r["d"]: r["v"] for r in raw}
    gmv_chart = line_chart([d.strftime("%d %b") for d in days],
                           [("GMV ₹", "#2e7d32", [m.get(d.isoformat(), 0) for d in days])],
                           unit="₹")

    top = q("SELECT crop_name, SUM(qty) AS kg FROM order_items GROUP BY crop_name "
            "ORDER BY kg DESC LIMIT 8")
    top_chart = bar_chart([r["crop_name"].split(" (")[0] for r in top],
                          [r["kg"] for r in top], "#f9a825", unit=" kg")

    staples = ["Tomato", "Onion", "Potato", "Rice (Sona Masoori)", "Wheat"]
    fc = []
    for name in staples:
        ci = crop_insight(name)
        fc.append(dict(name=name, sug=ci["suggested"], mandi=ci["mandi_pred"],
                       outlook=ci["outlook"], pct=ci["outlook_pct"]))

    metrics = {}
    try:
        with open(os.path.join(BASE, "ml", "models", "metrics.json")) as f:
            metrics = json.load(f)["overall"]
    except Exception:
        pass
    return render_template("admin/dashboard.html", kpi=kpi, gmv_chart=gmv_chart,
                           top_chart=top_chart, fc=fc, metrics=metrics)


# ----------------------------------------------------------------------- API
@app.get("/api/forecast/<path:crop>")
def api_forecast(crop):
    ins = crop_insight(crop)
    return jsonify(dict(crop=crop,
                        demand=[{"date": d["date"], "kg": d["pred_kg"]} for d in ins["fc_d"]],
                        price=[{"date": d["date"], "market": d["market_pred"],
                                "suggested": d["suggested_price"]} for d in ins["fc_p"]],
                        outlook=ins["outlook"], outlook_pct=ins["outlook_pct"]))


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
