from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import tkinter as tk
from contextlib import suppress
from dataclasses import dataclass, field
from tkinter import messagebox, ttk
from typing import Optional, Final

BASE_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lego.db"
CONFIG_PATH = BASE_DIR / "config.json"
LANG_DIR = BASE_DIR / "language"

WINDOW_TITLE = "LEGO DB"
WINDOW_GEOMETRY = "920x640"
BOOTSTRAP_GEOMETRY = "160x90"
DETAIL_WIDTH = 440
DETAIL_HEIGHT = 300

COND_TAG = {
    "0": "owned",
    "1": "bad",
    "2": "good",
}

COND_LABEL = {
    "0": "0",
    "1": "1",
    "2": "2",
}

LANGUAGE_LABELS = {
    "arz": "مصري عربي",
    "bn": "বাংলা",
    "cmn": "中文(普通话)",
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "hi": "हिन्दी",
    "id": "Bahasa Indonesia",
    "ja": "日本語",
    "ko": "한국어",
    "mr": "मराठी",
    "pt": "Português",
    "ru": "Русский",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "tr": "Türkçe",
    "ur": "اردو",
    "vi": "Tiếng Việt",
    "wuu": "吴语",
    "yue": "粵語",
}

TOKEN_PATTERN = re.compile(
    r"\[(?:\\.|[^\]])*\]>\d+(?:-\d+)?"
    r"|\+[0-9]+(?:-[0-9]+)?"
    r"|\-[0-9]+(?:-[0-9]+)?"
    r"|[012]>[0-9]+(?:-\d+)?"
)

ADD_RE = re.compile(r"^\+[0-9]+(?:-[0-9]+)?$")
REM_RE = re.compile(r"^\-[0-9]+(?:-[0-9]+)?$")
COND_RE = re.compile(r"^[012]>[0-9]+(?:-\d+)?$")
NOTE_RE = re.compile(r"^\[((?:\\.|[^\]])*)\]>([0-9]+(?:-\d+)?)$")
SETNUM_RE = re.compile(r"^([0-9]+)(?:-([0-9]+))?$")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F]")


def load_config() -> dict:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"language": "en"}


def build_language_comment() -> str:
    return ", ".join(
        f"[{code}]{LANGUAGE_LABELS[code]}"
        for code in sorted(LANGUAGE_LABELS)
    )


LANGUAGE_COMMENT = build_language_comment()


def language_options_from_files() -> list[tuple[str, str]]:
    if not LANG_DIR.exists():
        return []

    file_codes = {
        path.stem
        for path in LANG_DIR.glob("*.json")
        if path.is_file()
    }
    return [
        (code, f"[{code}]{LANGUAGE_LABELS.get(code, code)}")
        for code in sorted(file_codes)
    ]


def write_config(language: str) -> None:
    data = {
        "_comment": LANGUAGE_COMMENT,
        "language": language,
    }
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_window_geometry(geometry: str) -> tuple[int, int]:
    size_part = geometry.split("+", 1)[0]
    width_str, height_str = size_part.split("x", 1)
    return int(width_str), int(height_str)


