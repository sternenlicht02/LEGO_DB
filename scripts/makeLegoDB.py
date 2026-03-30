from __future__ import annotations

import csv
import logging
import sqlite3
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from importlib.resources import files
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "lego.db"

CSV_DIR = files("lego_db.data.csv")

THEMES_CSV = CSV_DIR.joinpath("themes.csv")
SETS_CSV = CSV_DIR.joinpath("sets.csv")

LOGGER = logging.getLogger("makeLegoDB")


@dataclass(frozen=True)
class ImportSummary:
    source: str
    total_rows: int
    imported_rows: int
    skipped_rows: int


@dataclass(frozen=True)
class ThemeRecord:
    theme_id: int
    name: str
    parent_id: Optional[int]


@dataclass(frozen=True)
class SetRecord:
    set_num: str
    name: str
    theme_id: Optional[int]
    num_parts: Optional[int]
    release: Optional[int]


class ProgressBar:
    def __init__(self, total: int, width: int = 30) -> None:
        self.total = max(int(total), 0)
        self.width = max(int(width), 1)
        self.start = time.perf_counter()
        self._finished = False

    def update(self, current: int, label: str = "") -> None:
        current = max(int(current), 0)

        if self.total > 0:
            progress = min(max(current / self.total, 0.0), 1.0)
        else:
            progress = 1.0

        filled = int(self.width * progress)
        bar = "#" * filled + "-" * (self.width - filled)

        elapsed = time.perf_counter() - self.start
        eta = (elapsed / progress - elapsed) if progress > 0 else 0.0

        sys.stdout.write(
            f"\r[{bar}] {int(progress * 100):3d}% | ETA {eta:6.1f}s | {label}"
        )
        sys.stdout.flush()

        if self.total == 0 or current >= self.total:
            self._finish_line()

    def _finish_line(self) -> None:
        if not self._finished:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._finished = True

    def finish(self, label: str = "") -> None:
        if self.total > 0:
            self.update(self.total, label=label)
        else:
            self.update(0, label=label)
        self._finish_line()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


def validate_files() -> None:
    required = [THEMES_CSV, SETS_CSV]
    missing = [p for p in required if not p.is_file()]
    if missing:
        for path in missing:
            LOGGER.error("Missing CSV file: %s", path)
        raise SystemExit(1)


def clean_text(value: Optional[str]) -> str:
    return "" if value is None else str(value).strip()


def get_text(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        text = clean_text(value)
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


def load_csv_rows(
    csv_path: Path,
    *,
    required_columns: set[str],
) -> list[tuple[int, dict[str, str]]]:
    rows: list[tuple[int, dict[str, str]]] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path.name}: missing header row")

        header = {str(name).strip() for name in reader.fieldnames if name is not None}
        missing = sorted(required_columns - header)
        if missing:
            raise ValueError(
                f"{csv_path.name}: missing required columns: {', '.join(missing)}"
            )

        for row_no, row in enumerate(reader, start=2):
            normalized = {
                str(key).strip(): value
                for key, value in row.items()
                if key is not None
            }
            if normalized and any(clean_text(value) for value in normalized.values()):
                rows.append((row_no, normalized))

    return rows


def parse_theme_record(
    row: dict[str, str],
    *,
    source: Path,
    row_no: int,
) -> ThemeRecord:
    theme_id = parse_required_int(
        row.get("id"),
        field_name="id",
        source=source,
        row_no=row_no,
    )
    name = clean_text(row.get("name"))
    if not name:
        raise ValueError("missing required field 'name'")
    parent_id = parse_optional_int(
        row.get("parent_id"),
        field_name="parent_id",
        source=source,
        row_no=row_no,
    )
    return ThemeRecord(theme_id=theme_id, name=name, parent_id=parent_id)


