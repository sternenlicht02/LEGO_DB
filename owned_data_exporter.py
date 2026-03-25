from __future__ import annotations

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lego.db"
EXPORT_PATH = BASE_DIR / "owned_export.txt"


def escape_note(text: str) -> str:
    return text.replace("\\", "\\\\").replace("]", "\\]")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
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

        if condition in (1, 2):
            tokens.append(f"{condition}>{set_num}")

        if note:
            tokens.append(f"[{escape_note(note)}]>{set_num}")

    text = " ".join(tokens)

    EXPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Exported to: {EXPORT_PATH}")


if __name__ == "__main__":
    main()