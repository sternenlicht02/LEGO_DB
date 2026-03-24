import sqlite3
import tkinter as tk
from tkinter import ttk
import re
import pathlib
import json
import time

BASE_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lego.db"

# =========================
# Language Loader
# =========================
def load_config():
    path = BASE_DIR / "config.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"language": "ko"}

class Lang:
    def __init__(self, code="ko"):
        self.code = code
        self.data = {}
        self.load()

    def load(self):
        try:
            with open(BASE_DIR / "language" / f"{self.code}.json", encoding="utf-8") as f:
                self.data = json.load(f)
        except:
            self.data = {}

    def t(self, key):
        return self.data.get(key, key)

config = load_config()
lang = Lang(config.get("language", "ko"))

def t(key):
    return lang.t(key)

# =========================
# Tooltip
# =========================
class HoverTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#FFFBEA",
                 relief="solid", borderwidth=1).pack()

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

class LegoDBApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LEGO DB")
        self.root.geometry("900x600")

        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.detail_window = None
        self.last_selected_tree = None

        self.build_ui()

    # =========================
    # Status
    # =========================
    def set_status(self, text, delay=5000):
        self.status.set(text)
        self.root.after(delay, lambda: self.status.set(""))

    def build_ui(self):

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=6)

        self.search_var = tk.StringVar()

        self.search_entry = tk.Entry(top, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)

        self.search_entry.bind("<Up>", self.move_cursor_start)
        self.search_entry.bind("<Down>", self.move_cursor_end)
        self.search_entry.bind("<Home>", self.move_cursor_start)
        self.search_entry.bind("<End>", self.move_cursor_end)
        self.search_entry.bind("<Return>", lambda event: self.search())
        self.search_entry.focus_set()

        tk.Button(top, text=t("search"), command=self.search).pack(side="left", padx=4)
        tk.Button(top, text=t("modify"), command=self.modify_owned_from_entry).pack(side="left", padx=4)
        tk.Button(top, text=t("detail"), command=self.show_detail).pack(side="left", padx=4)
        tk.Button(top, text=t("copy"), command=self.copy_clipboard).pack(side="left")

        self.status = tk.StringVar()

        status_frame = tk.Frame(self.root)
        status_frame.pack(fill="x", padx=10)

        tk.Label(status_frame, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)

        help_btn = tk.Label(status_frame, text="?", relief="ridge", width=3)
        help_btn.pack(side="right")

        HoverTooltip(help_btn,
            "+0000-1\n-0000-1\n2>0000-1\n[{}]>0000-1".format(t("note"))
        )

        main_frame = tk.LabelFrame(self.root, text=t("main_info"))
        main_frame.pack(fill="both", expand=True, padx=10, pady=6)

        cols = ("parent_theme", "theme", "set_num", "name", "pieces", "release_year", "condition", "note")

        self.main_tree = ttk.Treeview(main_frame, columns=cols, show="headings", height=12)

        widths = {
            "parent_theme": 90,
            "theme": 110,
            "set_num": 80,
            "name": 260,
            "pieces": 50,
            "release_year": 50,
            "condition": 55,
            "note": 100
        }

        headers = {
            "parent_theme": t("parent_theme"),
            "theme": t("theme"),
            "set_num": t("set_num"),
            "name": t("name"),
            "pieces": t("pieces"),
            "release_year": t("release_year"),
            "condition": t("condition"),
            "note": t("note")
        }

        for c in cols:
            self.main_tree.heading(c, text=headers[c])
            self.main_tree.column(c, anchor="center", width=widths[c])

        self.main_tree.pack(fill="both", expand=True)

        self.main_tree.tag_configure("owned", background="#EAF6FF")
        self.main_tree.tag_configure("bad", background="#ffe4e6")
        self.main_tree.tag_configure("good", background="#eaffea")

        related_frame = tk.LabelFrame(self.root, text=t("sub_info"))
        related_frame.pack(fill="both", expand=True, padx=10, pady=6)

        cols2 = ("set_num", "name", "pieces", "condition")

        self.related_tree = ttk.Treeview(related_frame, columns=cols2, show="headings", height=8)

        headers2 = {
            "set_num": t("set_num"),
            "name": t("name"),
            "pieces": t("pieces"),
            "condition": t("condition")
        }

        widths2 = {
            "set_num": 90,
            "name": 360,
            "pieces": 90,
            "condition": 80
        }

        for c in cols2:
            self.related_tree.heading(c, text=headers2[c])
            self.related_tree.column(c, anchor="center", width=widths2[c])

        self.related_tree.pack(fill="both", expand=True)

        self.related_tree.tag_configure("owned", background="#EAF6FF")
        self.related_tree.tag_configure("bad", background="#ffe4e6")
        self.related_tree.tag_configure("good", background="#eaffea")

        bottom = tk.Label(self.root, text=t("condition_desc"), font=("TkDefaultFont", 8))
        bottom.pack(pady=6)

        self.main_tree.bind("<<TreeviewSelect>>", self.on_main_select)
        self.related_tree.bind("<<TreeviewSelect>>", self.on_related_select)

    def get_note(self, set_num):
        cur = self.conn.cursor()
        r = cur.execute("SELECT note FROM owned_sets WHERE set_num=?", (set_num,)).fetchone()
        return r[0] if r and r[0] else ""

    # =========================
    # SEARCH
    # =========================
    def search(self):
        start = time.time()
        self.set_status(t("searching"))
        text = self.search_var.get().strip()

        if text.lower().startswith(("owned", "보유")):
            parts = text.split()
            cond = parts[1] if len(parts) > 1 else None
            n = self.search_owned(cond)
        else:
            n = self.search_set(text)

        elapsed = time.time() - start

        if elapsed > 0.5:
            self.set_status(f"{n}{t('result_count')}")
        else:
            self.set_status(f"{n}{t('result_count')}")

    def search_set(self, kwd):
        self.clear_all()
        cur = self.conn.cursor()
        rows = cur.execute(
            """
            SELECT
                s.set_num,
                pt.name,
                t.name,
                s.name,
                s.num_parts,
                s.release_year
            FROM sets s
            LEFT JOIN themes t ON s.theme_id=t.id
            LEFT JOIN themes pt ON t.parent_id=pt.id
            WHERE s.set_num LIKE ?
            ORDER BY CAST(substr(s.set_num,1,instr(s.set_num,'-')-1) AS INTEGER)
            """,
            (kwd + "%",),
        ).fetchall()

        for r in rows:
            cond = str(self.get_condition(r[0])).strip()
            note = self.get_note(r[0])

            tag = ""
            if cond == "0":
                tag = "owned"
            elif cond == "1":
                tag = "bad"
            elif cond == "2":
                tag = "good"

            self.main_tree.insert("", "end",
                values=(r[1], r[2], r[0], r[3], r[4], r[5], cond, note),
                tags=(tag,)
            )

        return len(rows)

    def search_owned(self, cond_filter=None):
        self.clear_all()
        cur = self.conn.cursor()
        query = """
            SELECT
                s.set_num,
                o.condition,
                pt.name,
                t.name,
                s.name,
                s.num_parts,
                s.release_year,
                o.note
            FROM owned_sets o
            JOIN sets s ON o.set_num=s.set_num
            LEFT JOIN themes t ON s.theme_id=t.id
            LEFT JOIN themes pt ON t.parent_id=pt.id
        """

        params = ()

        if cond_filter in ("0", "1", "2"):
            query += " WHERE o.condition=?"
            params = (cond_filter,)

        query += " ORDER BY CAST(substr(s.set_num,1,instr(s.set_num,'-')-1) AS INTEGER)"

        rows = cur.execute(query, params).fetchall()

        for r in rows:
            cond = str(r[1]).strip()

            tag = ""
            if cond == "0":
                tag = "owned"
            elif cond == "1":
                tag = "bad"
            elif cond == "2":
                tag = "good"

            self.main_tree.insert("", "end",
                values=(r[2], r[3], r[0], r[4], r[5], r[6], r[1], r[7] or ""),
                tags=(tag,)
            )

        return len(rows)
    
    def move_cursor_start(self, event=None):
        self.search_entry.icursor(0)
        return "break"

    def move_cursor_end(self, event=None):
        self.search_entry.icursor(tk.END)
        return "break"

    # =========================
    # DETAIL
    # =========================
    def show_detail(self):
        set_num = self.get_selected_set()

        if not set_num:
            self.set_status(t("no_selection"))
            return

        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.focus()
            return

        cur = self.conn.cursor()

        r = cur.execute(
            """
            SELECT
                s.set_num,
                pt.name,
                t.name,
                s.name,
                s.num_parts,
                s.release_year
            FROM sets s
            LEFT JOIN themes t ON s.theme_id=t.id
            LEFT JOIN themes pt ON t.parent_id=pt.id
            WHERE s.set_num=?
            """,
            (set_num,),
        ).fetchone()

        if not r:
            self.set_status(t("no_data"))
            return

        cond = self.get_condition(set_num)
        note = self.get_note(set_num) or "-"

        win = tk.Toplevel(self.root)
        self.detail_window = win
        win.title(t("detail"))

        self.center_window(win)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True)

        content = tk.Frame(frame, padx=16, pady=10)
        content.pack(fill="both", expand=True)

        labels = (
            ("set_num", r[0]),
            ("parent_theme", r[1] or ""),
            ("theme", r[2] or ""),
            ("name", r[3] or ""),
            ("pieces", r[4] or ""),
            ("release_year", r[5] or ""),
            ("condition", cond),
            ("note", note),
        )

        for k, v in labels:
            tk.Label(frame, text=f"{t(k)}: {v}", anchor="w").pack(fill="x", pady=2)

        normalize_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text=t("normalize"), variable=normalize_var).pack()

        def copy():
            cur2 = self.conn.cursor()
            r2 = cur2.execute(
                """
                SELECT
                    pt.name,
                    t.name,
                    s.set_num,
                    s.name,
                    s.num_parts,
                    s.release_year
                FROM sets s
                LEFT JOIN themes t ON s.theme_id=t.id
                LEFT JOIN themes pt ON t.parent_id=pt.id
                WHERE s.set_num=?
                """,
                (set_num,),
            ).fetchone()

            if not r2:
                return

            parent_theme = r2[0] or ""
            theme = r2[1] or ""

            s = r2[2]
            if normalize_var.get():
                s = self.normalize_setnum(s)

            text = f"{parent_theme} {theme} {s} {r2[3]}, {r2[4]}pc, {r2[5]}"

            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status(t("copied"))

        btn_frame = tk.Frame(frame)
        btn_frame.pack(side="bottom", pady=10)
        tk.Button(btn_frame, text=t("copy"), command=copy, padx=10, pady=6).pack()

    # =========================
    # OTHERS
    # =========================
    def clear_tree(self, tree):
        for row in tree.get_children():
            tree.delete(row)

    def clear_all(self):
        self.clear_tree(self.main_tree)
        self.clear_tree(self.related_tree)

    def get_selected_set(self):
        tree = self.last_selected_tree

        if tree is None:
            return None

        sel = tree.selection()
        if not sel:
            return None

        values = tree.item(sel)["values"]

        if tree == self.main_tree:
            return values[2]

        return values[0]

    def get_condition(self, set_num):
        cur = self.conn.cursor()

        r = cur.execute(
            "SELECT condition FROM owned_sets WHERE set_num=?",
            (set_num,),
        ).fetchone()

        if not r:
            return "-"

        return str(r[0]).strip()

    def normalize_setnum(self, set_num):

        m = re.match(r"[0-9]+", set_num)
        if not m:
            return set_num

        return m.group()

    def on_main_select(self, event):
        self.last_selected_tree = self.main_tree
        set_num = self.get_selected_set()

        if not set_num:
            self.clear_tree(self.related_tree)
            return

        self.update_related(set_num)

    def on_related_select(self, event):
        self.last_selected_tree = self.related_tree

    def update_related(self, set_num):
        self.clear_tree(self.related_tree)
        cur = self.conn.cursor()

        row = cur.execute(
            "SELECT theme_id, release_year FROM sets WHERE set_num=?",
            (set_num,),
        ).fetchone()

        if not row:
            return

        theme, year = row

        rows = cur.execute(
            """
            SELECT set_num, name, num_parts
            FROM sets
            WHERE theme_id=? AND release_year=? AND set_num!=?
            ORDER BY num_parts DESC
            """,
            (theme, year, set_num),
        ).fetchall()

        for r in rows:
            cond = str(self.get_condition(r[0])).strip()

            tag = ""
            if cond == "0":
                tag = "owned"
            elif cond == "1":
                tag = "bad"
            elif cond == "2":
                tag = "good"

            self.related_tree.insert("", "end",
                values=(r[0], r[1], r[2], cond),
                tags=(tag,)
            )

    def center_window(self, win, width=420, height=260):

        self.root.update_idletasks()

        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()

        x = rx + (rw // 2) - (width // 2)
        y = ry + (rh // 2) - (height // 2)

        win.geometry(f"{width}x{height}+{x}+{y}")

    # =========================
    # COPY
    # =========================
    def copy_clipboard(self):
        set_num = self.get_selected_set()

        if not set_num:
            self.set_status(t("no_selection"))
            return

        self.copy_detail(set_num)

    def copy_detail(self, set_num):
        cur = self.conn.cursor()

        r = cur.execute(
            """
            SELECT
                pt.name,
                t.name,
                s.set_num,
                s.name,
                s.num_parts,
                s.release_year
            FROM sets s
            LEFT JOIN themes t ON s.theme_id=t.id
            LEFT JOIN themes pt ON t.parent_id=pt.id
            WHERE s.set_num=?
            """,
            (set_num,),
        ).fetchone()

        if not r:
            return

        parent_theme = r[0] or ""
        theme = r[1] or ""

        s = r[2]

        text = f"{parent_theme} {theme} {s} {r[3]}, {r[4]}pc, {r[5]}"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status(t("copied"))

    # =========================
    # MODIFY
    # =========================
    def modify_owned_from_entry(self):

        text = self.search_var.get().strip()

        if not re.fullmatch(r"[^\x00-\x1F]+", text):
            self.set_status(t("modify_fail"))
            self.search_var.set("")
            self.search_entry.focus()
            return

        self.modify_owned(text)

    def modify_owned(self, text):

        token_pattern = re.compile(
            r"\[(?:\\.|[^\]])*\]>\d+(?:-\d+)?"
            r"|\+[0-9]+(?:-[0-9]+)?"
            r"|\-[0-9]+(?:-[0-9]+)?"
            r"|[012]>[0-9]+(?:-[0-9]+)?"
        )

        tokens = token_pattern.findall(text)

        add = []
        remove = []
        cond = []
        notes = []

        add_re = re.compile(r"^\+[0-9]+(?:-[0-9]+)?$")
        rem_re = re.compile(r"^\-[0-9]+(?:-[0-9]+)?$")
        cond_re = re.compile(r"^[012]>[0-9]+(?:-[0-9]+)?$")
        note_re = re.compile(r"^\[((?:\\.|[^\]])*)\]>([0-9]+(?:-[0-9]+)?)$")

        def _unescape_note(text):
            return re.sub(r"\\(.)", r"\1", text)

        for tkn in tokens:

            if add_re.match(tkn):
                add.append(tkn[1:])
                continue

            if rem_re.match(tkn):
                remove.append(tkn[1:])
                continue

            if cond_re.match(tkn):
                c = int(tkn[0])
                s = tkn[2:]
                cond.append((s, c))
                continue

            m = note_re.match(tkn)
            if m:
                note_text = _unescape_note(m.group(1))
                set_num = m.group(2)
                notes.append((set_num, note_text))
                continue

        cur = self.conn.cursor()

        changed = False
        partial = False

        for s in add:

            exists = cur.execute(
                "SELECT 1 FROM sets WHERE set_num=?",
                (s,),
            ).fetchone()

            if not exists:
                partial = True
                continue

            cur.execute(
                "INSERT OR IGNORE INTO owned_sets(set_num, condition, note) VALUES (?,0,NULL)",
                (s,),
            )

            changed = True

        for s in remove:

            r = cur.execute(
                "DELETE FROM owned_sets WHERE set_num=?",
                (s,),
            )

            if r.rowcount:
                changed = True
            else:
                partial = True

        for s, c in cond:

            r = cur.execute(
                "UPDATE owned_sets SET condition=? WHERE set_num=?",
                (c, s),
            )

            if r.rowcount:
                changed = True
            else:
                partial = True

        for s, note_text in notes:

            r = cur.execute(
                "UPDATE owned_sets SET note=? WHERE set_num=?",
                (note_text, s),
            )

            if r.rowcount:
                changed = True
            else:
                partial = True

        self.conn.commit()

        if not changed:
            self.set_status(t("modify_fail"))
        elif partial:
            self.set_status(t("modify_partial"))
        else:
            self.set_status(t("modify_done"))

        self.search_var.set("")
        self.search_entry.focus()

def main():
    root = tk.Tk()
    app = LegoDBApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
