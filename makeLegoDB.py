from __future__ import annotations

import csv
import sqlite3
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "csv"
DB_PATH = BASE_DIR / "lego.db"

THEMES_CSV = CSV_DIR / "themes.csv"
SETS_CSV = CSV_DIR / "sets.csv"


@dataclass(frozen=True)
class ImportSummary:
    source: str
    total_rows: int
    imported_rows: int
    skipped_rows: int


class ProgressBar:
    def __init__(self, total: int, width: int = 30) -> None:
        self.total = max(int(total), 0)
        self.width = max(int(width), 1)
        self.start = time.time()

    def update(self, current: int, label: str = "") -> None:
        current = max(int(current), 0)
        if self.total > 0:
            progress = min(max(current / self.total, 0.0), 1.0)
        else:
            progress = 1.0 if current > 0 else 0.0

        filled = int(self.width * progress)
        bar = "#" * filled + "-" * (self.width - filled)

        elapsed = time.time() - self.start
        eta = (elapsed / progress - elapsed) if progress > 0 else 0.0

        sys.stdout.write(
            f"\r[{bar}] {int(progress * 100):3d}% | ETA {eta:6.1f}s | {label}"
        )
        sys.stdout.flush()

        if self.total == 0 or current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def finish(self, label: str = "") -> None:
        self.update(self.total if self.total > 0 else 0, label=label)


def validate_files() -> None:
    required = [THEMES_CSV, SETS_CSV]
    missing = [p for p in required if not p.exists()]
    if missing:
        print("Missing CSV files:", file=sys.stderr)
        for m in missing:
            print(f" - {m}", file=sys.stderr)
        raise SystemExit(1)


def count_rows(csv_path: Path) -> int:
    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row and any((value or "").strip() for value in row.values()):
                count += 1
    return count


