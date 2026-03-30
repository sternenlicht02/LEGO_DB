from __future__ import annotations

import pathlib
import sqlite3
from contextlib import suppress
from tkinter import messagebox
from typing import Final, Optional

from lego_db.core import SetRow, WINDOW_TITLE, escape_like_pattern, setnum_order_sql


class LegoRepository:
    _SET_COLUMNS_SQL: Final[str] = """
        s.set_num AS set_num,
        COALESCE(pt.name, '') AS parent_theme,
        COALESCE(t.name, '') AS theme,
        COALESCE(s.name, '') AS name,
        s.num_parts AS num_parts,
        s.release AS release,
        COALESCE(o.condition, '-') AS condition,
        COALESCE(o.note, '') AS note
    """

    def __init__(self, db_path: pathlib.Path) -> None:
        self.db_path = db_path
        self.conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            messagebox.showerror(
                WINDOW_TITLE,
                f"Database file not found:\n{self.db_path}",
            )
            raise FileNotFoundError(self.db_path)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 3000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        return conn

    def close(self) -> None:
        with suppress(Exception):
            self.conn.close()

    @staticmethod
    def _row_to_set(row: sqlite3.Row) -> SetRow:
        return SetRow(
            set_num=str(row["set_num"]),
            parent_theme=str(row["parent_theme"] or ""),
            theme=str(row["theme"] or ""),
            name=str(row["name"] or ""),
            num_parts=row["num_parts"],
            release=row["release"],
            condition="-" if row["condition"] is None else str(row["condition"]),
            note=str(row["note"] or ""),
        )

    def _fetch_set_rows(self, query: str, params: tuple[object, ...] = ()) -> list[SetRow]:
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_set(row) for row in rows]

    def has_set(self, set_num: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sets WHERE set_num = ?",
            (set_num,),
        ).fetchone()
        return row is not None

    def fetch_set(self, set_num: str) -> Optional[SetRow]:
        row = self.conn.execute(
            f"""
            SELECT
                {self._SET_COLUMNS_SQL}
            FROM sets s
            LEFT JOIN themes t ON s.theme_id = t.id
            LEFT JOIN themes pt ON t.parent_id = pt.id
            LEFT JOIN owned_sets o ON o.set_num = s.set_num
            WHERE s.set_num = ?
            """,
            (set_num,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_set(row)

    def search_sets(self, prefix: str) -> list[SetRow]:
        return self._fetch_set_rows(
            f"""
            SELECT
                {self._SET_COLUMNS_SQL}
            FROM sets s
            LEFT JOIN themes t ON s.theme_id = t.id
            LEFT JOIN themes pt ON t.parent_id = pt.id
            LEFT JOIN owned_sets o ON o.set_num = s.set_num
            WHERE s.set_num LIKE ? ESCAPE '\\'
            ORDER BY {setnum_order_sql('s.set_num')}
            """,
            (f"{escape_like_pattern(prefix)}%",),
        )

    def search_owned(self, condition: Optional[str] = None) -> list[SetRow]:
        query = f"""
            SELECT
                {self._SET_COLUMNS_SQL}
            FROM owned_sets o
            JOIN sets s ON o.set_num = s.set_num
            LEFT JOIN themes t ON s.theme_id = t.id
            LEFT JOIN themes pt ON t.parent_id = pt.id
        """
        params: tuple[object, ...] = ()
        if condition is None:
            pass
        elif condition in {"0", "1", "2"}:
            query += " WHERE o.condition = ?"
            params = (condition,)
        else:
            return []
        query += f" ORDER BY {setnum_order_sql('s.set_num')}"
        return self._fetch_set_rows(query, params)

    def related_sets(self, set_num: str) -> list[SetRow]:
        source = self.conn.execute(
            "SELECT theme_id, release FROM sets WHERE set_num = ?",
            (set_num,),
        ).fetchone()
        if source is None:
            return []

        theme_id, release = source["theme_id"], source["release"]
        if theme_id is None or release is None:
            return []

        return self._fetch_set_rows(
            f"""
            SELECT
                {self._SET_COLUMNS_SQL}
            FROM sets s
            LEFT JOIN themes t ON s.theme_id = t.id
            LEFT JOIN themes pt ON t.parent_id = pt.id
            LEFT JOIN owned_sets o ON o.set_num = s.set_num
            WHERE s.theme_id = ? AND s.release = ? AND s.set_num != ?
            ORDER BY s.num_parts DESC, {setnum_order_sql('s.set_num')}
            """,
            (theme_id, release, set_num),
        )
    
    def is_owned(self, set_num: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM owned_sets WHERE set_num = ?",
            (set_num,),
        ).fetchone()
        return row is not None

    def add_owned(self, set_num: str) -> bool:
        if not self.has_set(set_num):
            return False
        if self.conn.execute(
            "SELECT 1 FROM owned_sets WHERE set_num = ?",
            (set_num,),
        ).fetchone() is not None:
            return False
        self.conn.execute(
            "INSERT INTO owned_sets(set_num, condition, note) VALUES (?, 0, NULL)",
            (set_num,),
        )
        return True

    def remove_owned(self, set_num: str) -> bool:
        result = self.conn.execute(
            "DELETE FROM owned_sets WHERE set_num = ?",
            (set_num,),
        )
        return result.rowcount > 0

    def update_condition(self, set_num: str, condition: int) -> bool:
        result = self.conn.execute(
            "UPDATE owned_sets SET condition = ? WHERE set_num = ?",
            (condition, set_num),
        )
        return result.rowcount > 0

    def update_note(self, set_num: str, note: str) -> bool:
        result = self.conn.execute(
            "UPDATE owned_sets SET note = ? WHERE set_num = ?",
            (note, set_num),
        )
        return result.rowcount > 0