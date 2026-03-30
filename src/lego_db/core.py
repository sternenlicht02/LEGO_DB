from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from dataclasses import dataclass, field
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "lego.db"
CONFIG_PATH = PROJECT_ROOT / "config.json"
LANG_DIR = Path(__file__).resolve().parent / "data" / "language"

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
    r"|[012]\[(?:\\.|[^\]])*\]>\d+(?:-\d+)?"
    r"|\[(?:\\.|[^\]])*\][012]>\d+(?:-\d+)?"
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

COMBINED_RE = re.compile(
    r"^(?:"
    r"([012])\[((?:\\.|[^\]])*)\]"
    r"|"
    r"\[((?:\\.|[^\]])*)\]([012])"
    r")>([0-9]+(?:-\d+)?)$"
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


def escape_like_pattern(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


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
            combined = COMBINED_RE.fullmatch(token)
            if combined:
                if combined.group(1):
                    cond = int(combined.group(1))
                    note = combined.group(2)
                else:
                    cond = int(combined.group(4))
                    note = combined.group(3)

                set_num = combined.group(5)
                plan.conditions.append((set_num, cond))
                plan.notes.append((set_num, unescape_note(note)))

            else:
                note_match = NOTE_RE.fullmatch(token)
                if note_match:
                    plan.notes.append(
                        (note_match.group(2), unescape_note(note_match.group(1)))
                    )
                else:
                    plan.malformed = True

        cursor = match.end()

    if text[cursor:].strip():
        plan.malformed = True

    return plan