def iter_csv_rows(csv_path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_no, row in enumerate(reader, start=2):
            if row and any((value or "").strip() for value in row.values()):
                yield row_no, row


def clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


def get_text(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def parse_required_int(
    value: Optional[str],
    *,
    field_name: str,
    source: Path,
    row_no: int,
) -> int:
    text = clean_text(value)
    if not text:
        raise ValueError(f"missing required field '{field_name}'")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(
            f"{source.name}: invalid integer in field '{field_name}' at row {row_no}: {text!r}"
        ) from exc


def parse_optional_int(
    value: Optional[str],
    *,
    field_name: str,
    source: Path,
    row_no: int,
) -> Optional[int]:
    text = clean_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(
            f"{source.name}: invalid integer in field '{field_name}' at row {row_no}: {text!r}"
        ) from exc


class DatabaseBuilder:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def reset_database_file(self) -> None:
        for path in (
            self.db_path,
            self.db_path.with_suffix(self.db_path.suffix + "-wal"),
            self.db_path.with_suffix(self.db_path.suffix + "-shm"),
        ):
            with suppress(FileNotFoundError):
                path.unlink()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 3000")
        conn.execute("PRAGMA synchronous = NORMAL")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        return conn

    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS themes (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id INTEGER,
                FOREIGN KEY(parent_id) REFERENCES themes(id)
                    ON UPDATE CASCADE
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sets (
                set_num TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                theme_id INTEGER,
                num_parts INTEGER,
                release INTEGER,
                FOREIGN KEY(theme_id) REFERENCES themes(id)
                    ON UPDATE CASCADE
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS owned_sets (
                set_num TEXT PRIMARY KEY,
                condition INTEGER NOT NULL DEFAULT 0 CHECK (condition IN (0, 1, 2)),
                note TEXT,
                FOREIGN KEY(set_num) REFERENCES sets(set_num)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            );
            """
        )

    def _log_skip(self, csv_path: Path, row_no: int, exc: Exception) -> None:
        print(f"[skip] {csv_path.name}:{row_no}: {exc}", file=sys.stderr)

    def import_themes(self, conn: sqlite3.Connection) -> ImportSummary:
        total = count_rows(THEMES_CSV)
        progress = ProgressBar(total)

        imported_rows = 0
        skipped_rows = 0
        processed_rows = 0
        records: dict[int, tuple[str, Optional[int]]] = {}

        for row_no, row in iter_csv_rows(THEMES_CSV):
            processed_rows += 1
            try:
                theme_id = parse_required_int(
                    row.get("id"),
                    field_name="id",
                    source=THEMES_CSV,
                    row_no=row_no,
                )
                name = clean_text(row.get("name"))
                if not name:
                    raise ValueError("missing required field 'name'")

                parent_id = parse_optional_int(
                    row.get("parent_id"),
                    field_name="parent_id",
                    source=THEMES_CSV,
                    row_no=row_no,
                )

                records[theme_id] = (name, parent_id)
                imported_rows += 1
            except Exception as exc:
                skipped_rows += 1
                self._log_skip(THEMES_CSV, row_no, exc)

            progress.update(processed_rows, "themes.csv")

        with conn:
            cur = conn.cursor()

            for theme_id, (name, _parent_id) in records.items():
                cur.execute(
                    """
                    INSERT INTO themes (id, name, parent_id)
                    VALUES (?, ?, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        parent_id = NULL
                    """,
                    (theme_id, name),
                )

            existing_ids = set(records.keys())
            for theme_id, (_name, parent_id) in records.items():
                if parent_id is None or parent_id == theme_id or parent_id not in existing_ids:
                    if parent_id is not None and parent_id not in existing_ids:
                        print(
                            f"[warn] {THEMES_CSV.name}: theme {theme_id} references missing parent_id {parent_id}; stored as NULL",
                            file=sys.stderr,
                        )
                    cur.execute("UPDATE themes SET parent_id = NULL WHERE id = ?", (theme_id,))
                else:
                    cur.execute(
                        "UPDATE themes SET parent_id = ? WHERE id = ?",
                        (parent_id, theme_id),
                    )

        progress.finish("themes.csv")
        return ImportSummary(
            source="themes.csv",
            total_rows=total,
            imported_rows=imported_rows,
            skipped_rows=skipped_rows,
        )

    def import_sets(self, conn: sqlite3.Connection) -> ImportSummary:
        total = count_rows(SETS_CSV)
        progress = ProgressBar(total)

        imported_rows = 0
        skipped_rows = 0
        processed_rows = 0

        with conn:
            cur = conn.cursor()
            for row_no, row in iter_csv_rows(SETS_CSV):
                processed_rows += 1
                try:
                    set_num = clean_text(row.get("set_num"))
                    if not set_num:
                        raise ValueError("missing required field 'set_num'")

                    name = clean_text(row.get("name"))
                    if not name:
                        raise ValueError("missing required field 'name'")

                    theme_id = parse_optional_int(
                        row.get("theme_id"),
                        field_name="theme_id",
                        source=SETS_CSV,
                        row_no=row_no,
                    )
                    num_parts = parse_optional_int(
                        row.get("num_parts"),
                        field_name="num_parts",
                        source=SETS_CSV,
                        row_no=row_no,
                    )
                    release = parse_optional_int(
                        get_text(row, "year", "release"),
                        field_name="year",
                        source=SETS_CSV,
                        row_no=row_no,
                    )

                    cur.execute(
                        """
                        INSERT INTO sets (set_num, name, theme_id, num_parts, release)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(set_num) DO UPDATE SET
                            name = excluded.name,
                            theme_id = excluded.theme_id,
                            num_parts = excluded.num_parts,
                            release = excluded.release
                        """,
                        (set_num, name, theme_id, num_parts, release),
                    )
                    imported_rows += 1
                except Exception as exc:
                    skipped_rows += 1
                    self._log_skip(SETS_CSV, row_no, exc)

                progress.update(processed_rows, "sets.csv")

        progress.finish("sets.csv")
        return ImportSummary(
            source="sets.csv",
            total_rows=total,
            imported_rows=imported_rows,
            skipped_rows=skipped_rows,
        )

    def build_database(self) -> tuple[ImportSummary, ImportSummary]:
        print("Mode: BUILD")
        self.reset_database_file()
        with self.connect() as conn:
            self.create_tables(conn)
            print("Importing themes")
            themes = self.import_themes(conn)
            print("Importing sets")
            sets = self.import_sets(conn)
        return themes, sets

    def update_database(self) -> tuple[ImportSummary, ImportSummary]:
        print("Mode: UPDATE")
        with self.connect() as conn:
            self.create_tables(conn)
            print("Updating themes")
            themes = self.import_themes(conn)
            print("Updating sets")
            sets = self.import_sets(conn)
        return themes, sets


def detect_mode() -> str:
    return "update" if DB_PATH.exists() else "build"


def main() -> None:
    validate_files()

    builder = DatabaseBuilder(DB_PATH)
    mode = detect_mode()

    start = time.time()
    try:
        if mode == "build":
            themes_summary, sets_summary = builder.build_database()
        else:
            themes_summary, sets_summary = builder.update_database()
    except Exception as exc:
        print(f"Database operation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    elapsed = time.time() - start
    print(
        f"Imported {themes_summary.imported_rows}/{themes_summary.total_rows} rows from themes.csv "
        f"(skipped {themes_summary.skipped_rows})"
    )
    print(
        f"Imported {sets_summary.imported_rows}/{sets_summary.total_rows} rows from sets.csv "
        f"(skipped {sets_summary.skipped_rows})"
    )
    print(f"Total time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