def parse_set_record(
    row: dict[str, str],
    *,
    source: Path,
    row_no: int,
) -> SetRecord:
    set_num = clean_text(row.get("set_num"))
    if not set_num:
        raise ValueError("missing required field 'set_num'")

    name = clean_text(row.get("name"))
    if not name:
        raise ValueError("missing required field 'name'")

    theme_id = parse_optional_int(
        row.get("theme_id"),
        field_name="theme_id",
        source=source,
        row_no=row_no,
    )
    num_parts = parse_optional_int(
        row.get("num_parts"),
        field_name="num_parts",
        source=source,
        row_no=row_no,
    )
    release = parse_optional_int(
        get_text(row, "year", "release"),
        field_name="year",
        source=source,
        row_no=row_no,
    )
    return SetRecord(
        set_num=set_num,
        name=name,
        theme_id=theme_id,
        num_parts=num_parts,
        release=release,
    )


class DatabaseBuilder:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _cleanup_orphaned_sidecars(self) -> None:
        if self.db_path.exists():
            return

        for suffix in ("-wal", "-shm"):
            sidecar = self.db_path.with_suffix(self.db_path.suffix + suffix)
            with suppress(FileNotFoundError):
                sidecar.unlink()

    def connect(self) -> sqlite3.Connection:
        self._cleanup_orphaned_sidecars()

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

            CREATE INDEX IF NOT EXISTS idx_sets_theme_release
            ON sets(theme_id, release);
            """
        )

    def _log_skip(self, csv_path: Path, row_no: int, exc: Exception) -> None:
        LOGGER.warning("[skip] %s:%d: %s", csv_path.name, row_no, exc)

    def _log_warn(self, message: str, *args: object) -> None:
        LOGGER.warning(message, *args)

    def _load_theme_ids(self, conn: sqlite3.Connection) -> set[int]:
        rows = conn.execute("SELECT id FROM themes").fetchall()
        return {int(row[0]) for row in rows}

    def import_themes(self, conn: sqlite3.Connection) -> ImportSummary:
        rows = load_csv_rows(THEMES_CSV, required_columns={"id", "name"})
        total = len(rows)
        progress = ProgressBar(total)

        imported_rows = 0
        skipped_rows = 0
        parsed: dict[int, ThemeRecord] = {}

        for index, (row_no, row) in enumerate(rows, start=1):
            try:
                record = parse_theme_record(row, source=THEMES_CSV, row_no=row_no)
                if record.theme_id in parsed:
                    self._log_warn(
                        "%s: duplicate theme id %s at row %d; last row wins",
                        THEMES_CSV.name,
                        record.theme_id,
                        row_no,
                    )
                parsed[record.theme_id] = record
                imported_rows += 1
            except Exception as exc:
                skipped_rows += 1
                self._log_skip(THEMES_CSV, row_no, exc)

            progress.update(index, THEMES_CSV.name)

        ordered_records = [parsed[theme_id] for theme_id in sorted(parsed)]
        known_theme_ids: set[int]

        with conn:
            cur = conn.cursor()

            cur.executemany(
                """
                INSERT INTO themes (id, name, parent_id)
                VALUES (?, ?, NULL)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    parent_id = NULL
                """,
                ((record.theme_id, record.name) for record in ordered_records),
            )

            known_theme_ids = self._load_theme_ids(conn)

            for record in ordered_records:
                parent_id = record.parent_id
                if parent_id is None:
                    cur.execute(
                        "UPDATE themes SET parent_id = NULL WHERE id = ?",
                        (record.theme_id,),
                    )
                    continue

                if parent_id == record.theme_id:
                    self._log_warn(
                        "%s: theme %s references itself as parent_id; stored as NULL",
                        THEMES_CSV.name,
                        record.theme_id,
                    )
                    cur.execute(
                        "UPDATE themes SET parent_id = NULL WHERE id = ?",
                        (record.theme_id,),
                    )
                    continue

                if parent_id not in known_theme_ids:
                    self._log_warn(
                        "%s: theme %s references missing parent_id %s; stored as NULL",
                        THEMES_CSV.name,
                        record.theme_id,
                        parent_id,
                    )
                    cur.execute(
                        "UPDATE themes SET parent_id = NULL WHERE id = ?",
                        (record.theme_id,),
                    )
                    continue

                cur.execute(
                    "UPDATE themes SET parent_id = ? WHERE id = ?",
                    (parent_id, record.theme_id),
                )

        progress.finish(THEMES_CSV.name)
        return ImportSummary(
            source=THEMES_CSV.name,
            total_rows=total,
            imported_rows=imported_rows,
            skipped_rows=skipped_rows,
        )

    def import_sets(self, conn: sqlite3.Connection) -> ImportSummary:
        rows = load_csv_rows(SETS_CSV, required_columns={"set_num", "name"})
        total = len(rows)
        progress = ProgressBar(total)

        imported_rows = 0
        skipped_rows = 0
        parsed: dict[str, SetRecord] = {}

        known_theme_ids = self._load_theme_ids(conn)

        for index, (row_no, row) in enumerate(rows, start=1):
            try:
                record = parse_set_record(row, source=SETS_CSV, row_no=row_no)

                if record.theme_id is not None and record.theme_id not in known_theme_ids:
                    self._log_warn(
                        "%s: set %s references missing theme_id %s; stored as NULL",
                        SETS_CSV.name,
                        record.set_num,
                        record.theme_id,
                    )
                    record = SetRecord(
                        set_num=record.set_num,
                        name=record.name,
                        theme_id=None,
                        num_parts=record.num_parts,
                        release=record.release,
                    )

                if record.set_num in parsed:
                    self._log_warn(
                        "%s: duplicate set_num %s at row %d; last row wins",
                        SETS_CSV.name,
                        record.set_num,
                        row_no,
                    )

                parsed[record.set_num] = record
                imported_rows += 1
            except Exception as exc:
                skipped_rows += 1
                self._log_skip(SETS_CSV, row_no, exc)

            progress.update(index, SETS_CSV.name)

        ordered_records = [parsed[set_num] for set_num in sorted(parsed)]

        with conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO sets (set_num, name, theme_id, num_parts, release)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(set_num) DO UPDATE SET
                    name = excluded.name,
                    theme_id = excluded.theme_id,
                    num_parts = excluded.num_parts,
                    release = excluded.release
                """,
                (
                    (
                        record.set_num,
                        record.name,
                        record.theme_id,
                        record.num_parts,
                        record.release,
                    )
                    for record in ordered_records
                ),
            )

        progress.finish(SETS_CSV.name)
        return ImportSummary(
            source=SETS_CSV.name,
            total_rows=total,
            imported_rows=imported_rows,
            skipped_rows=skipped_rows,
        )

    def _run_pipeline(self, mode_label: str) -> tuple[ImportSummary, ImportSummary]:
        LOGGER.info("Mode: %s", mode_label)
        with self.connect() as conn:
            self.create_tables(conn)

            action = "Importing" if mode_label == "BUILD" else "Updating"
            LOGGER.info("%s themes", action)
            themes = self.import_themes(conn)

            LOGGER.info("%s sets", action)
            sets = self.import_sets(conn)

        return themes, sets

    def build_database(self) -> tuple[ImportSummary, ImportSummary]:
        return self._run_pipeline("BUILD")

    def update_database(self) -> tuple[ImportSummary, ImportSummary]:
        return self._run_pipeline("UPDATE")


def detect_mode() -> str:
    return "update" if DB_PATH.exists() else "build"


def main() -> None:
    configure_logging()
    validate_files()

    builder = DatabaseBuilder(DB_PATH)
    mode = detect_mode()

    start = time.perf_counter()
    try:
        if mode == "build":
            themes_summary, sets_summary = builder.build_database()
        else:
            themes_summary, sets_summary = builder.update_database()
    except Exception as exc:
        LOGGER.exception("Database operation failed: %s", exc)
        raise SystemExit(1) from exc

    elapsed = time.perf_counter() - start
    LOGGER.info(
        "Imported %d/%d rows from %s (skipped %d)",
        themes_summary.imported_rows,
        themes_summary.total_rows,
        themes_summary.source,
        themes_summary.skipped_rows,
    )
    LOGGER.info(
        "Imported %d/%d rows from %s (skipped %d)",
        sets_summary.imported_rows,
        sets_summary.total_rows,
        sets_summary.source,
        sets_summary.skipped_rows,
    )
    LOGGER.info("Total time: %.2f seconds", elapsed)


if __name__ == "__main__":
    main()