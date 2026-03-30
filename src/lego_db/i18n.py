from __future__ import annotations

import json

from lego_db.core import CONFIG_PATH, LANG_DIR, LANGUAGE_LABELS


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


def set_language(code: str) -> None:
    global lang
    lang = Lang(code)


def t(key: str) -> str:
    return lang.t(key)