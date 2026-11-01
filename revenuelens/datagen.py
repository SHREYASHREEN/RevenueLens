"""Deterministic SYNTHETIC sales data generator (fixed seed => identical output every run).
Nothing here is real company data."""
import random
from datetime import date, timedelta
import pandas as pd
from . import config

# product, category, list price, unit cost as fraction of price
PRODUCTS = [
    ("Aero Laptop 14", "Electronics", 62000, 0.78), ("Pulse Smartphone", "Electronics", 34000, 0.80),
    ("Nimbus Headphones", "Electronics", 8500, 0.62), ("Vista 4K Monitor", "Electronics", 21000, 0.86),
    ("Orbit Smartwatch", "Electronics", 12500, 0.70),
    ("ErgoChair Pro", "Furniture", 15500, 0.66), ("Oak Study Desk", "Furniture", 18500, 0.60),
    ("Cloud Sofa 3-Seat", "Furniture", 42000, 0.72), ("Nord Bookshelf", "Furniture", 9500, 0.55),
    ("Lumen Floor Lamp", "Furniture", 4200, 0.50),
    ("Fresh Blend Coffee 1kg", "Grocery", 950, 0.70), ("Organic Tea Box", "Grocery", 620, 0.58),
    ("Premium Olive Oil 1L", "Grocery", 1150, 0.74), ("Mixed Nuts Pack", "Grocery", 780, 0.64),
    ("Whole Grain Cereal", "Grocery", 410, 0.60),
    ("Trail Running Shoes", "Apparel", 6200, 0.52), ("Merino Jacket", "Apparel", 9800, 0.58),
    ("Everyday Denim", "Apparel", 3100, 0.48), ("Cotton Tee 3-Pack", "Apparel", 1400, 0.44),
    ("Rain Shell", "Apparel", 5200, 0.55),
    ("Smart Desk Organiser", "Office", 2400, 0.50), ("Noise-Free Keyboard", "Office", 5600, 0.60),
    ("Ink Pro Printer", "Office", 14800, 0.84), ("Paper Ream Box", "Office", 1900, 0.72),
    ("Whiteboard 4ft", "Office", 3800, 0.56),
]
REGIONS = {"North": 1.0, "South": 1.25, "East": 0.85, "West": 1.15, "Central": 0.7}
CHANNELS = {"Online": 1.4, "Retail Store": 1.0, "Distributor": 0.7, "Direct Sales": 0.5}
SEGMENTS = {"Consumer": 0.55, "Small Business": 0.3, "Enterprise": 0.15}
STATUSES = {"Completed": 0.90, "Cancelled": 0.04, "Returned": 0.04, "Refunded": 0.02}
DISCOUNTS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]
MONTH_FACTOR = {1: 0.9, 2: 0.85, 3: 1.0, 4: 1.0, 5: 1.05, 6: 0.95, 7: 0.9, 8: 1.0, 9: 1.05, 10: 1.25, 11: 1.35, 12: 1.2}


def generate(n=config.N_ORDERS, seed=config.SEED, start=date(2025, 1, 1), end=date(2026, 6, 30)):
    rnd = random.Random(seed)
    days = (end - start).days + 1
    day_list = [start + timedelta(days=i) for i in range(days)]
    day_weights = [MONTH_FACTOR[d.month] * (1 + 0.15 * ((d.year - 2025) * 12 + d.month) / 18) for d in day_list]
    rows = []
    for i in range(1, n + 1):
        d = rnd.choices(day_list, day_weights)[0]
        name, cat, price, cost_frac = rnd.choices(PRODUCTS, [3 if p[2] < 10000 else 1.5 for p in PRODUCTS])[0]
        region = rnd.choices(list(REGIONS), list(REGIONS.values()))[0]
        channel = rnd.choices(list(CHANNELS), list(CHANNELS.values()))[0]
        segment = rnd.choices(list(SEGMENTS), list(SEGMENTS.values()))[0]
        qty = rnd.choices([1, 2, 3, 4, 5, 8, 10], [40, 25, 15, 8, 6, 4, 2])[0] if price < 10000 else rnd.choices([1, 2, 3], [70, 22, 8])[0]
        discount = rnd.choices(DISCOUNTS, [30, 25, 20, 12, 9, 4] if channel != "Distributor" else [10, 15, 25, 25, 15, 10])[0]
        unit_price = round(price * rnd.uniform(0.97, 1.03), 2)
        unit_cost = round(price * cost_frac * rnd.uniform(0.98, 1.02), 2)
        status = rnd.choices(list(STATUSES), list(STATUSES.values()))[0]
        rows.append({"order_id": f"ORD-{i:06d}", "order_date": d.isoformat(), "product": name, "category": cat,
                     "region": region, "channel": channel, "quantity": qty, "unit_price": unit_price,
                     "discount": discount, "unit_cost": unit_cost, "customer_segment": segment, "status": status})
    df = pd.DataFrame(rows).sort_values(["order_date", "order_id"]).reset_index(drop=True)
    return df


def write_csv(path=config.SAMPLE_CSV, **kw):
    df = generate(**kw)
    df.to_csv(path, index=False)
    return df