def center_window_on_screen(window: tk.Misc, width: int, height: int) -> None:
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class Lang:
    def __init__(self, code: str = "en") -> None:
        self.code = code
        self.data: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        path = LANG_DIR / f"{self.code}.json"
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.data = data
                return
        except Exception:
            pass

        if self.code != "en":
            fallback = LANG_DIR / "en.json"
            try:
                with fallback.open(encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.data = data
                    return
            except Exception:
                pass

        self.data = {}

    def t(self, key: str) -> str:
        return str(self.data.get(key, key))


lang = Lang("en")


def t(key: str) -> str:
    return lang.t(key)


def setnum_order_sql(column: str) -> str:
    return (
        f"CAST(substr({column}, 1, "
        f"CASE WHEN instr({column}, '-') > 0 "
        f"THEN instr({column}, '-') - 1 ELSE length({column}) END) AS INTEGER), "
        f"CASE WHEN instr({column}, '-') > 0 "
        f"THEN CAST(substr({column}, instr({column}, '-') + 1) AS INTEGER) ELSE 0 END, "
        f"{column}"
    )


def normalize_setnum(set_num: str) -> str:
    match = SETNUM_RE.match(set_num)
    if not match:
        return set_num
    return match.group(1)


def condition_tag(condition: Optional[str]) -> str:
    if condition is None:
        return ""
    return COND_TAG.get(str(condition).strip(), "")


def unescape_note(raw: str) -> str:
    return re.sub(r"\\(.)", r"\1", raw)


@dataclass(frozen=True)
class SetRow:
    set_num: str
    parent_theme: str
    theme: str
    name: str
    num_parts: Optional[int]
    release: Optional[int]
    condition: str = "-"
    note: str = ""

    def main_values(self) -> tuple[object, ...]:
        return (
            self.parent_theme or "",
            self.theme or "",
            self.set_num,
            self.name or "",
            self.num_parts if self.num_parts is not None else "",
            self.release if self.release is not None else "",
            self.condition or "-",
            self.note or "",
        )

    def related_values(self) -> tuple[object, ...]:
        return (
            self.set_num,
            self.name or "",
            self.num_parts if self.num_parts is not None else "",
            self.condition or "-",
        )


@dataclass
class ModificationPlan:
    add: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    conditions: list[tuple[str, int]] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)
    malformed: bool = False

    @property
    def has_tokens(self) -> bool:
        return bool(self.add or self.remove or self.conditions or self.notes)


def parse_modification_text(text: str) -> ModificationPlan:
    plan = ModificationPlan()
    cursor = 0
    matches = list(TOKEN_PATTERN.finditer(text))

    if not matches:
        plan.malformed = True
        return plan

    for match in matches:
        gap = text[cursor:match.start()]
        if gap.strip():
            plan.malformed = True

        token = match.group(0)
        if ADD_RE.fullmatch(token):
            plan.add.append(token[1:])
        elif REM_RE.fullmatch(token):
            plan.remove.append(token[1:])
        elif COND_RE.fullmatch(token):
            plan.conditions.append((token[2:], int(token[0])))
        else:
            note_match = NOTE_RE.fullmatch(token)
            if note_match:
                plan.notes.append((note_match.group(2), unescape_note(note_match.group(1))))
            else:
                plan.malformed = True

        cursor = match.end()

    if text[cursor:].strip():
        plan.malformed = True

    return plan


