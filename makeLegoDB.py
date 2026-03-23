import sqlite3
import csv
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "csv"
DB_PATH = BASE_DIR / "lego.db"

THEMES_CSV = CSV_DIR / "themes.csv"
SETS_CSV = CSV_DIR / "sets.csv"

class ProgressBar:
    def __init__(self, total, width=30):
        self.total = total
        self.width = width
        self.start = time.time()

    def update(self, current, label=""):
        progress = current / self.total if self.total else 1
        filled = int(self.width * progress)
        bar = "#" * filled + "-" * (self.width - filled)

        elapsed = time.time() - self.start
        eta = (elapsed / progress - elapsed) if progress > 0 else 0

        sys.stdout.write(
            f"\r[{bar}] {int(progress*100):3d}% | ETA {eta:6.1f}s | {label}"
        )
        sys.stdout.flush()

        if current >= self.total:
            sys.stdout.write("\n")

def count_rows(csv_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY,
            name TEXT,
            parent_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS sets (
            set_num TEXT PRIMARY KEY,
            name TEXT,
            theme_id INTEGER,
            num_parts INTEGER,
            release_year INTEGER,
            FOREIGN KEY(theme_id) REFERENCES themes(id)
        );

        CREATE TABLE IF NOT EXISTS owned_sets (
            set_num TEXT PRIMARY KEY,
            condition INTEGER,
            note TEXT,
            FOREIGN KEY(set_num) REFERENCES sets(set_num)
        );

        CREATE INDEX IF NOT EXISTS idx_sets_setnum
        ON sets(set_num);
        """
    )

def import_themes(conn):
    total = count_rows(THEMES_CSV)
    progress = ProgressBar(total)

    with open(THEMES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cur = conn.cursor()
        for i, row in enumerate(reader, 1):
            parent = row["parent_id"] if row["parent_id"] else None

            cur.execute(
                """
                INSERT OR REPLACE INTO themes
                (id, name, parent_id)
                VALUES (?, ?, ?)
                """,
                (
                    int(row["id"]),
                    row["name"],
                    int(parent) if parent else None,
                ),
            )
            progress.update(i, "themes.csv")
    conn.commit()

def import_sets(conn):
    total = count_rows(SETS_CSV)
    progress = ProgressBar(total)

    with open(SETS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cur = conn.cursor()

        for i, row in enumerate(reader, 1):

            cur.execute(
                """
                INSERT OR REPLACE INTO sets
                (set_num, name, theme_id, num_parts, release_year)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["set_num"],
                    row["name"],
                    int(row["theme_id"]) if row["theme_id"] else None,
                    int(row["num_parts"]) if row["num_parts"] else None,
                    int(row["year"]) if row["year"] else None,
                ),
            )

            progress.update(i, "sets.csv")
    conn.commit()

def build_database():
    print("Mode: BUILD")
    conn = connect_db()
    create_tables(conn)
    print("Importing themes")
    import_themes(conn)
    print("Importing sets")
    import_sets(conn)
    conn.close()
    print("Database build complete")

def update_database():
    print("Mode: UPDATE")
    conn = connect_db()
    print("Updating themes")
    import_themes(conn)
    print("Updating sets")
    import_sets(conn)
    conn.close()
    print("Database update complete")

def detect_mode():
    return update_database if DB_PATH.exists() else build_database

def validate_files():
    required = [THEMES_CSV, SETS_CSV]
    missing = [p for p in required if not p.exists()]

    if missing:
        print("Missing CSV files:")
        for m in missing:
            print(m)
        sys.exit(1)

def main():
    validate_files()
    mode = detect_mode()
    start = time.time()
    mode()
    elapsed = time.time() - start
    print(f"Total time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    main()
