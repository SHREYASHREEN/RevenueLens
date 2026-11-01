"""Regenerate sample_data/synthetic_sales.csv (deterministic, fixed seed).  Run:  python scripts/generate_dataset.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from revenuelens import datagen  # noqa: E402

df = datagen.write_csv()
print(f"Wrote {len(df)} SYNTHETIC orders to sample_data/synthetic_sales.csv")
