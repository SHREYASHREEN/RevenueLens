"""Create demo users, load the synthetic dataset and generate SAMPLE targets (all fictional)."""
import sqlite3
import random
from . import auth, config, datagen, db, loader, targets

DEMO_USERS = [("admin", "Demo Admin", "RL-Admin@123", "Admin"),
              ("analyst", "Demo Analyst", "RL-Analyst@123", "Analyst"),
              ("viewer", "Demo Viewer", "RL-Viewer@123", "Viewer")]


def seed_users(conn):
    for username, full_name, password, role in DEMO_USERS:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            continue

        try:
            auth.create_user(
                conn,
                username,
                full_name,
                password,
                role
            )
        except sqlite3.IntegrityError:
            # Another startup process may have created this user.
            if not conn.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username,)
            ).fetchone():
                raise

def seed_transactions(conn, replace=False):
    if not replace and conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] > 0:
        return False
    loader.import_dataframe(conn, datagen.generate(), source="synthetic generator", user="seed", replace=replace, synthetic=True)
    return True


def seed_targets(conn, seed=config.SEED):
    """SAMPLE targets: each month's company and region target is the actual revenue scaled by a random factor
    (0.90-1.15), so some segments land above and some below target. Labelled sample data."""
    if conn.execute("SELECT COUNT(*) FROM sales_targets").fetchone()[0] > 0:
        return False
    rnd = random.Random(seed)
    for m in conn.execute("SELECT month, SUM(revenue) AS r FROM valid_orders GROUP BY month ORDER BY month").fetchall():
        targets.set_target(conn, m["month"], "All", "All", "All", round(m["r"] * rnd.uniform(0.92, 1.12), -3))
    for r in conn.execute("SELECT month, region, SUM(revenue) AS r FROM valid_orders GROUP BY month, region ORDER BY month, region").fetchall():
        targets.set_target(conn, r["month"], r["region"], "All", "All", round(r["r"] * rnd.uniform(0.90, 1.15), -3))
    return True