class HoverTooltip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None) -> None:
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text,
            background="#FFFBEA",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def hide(self, event=None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class LanguageSelectionWindow:
    def __init__(self, parent: tk.Tk, options: list[tuple[str, str]]) -> None:
        self.parent = parent
        self.options = options
        self.codes = [code for code, _ in options]
        self.label_to_code = {label: code for code, label in options}

        self.window = tk.Toplevel(parent)
        self.window.title(WINDOW_TITLE)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._close_default)
        self.window.bind("<Escape>", self._on_escape)

        self.selected = tk.StringVar()
        display_values = [label for _, label in options]

        frame = tk.Frame(self.window, padx=16, pady=14)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Select a language", anchor="w").pack(fill="x", pady=(0, 8))

        self.combo = ttk.Combobox(
            frame,
            textvariable=self.selected,
            values=display_values,
            state="readonly",
            width=42,
        )
        self.combo.pack(fill="x")

        default_display = self._display_for_code("en")
        if default_display is None and display_values:
            default_display = display_values[0]
        if default_display is not None:
            self.combo.set(default_display)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=(16, 0))
        tk.Button(btn_frame, text="confirm", command=self._confirm).pack(side="right")

        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), 360)
        h = max(self.window.winfo_reqheight(), 200)
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.lift()
        self.window.focus_force()
        self.window.grab_set()

    def _display_for_code(self, code: str) -> Optional[str]:
        for c, label in self.options:
            if c == code:
                return label
        return None

    def _save(self, code: str) -> None:
        if code not in self.codes and self.codes:
            code = "en" if "en" in self.codes else self.codes[0]
        write_config(code)

    def _confirm(self) -> None:
        label = self.combo.get().strip()
        code = self.label_to_code.get(label, "en")
        self._save(code)
        self.window.destroy()

    def _close_default(self) -> None:
        self._save("en")
        self.window.destroy()

    def _on_escape(self, event=None) -> str:
        self._close_default()
        return "break"


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
            condition=str(row["condition"] or "-").strip() or "-",
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
            WHERE s.set_num LIKE ?
            ORDER BY {setnum_order_sql('s.set_num')}
            """,
            (f"{prefix}%",),
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
        if condition in {"0", "1", "2"}:
            query += " WHERE o.condition = ?"
            params = (condition,)
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


class LegoDBApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        center_window_on_screen(self.root, *parse_window_geometry(WINDOW_GEOMETRY))

        self.repo = LegoRepository(DB_PATH)
        self.detail_window: Optional[tk.Toplevel] = None
        self.last_selected_tree: Optional[ttk.Treeview] = None
        self.last_search_text = ""
        self._status_after_id: Optional[str] = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        self._close_detail_window()
        if self.repo is not None:
            self.repo.close()
        self.root.destroy()

    def set_status(self, text: str, delay: int | None = 5000) -> None:
        self.status.set(text)

        if self._status_after_id is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._status_after_id)
            self._status_after_id = None

        if delay and delay > 0:
            self._status_after_id = self.root.after(delay, self._clear_status_if_active)

    def _clear_status_if_active(self) -> None:
        self.status.set("")
        self._status_after_id = None

    def clear_tree(self, tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)
        tree.selection_remove(tree.selection())
        tree.yview_moveto(0)

    def clear_all(self) -> None:
        self.clear_tree(self.main_tree)
        self.clear_tree(self.related_tree)

    def _condition_tag(self, condition: Optional[str]) -> str:
        return condition_tag(condition)

    def _populate_main_tree(self, rows: list[SetRow]) -> int:
        for row in rows:
            self.main_tree.insert(
                "",
                "end",
                values=row.main_values(),
                tags=(self._condition_tag(row.condition),),
            )
        return len(rows)

    def _populate_related_tree(self, rows: list[SetRow]) -> int:
        for row in rows:
            self.related_tree.insert(
                "",
                "end",
                values=row.related_values(),
                tags=(self._condition_tag(row.condition),),
            )
        return len(rows)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=6)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(top, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda event: self.search())
        self.search_entry.bind("<Up>", self.move_cursor_start)
        self.search_entry.bind("<Down>", self.move_cursor_end)
        self.search_entry.bind("<Home>", self.move_cursor_start)
        self.search_entry.bind("<End>", self.move_cursor_end)

        tk.Button(top, text=t("search"), command=self.search).pack(side="left", padx=4)
        tk.Button(top, text=t("modify"), command=self.modify_owned_from_entry).pack(side="left", padx=4)
        tk.Button(top, text=t("detail"), command=self.show_detail).pack(side="left", padx=4)
        tk.Button(top, text=t("copy"), command=self.copy_clipboard).pack(side="left", padx=4)

        bottom = tk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        self.status = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)
        self.help_label = tk.Label(bottom, text="?", relief="groove", width=2)
        self.help_label.pack(side="right")
        self.help_tooltip = HoverTooltip(
            self.help_label,
            "+0000-1\n-0000-1\n2>0000-1\n[{}]>0000-1".format(t("note")),
        )

        main_frame = tk.LabelFrame(self.root, text=t("main_info"))
        main_frame.pack(fill="both", expand=True, padx=10, pady=6)

        main_columns = ("parent_theme", "theme", "set_num", "name", "pieces", "year", "condition", "note")
        self.main_tree = self._create_tree_section(
            main_frame,
            columns=main_columns,
            headings={
                "parent_theme": t("parent_theme"),
                "theme": t("theme"),
                "set_num": t("set_num"),
                "name": t("name"),
                "pieces": t("pieces"),
                "year": t("release"),
                "condition": t("condition"),
                "note": t("note"),
            },
            widths={
                "parent_theme": 90,
                "theme": 110,
                "set_num": 80,
                "name": 260,
                "pieces": 50,
                "year": 50,
                "condition": 55,
                "note": 100,
            },
            stretch={"name", "note"},
            height=12,
        )
        self.main_tree.tag_configure("owned", background="#EAF6FF")
        self.main_tree.tag_configure("bad", background="#ffe4e6")
        self.main_tree.tag_configure("good", background="#eaffea")

        related_frame = tk.LabelFrame(self.root, text=t("sub_info"))
        related_frame.pack(fill="both", expand=True, padx=10, pady=6)

        related_columns = ("set_num", "name", "pieces", "condition")
        self.related_tree = self._create_tree_section(
            related_frame,
            columns=related_columns,
            headings={
                "set_num": t("set_num"),
                "name": t("name"),
                "pieces": t("pieces"),
                "condition": t("condition"),
            },
            widths={
                "set_num": 90,
                "name": 360,
                "pieces": 90,
                "condition": 80,
            },
            stretch={"name"},
            height=8,
        )
        self.related_tree.tag_configure("owned", background="#EAF6FF")
        self.related_tree.tag_configure("bad", background="#ffe4e6")
        self.related_tree.tag_configure("good", background="#eaffea")

        tk.Label(self.root, text=t("condition_desc"), font=("TkDefaultFont", 8)).pack(pady=(0, 6))

        self.main_tree.bind("<<TreeviewSelect>>", self.on_main_select)
        self.related_tree.bind("<<TreeviewSelect>>", self.on_related_select)
        self.main_tree.bind("<Double-1>", lambda event: self.show_detail())
        self.related_tree.bind("<Double-1>", lambda event: self.show_detail())

    def _create_tree_section(
        self,
        parent: tk.Widget,
        *,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
        stretch: set[str],
        height: int,
    ) -> ttk.Treeview:
        container = tk.Frame(parent)
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
        vsb = tk.Scrollbar(container, orient="vertical", command=tree.yview)
        hsb = tk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(
                col,
                anchor="center",
                width=widths[col],
                stretch=(col in stretch),
            )

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        return tree

    def search(self) -> None:
        text = self.search_var.get().strip()
        self.last_search_text = text
        count = self._search_text(text)
        self.set_status(f"{count}{t('result_count')}", delay=0)

    def _search_text(self, text: str) -> int:
        if self.repo is None:
            return 0

        if not text:
            return self.search_set("")

        head = text.split(maxsplit=1)[0].casefold()
        if head in {"owned", "보유"}:
            parts = text.split()
            condition = parts[1] if len(parts) > 1 else None
            return self.search_owned(condition)

        return self.search_set(text)

    def search_set(self, prefix: str) -> int:
        if self.repo is None:
            return 0
        self.clear_all()
        rows = self.repo.search_sets(prefix)
        return self._populate_main_tree(rows)

    def search_owned(self, condition: Optional[str] = None) -> int:
        if self.repo is None:
            return 0
        self.clear_all()
        rows = self.repo.search_owned(condition)
        return self._populate_main_tree(rows)

    def move_cursor_start(self, event=None):
        self.search_entry.icursor(0)
        return "break"

    def move_cursor_end(self, event=None):
        self.search_entry.icursor(tk.END)
        return "break"
    
    def _focus_search_entry(self) -> None:
        if self.search_entry.winfo_exists():
            self.search_entry.focus_force()
            self.search_entry.icursor(0)
            self.search_entry.selection_range(0, tk.END)

    def _tree_setnum(self, tree: ttk.Treeview) -> Optional[str]:
        selection = tree.selection()
        if not selection:
            return None
        values = tree.item(selection[0]).get("values", [])
        if not values:
            return None
        if tree is self.main_tree:
            return str(values[2])
        if tree is self.related_tree:
            return str(values[0])
        return None

    def _selected_tree_and_set(self) -> tuple[Optional[ttk.Treeview], Optional[str]]:
        candidates: list[ttk.Treeview] = []
        if self.last_selected_tree is not None:
            candidates.append(self.last_selected_tree)
        candidates.extend([self.main_tree, self.related_tree])

        seen: set[int] = set()
        for tree in candidates:
            identity = id(tree)
            if identity in seen:
                continue
            seen.add(identity)
            set_num = self._tree_setnum(tree)
            if set_num is not None:
                return tree, set_num
        return None, None

    def get_selected_set(self) -> Optional[str]:
        _, set_num = self._selected_tree_and_set()
        return set_num

    def on_main_select(self, event=None) -> None:
        self.last_selected_tree = self.main_tree
        set_num = self._tree_setnum(self.main_tree)
        if not set_num:
            self.clear_tree(self.related_tree)
            return
        self.update_related(set_num)

    def on_related_select(self, event=None) -> None:
        self.last_selected_tree = self.related_tree

    def update_related(self, set_num: str) -> None:
        if self.repo is None:
            return
        self.clear_tree(self.related_tree)
        rows = self.repo.related_sets(set_num)
        self._populate_related_tree(rows)

    def center_window(self, win: tk.Toplevel, width: int = DETAIL_WIDTH, height: int = DETAIL_HEIGHT) -> None:
        self.root.update_idletasks()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        x = rx + (rw // 2) - (width // 2)
        y = ry + (rh // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

    def show_detail(self) -> None:
        if self.repo is None:
            return

        set_num = self.get_selected_set()
        if not set_num:
            self.set_status(t("no_selection"))
            return

        info = self.repo.fetch_set(set_num)
        if info is None:
            self.set_status(t("no_data"))
            return

        win = tk.Toplevel(self.root)
        self.detail_window = win
        win.withdraw()

        win.title(t("detail"))
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self._close_detail_window)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True)
        content = tk.Frame(frame, padx=16, pady=10)
        content.pack(fill="both", expand=True)

        labels = (
            ("set_num", info.set_num),
            ("parent_theme", info.parent_theme),
            ("theme", info.theme),
            ("name", info.name),
            ("pieces", info.num_parts if info.num_parts is not None else ""),
            ("release", info.release if info.release is not None else ""),
            ("condition", info.condition),
            ("note", info.note or "-"),
        )
        for key, value in labels:
            tk.Label(content, text=f"{t(key)}: {value}", anchor="w", justify="left").pack(fill="x", pady=2)

        normalize_var = tk.BooleanVar(value=True)
        tk.Checkbutton(content, text=t("normalize"), variable=normalize_var).pack(pady=(6, 0))

        def copy() -> None:
            text = self._format_copy_text(info, normalize_var.get())
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status(t("copied"))

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)

        center_frame = tk.Frame(btn_frame)
        center_frame.pack(anchor="center")

        tk.Button(
            center_frame,
            text=t("copy"),
            command=copy,
            padx=10,
            pady=6
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            center_frame,
            text=t("close"),
            command=self._close_detail_window,
            padx=10,
            pady=6
        ).pack(side="left")

        win.update_idletasks()
        self.center_window(win)
        win.deiconify()
        win.lift()
        win.focus_force()
        win.grab_set()

    def _close_detail_window(self) -> None:
        try:
            if self.detail_window is not None and self.detail_window.winfo_exists():
                self.detail_window.destroy()
        finally:
            self.detail_window = None

    def _format_copy_text(self, info: SetRow, normalize: bool) -> str:
        set_num = normalize_setnum(info.set_num) if normalize else info.set_num
        parent_theme = info.parent_theme or ""
        theme = info.theme or ""
        pieces = "" if info.num_parts is None else str(info.num_parts)
        year = "" if info.release is None else str(info.release)
        return f"{parent_theme} {theme} {set_num} {info.name}, {pieces}pc, {year}".strip()

    def copy_clipboard(self) -> None:
        set_num = self.get_selected_set()
        if not set_num:
            self.set_status(t("no_selection"))
            return
        self.copy_detail(set_num)

    def copy_detail(self, set_num: str) -> None:
        if self.repo is None:
            return
        info = self.repo.fetch_set(set_num)
        if info is None:
            self.set_status(t("no_data"))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_copy_text(info, True))
        self.set_status(t("copied"))

    def modify_owned_from_entry(self) -> None:
        text = self.search_var.get().strip()
        if not text or CONTROL_CHAR_RE.search(text):
            self.set_status(t("modify_fail"))
            self.search_var.set("")
            self.search_entry.focus()
            return
        self.modify_owned(text)

    def modify_owned(self, text: str) -> None:
        if self.repo is None:
            return

        plan = parse_modification_text(text)
        if not plan.has_tokens or plan.malformed:
            self.set_status(t("modify_fail"))
            self.search_var.set("")
            self.search_entry.focus()
            return

        changed = False
        partial = False

        try:
            self.repo.conn.execute("BEGIN")

            for set_num in plan.add:
                if not SETNUM_RE.fullmatch(set_num):
                    partial = True
                    continue
                if not self.repo.has_set(set_num):
                    partial = True
                    continue
                if self.repo.add_owned(set_num):
                    changed = True

            for set_num in plan.remove:
                if not SETNUM_RE.fullmatch(set_num):
                    partial = True
                    continue
                if self.repo.remove_owned(set_num):
                    changed = True
                else:
                    partial = True

            for set_num, condition in plan.conditions:
                if not SETNUM_RE.fullmatch(set_num):
                    partial = True
                    continue
                if self.repo.update_condition(set_num, condition):
                    changed = True
                else:
                    partial = True

            for set_num, note_text in plan.notes:
                if not SETNUM_RE.fullmatch(set_num):
                    partial = True
                    continue
                if self.repo.update_note(set_num, note_text):
                    changed = True
                else:
                    partial = True

            self.repo.conn.commit()
        except sqlite3.DatabaseError as exc:
            self.repo.conn.rollback()
            self.set_status(f"{t('modify_fail')}: {exc}")
            self.search_var.set("")
            self.search_entry.focus()
            return

        if changed and partial:
            self.set_status(t("modify_partial"))
        elif changed:
            self.set_status(t("modify_done"))
        else:
            self.set_status(t("modify_fail"))

        self.search_var.set("")
        self.search_entry.focus()
        self._refresh_after_modification()

    def _refresh_after_modification(self) -> None:
        self._search_text(self.last_search_text)


def main() -> None:
    global lang

    root = tk.Tk()
    try:
        root.attributes("-alpha", 0)

        if not CONFIG_PATH.exists():
            options = language_options_from_files()
            if options:
                selector = LanguageSelectionWindow(root, options)
                root.wait_window(selector.window)
            else:
                write_config("en")

        config = load_config()
        lang = Lang(str(config.get("language", "en")))
        app = LegoDBApp(root)

        root.update_idletasks()
        root.attributes("-alpha", 1)
        root.deiconify()
        root.lift()
        root.after_idle(root.lift)
        root.after(0, app._focus_search_entry)

    except Exception:
        with suppress(Exception):
            root.destroy()
        raise

    app.start()


if __name__ == "__main__":
    main()
