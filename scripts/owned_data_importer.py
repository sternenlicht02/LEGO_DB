from __future__ import annotations

import sys
import sqlite3
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "lego.db"
INPUT_PATH = PROJECT_ROOT / "owned_export.txt"

TOKEN_PATTERN = re.compile(
    r"\[(?:\\.|[^\]])*\]>\d+(?:-\d+)?"
    r"|\+[0-9]+(?:-[0-9]+)?"
    r"|[012]>[0-9]+(?:-\d+)?"
)

NOTE_RE = re.compile(r"^\[((?:\\.|[^\]])*)\]>([0-9\-]+)$")


def parse_tokens(text: str):
    for match in TOKEN_PATTERN.finditer(text):
        token = match.group(0)

        if token.startswith("+"):
            yield ("add", token[1:], None)

        elif token[0] in "012":
            yield ("condition", token[2:], int(token[0]))

        else:
            m = NOTE_RE.match(token)
            if m:
                yield ("note", m.group(2), m.group(1))


def import_owned():
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)

    text = INPUT_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # 핵심: 초기화
    conn.execute("DELETE FROM owned_sets")

    for kind, set_num, value in parse_tokens(text):

        if kind == "add":
            conn.execute(
                "INSERT OR IGNORE INTO owned_sets(set_num, condition, note) VALUES (?, 0, NULL)",
                (set_num,),
            )

        elif kind == "condition":
            conn.execute(
                """
                INSERT INTO owned_sets(set_num, condition)
                VALUES (?, ?)
                ON CONFLICT(set_num) DO UPDATE SET condition=excluded.condition
                """,
                (set_num, value),
            )

        elif kind == "note":
            conn.execute(
                """
                INSERT INTO owned_sets(set_num, note)
                VALUES (?, ?)
                ON CONFLICT(set_num) DO UPDATE SET note=excluded.note
                """,
                (set_num, value),
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    import_owned()
    print("Import complete")