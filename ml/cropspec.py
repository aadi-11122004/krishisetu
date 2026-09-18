"""Shared crop specification + calendar helpers for KrishiSetu ML pipeline."""

# (name, emoji, category, unit, base_mandi_price_rs_per_kg, base_daily_city_demand_kg,
#  peak_months, low_months)
CROP_SPEC = [
    ("Tomato",               "🍅", "Vegetable",    "kg", 32.0, 4200, [12, 1, 2, 3], [6, 7]),
    ("Onion",                "🧅", "Vegetable",    "kg", 26.0, 5200, [11, 12, 1],   [4, 5]),
    ("Potato",               "🥔", "Vegetable",    "kg", 28.0, 4800, [1, 2],        [7, 8]),
    ("Carrot",               "🥕", "Vegetable",    "kg", 44.0, 900,  [12, 1],       [6, 7]),
    ("Spinach",              "🥬", "Leafy Greens", "kg", 30.0, 750,  [11, 12, 1],   [5, 6]),
    ("Green Chilli",         "🌶️", "Spice",        "kg", 58.0, 650,  [6, 7, 8],     [12, 1]),
    ("Wheat",                "🌾", "Grain",        "kg", 29.0, 6800, [3, 4],        [9, 10]),
    ("Rice (Sona Masoori)",  "🍚", "Grain",        "kg", 54.0, 6200, [11, 12, 1],   [6, 7]),
    ("Alphonso Mango",       "🥭", "Fruit",        "kg", 135.0, 1400, [4, 5],       [8, 9]),
    ("Banana (Elaichi)",     "🍌", "Fruit",        "kg", 46.0, 2600, [9, 10],       [2, 3]),
    ("Grapes (Thompson)",    "🍇", "Fruit",        "kg", 72.0, 1900, [1, 2, 3],     [7, 8]),
    ("Mosambi (Sweet Lime)", "🍋", "Fruit",        "kg", 50.0, 1100, [12, 1, 2],    [6, 7]),
]

# Festival / payday-ish dates (month, day) that spike demand
FEST_DAYS = {
    (1, 1), (1, 14), (1, 26), (3, 4), (3, 14), (3, 25), (4, 2), (4, 14),
    (6, 7), (8, 15), (8, 28), (9, 7), (10, 2), (10, 21), (11, 1), (11, 8),
    (11, 12), (12, 25),
}

# Retail demand dips on Tue/Wed, peaks on Fri/weekend
DOW_FACTOR = {0: 0.90, 1: 0.85, 2: 0.95, 3: 1.00, 4: 1.06, 5: 1.18, 6: 1.14}


def is_festival(d):
    """1 if d (datetime.date) is within +/-1 day of a festival date."""
    from datetime import timedelta
    for off in (-1, 0, 1):
        dd = d + timedelta(days=off)
        if (dd.month, dd.day) in FEST_DAYS:
            return 1
    return 0
