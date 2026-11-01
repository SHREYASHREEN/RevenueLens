"""Validate and clean raw sales data before it touches the database."""
import io
import math
from datetime import datetime
import pandas as pd
from . import config

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def parse_date(value):
    s = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date '{value}'")


def _num(value, name):
    s = str(value).strip().replace(",", "")
    if s == "":
        raise ValueError(f"{name} is missing")
    try:
        x = float(s)
    except ValueError:
        raise ValueError(f"{name} '{value}' is not a number")
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f"{name} is not finite")
    return x


def clean_row(raw):
    """Return a clean dict or raise ValueError with a human message."""
    out = {}
    for col in ("order_id", "product", "category", "region", "channel"):
        v = str(raw.get(col, "")).strip()
        if v == "" or v.lower() in ("nan", "none", "null"):
            raise ValueError(f"{col} is missing")
        out[col] = v
    out["order_date"] = parse_date(raw.get("order_date", ""))
    qty = _num(raw.get("quantity", ""), "quantity")
    if qty != int(qty) or qty <= 0:
        raise ValueError("quantity must be a positive whole number")
    out["quantity"] = int(qty)
    price = _num(raw.get("unit_price", ""), "unit_price")
    if price <= 0:
        raise ValueError("unit_price must be greater than 0")
    out["unit_price"] = price
    disc_raw = str(raw.get("discount", "")).strip()
    disc = 0.0 if disc_raw == "" else _num(disc_raw, "discount")  # a blank discount means no discount
    if disc < 0 or disc > 1:
        raise ValueError("discount must be a fraction between 0 and 1 (e.g. 0.15 for 15%)")
    out["discount"] = disc
    cost = _num(raw.get("unit_cost", ""), "unit_cost")
    if cost < 0:
        raise ValueError("unit_cost cannot be negative")
    out["unit_cost"] = cost
    status = str(raw.get("status", "")).strip().title()
    if status not in config.ALL_STATUSES:
        raise ValueError(f"status '{raw.get('status')}' must be one of {', '.join(config.ALL_STATUSES)}")
    out["status"] = status
    seg = str(raw.get("customer_segment", raw.get("segment", ""))).strip()
    out["segment"] = "Unknown" if seg == "" or seg.lower() in ("nan", "none", "null") else seg
    return out


def clean_dataframe(df):
    """Returns (clean_rows, report). Duplicate order IDs inside the file: first kept, later ones counted."""
    report = {"rows_read": len(df), "valid": 0, "rejected": 0, "duplicates_in_file": 0,
              "segment_filled": 0, "errors": [], "missing_columns": []}
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        report["missing_columns"] = missing
        report["errors"].append("Missing required column(s): " + ", ".join(missing))
        return [], report
    seen, rows = set(), []
    for idx, raw in df.iterrows():
        line = idx + 2
        oid = str(raw.get("order_id", "")).strip()
        if oid in seen:
            report["duplicates_in_file"] += 1
            report["errors"].append(f"Line {line}: duplicate order_id {oid} skipped.")
            continue
        try:
            row = clean_row(raw.to_dict())
        except ValueError as exc:
            report["rejected"] += 1
            report["errors"].append(f"Line {line}: {exc}")
            continue
        if row["segment"] == "Unknown":
            report["segment_filled"] += 1
        seen.add(oid)
        rows.append(row)
    report["valid"] = len(rows)
    return rows, report


def read_csv(file_or_bytes):
    raw = file_or_bytes.read() if hasattr(file_or_bytes, "read") else file_or_bytes
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    return pd.read_csv(io.StringIO(raw), dtype=str, keep_default_na=False)
