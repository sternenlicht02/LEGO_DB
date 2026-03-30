from __future__ import annotations

from contextlib import suppress
from typing import Optional

import tkinter as tk
from tkinter import ttk

from lego_db.commands import apply_modification_plan
from lego_db.core import (
    CONFIG_PATH,
    CONTROL_CHAR_RE,
    DETAIL_HEIGHT,
    DETAIL_WIDTH,
    WINDOW_GEOMETRY,
    WINDOW_TITLE,
    SetRow,
    center_window_on_screen,
    normalize_setnum,
    parse_modification_text,
    parse_window_geometry,
    condition_tag,
    SETNUM_RE,
)
from lego_db.i18n import language_options_from_files, load_config, set_language, t, write_config
from lego_db.repository import LegoRepository
from lego_db.core import DB_PATH


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

    def _on_global_keypress(self, event) -> str | None:
        if event.char != "/" and event.keysym.lower() != "slash":
            return None
        
        if self.detail_window is not None and self.detail_window.winfo_exists():
            return None
        
        if event.widget is self.search_entry:
            return None
        
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        
        self._focus_search_entry(clear=True)
        return "break"

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

        self.root.bind_all("<KeyPress>", self._on_global_keypress, add="+")

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
                "name": 232,
                "pieces": 50,
                "year": 50,
                "condition": 63,
                "note": 120,
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
        self.main_tree.bind("<Button-3>", self._on_right_click)
        self.related_tree.bind("<Button-3>", self._on_right_click)

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

    def _focus_search_entry(self, clear: bool = False) -> None:
        if self.search_entry.winfo_exists():
            self.search_entry.focus_force()
            if clear:
                self.search_entry.delete(0, tk.END)
            self.search_entry.icursor(0)

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
    
    def _on_right_click(self, event) -> str:
        tree = event.widget

        item_id = tree.identify_row(event.y)
        if not item_id:
            return "break"

        tree.selection_set(item_id)
        tree.focus(item_id)
        self.last_selected_tree = tree

        set_num = self._tree_setnum(tree)
        if not set_num or self.repo is None:
            return "break"

        owned = self.repo.is_owned(set_num)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label=t("remove_owned") if owned else t("add_owned"),
            command=lambda: self._toggle_owned(set_num),
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

        return "break"
    
    def _toggle_owned(self, set_num: str) -> None:
        if self.repo is None:
            return

        try:
            self.repo.conn.execute("BEGIN")

            if self.repo.is_owned(set_num):
                changed = self.repo.remove_owned(set_num)
            else:
                changed = self.repo.add_owned(set_num)

            if not changed:
                self.repo.conn.rollback()
                return

            self.repo.conn.commit()

        except Exception:
            self.repo.conn.rollback()
            raise

        self.set_status(t("modify_done"))
        self._refresh_after_owned_change(set_num)

    def _refresh_after_owned_change(self, set_num: str) -> None:
        text = self.last_search_text.strip()

        if not text:
            self.search()
            return

        head = text.split(maxsplit=1)[0].casefold()

        if head in {"owned", "보유"}:
            self.search()
            return

        info = self.repo.fetch_set(set_num)
        if info is None:
            return

        for tree in (self.main_tree, self.related_tree):
            for item in tree.get_children():
                values = tree.item(item, "values")
                if not values:
                    continue

                current = str(values[2]) if tree is self.main_tree else str(values[0])

                if current == set_num:
                    new_values = (
                        info.main_values()
                        if tree is self.main_tree
                        else info.related_values()
                    )
                    tree.item(
                        item,
                        values=new_values,
                        tags=(self._condition_tag(info.condition),),
                    )

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
            pady=6,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            center_frame,
            text=t("close"),
            command=self._close_detail_window,
            padx=10,
            pady=6,
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

        result = apply_modification_plan(self.repo, plan)
        if result.error is not None:
            self.set_status(f"{t('modify_fail')}: {result.error}")
            self.search_var.set("")
            self.search_entry.focus()
            return

        if result.changed and result.partial:
            self.set_status(t("modify_partial"))
        elif result.changed:
            self.set_status(t("modify_done"))
        else:
            self.set_status(t("modify_fail"))

        self.search_var.set("")
        self.search_entry.focus()
        self._refresh_after_modification()

    def _refresh_after_modification(self) -> None:
        self._search_text(self.last_search_text)


def main() -> None:
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
        set_language(str(config.get("language", "en")))
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