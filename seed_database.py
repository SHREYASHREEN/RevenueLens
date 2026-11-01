"""Create the database, demo users, synthetic data and sample targets.
Run from the project folder:  python scripts/seed_database.py      (add --reset to reload the data)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from revenuelens import db, seed  # noqa: E402


def main():
    conn = db.connect()
    db.init_db(conn)
    reset = "--reset" in sys.argv
    if reset:
        conn.execute("DELETE FROM sales_targets"); conn.commit()
    seed.seed_users(conn)
    loaded = seed.seed_transactions(conn, replace=reset)
    seed.seed_targets(conn)
    n = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    print(("Loaded" if loaded else "Already loaded:") + f" {n} synthetic transactions.")
    print("Demo logins: admin / RL-Admin@123, analyst / RL-Analyst@123, viewer / RL-Viewer@123")
    print("Change these passwords before using the app with any real data.")
    conn.close()


if __name__ == "__main__":
    main()
