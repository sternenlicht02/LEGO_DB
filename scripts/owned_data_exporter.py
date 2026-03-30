from __future__ import annotations

import sys
import csv
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lego_db.core import DB_PATH, SetRow
from lego_db.repository import LegoRepository
from lego_db.i18n import load_config, set_language, t

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_TXT = PROJECT_ROOT / "owned_export.txt"
EXPORT_CSV = PROJECT_ROOT / "owned_export.csv"


def escape_note(text: str) -> str:
    return text.replace("\\", "\\\\").replace("]", "\\]")


def export_txt(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT set_num, condition, COALESCE(note, '') AS note
        FROM owned_sets
        ORDER BY set_num
        """
    ).fetchall()

    tokens: list[str] = []

    for row in rows:
        set_num = row["set_num"]
        condition = row["condition"]
        note = row["note"] or ""

        tokens.append(f"+{set_num}")

        cond_valid = condition in (1, 2)
        note_valid = bool(note)

        if cond_valid and note_valid:
            tokens.append(f"{condition}[{escape_note(note)}]>{set_num}")
        elif cond_valid:
            tokens.append(f"{condition}>{set_num}")
        elif note_valid:
            tokens.append(f"[{escape_note(note)}]>{set_num}")

    text = " ".join(tokens)
    EXPORT_TXT.write_text(text, encoding="utf-8")


def export_csv(repo: LegoRepository) -> None:
    rows: list[SetRow] = repo.search_owned()

    headers = [
        t("parent_theme"),
        t("theme"),
        t("set_num"),
        t("name"),
        t("pieces"),
        t("release"),
        t("condition"),
        t("note"),
    ]

    with open(EXPORT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            writer.writerow(row.main_values())


def main() -> None:
    config = load_config()
    set_language(str(config.get("language", "en")))

    conn = sqlite3.connect(DB_PATH)
    repo = LegoRepository(DB_PATH)

    try:
        export_txt(conn)
        export_csv(repo)

    finally:
        conn.close()
        repo.close()

    print(f"Exported TXT: {EXPORT_TXT}")
    print(f"Exported CSV: {EXPORT_CSV}")


if __name__ == "__main__":
    main()