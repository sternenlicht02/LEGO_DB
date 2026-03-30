from __future__ import annotations

import sqlite3
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from lego_db.core import ModificationPlan, SETNUM_RE


@dataclass(frozen=True)
class ModificationResult:
    changed: bool
    partial: bool
    malformed: bool = False
    error: Optional[str] = None


def apply_modification_plan(repo, plan: ModificationPlan) -> ModificationResult:
    if not plan.has_tokens or plan.malformed:
        return ModificationResult(changed=False, partial=False, malformed=True)

    changed = False
    partial = False

    try:
        repo.conn.execute("BEGIN")

        for set_num in plan.add:
            if not SETNUM_RE.fullmatch(set_num):
                partial = True
                continue
            if not repo.has_set(set_num):
                partial = True
                continue
            if repo.add_owned(set_num):
                changed = True

        for set_num in plan.remove:
            if not SETNUM_RE.fullmatch(set_num):
                partial = True
                continue
            if repo.remove_owned(set_num):
                changed = True
            else:
                partial = True

        for set_num, condition in plan.conditions:
            if not SETNUM_RE.fullmatch(set_num):
                partial = True
                continue
            if repo.update_condition(set_num, condition):
                changed = True
            else:
                partial = True

        for set_num, note_text in plan.notes:
            if not SETNUM_RE.fullmatch(set_num):
                partial = True
                continue
            if repo.update_note(set_num, note_text):
                changed = True
            else:
                partial = True

        repo.conn.commit()
    except sqlite3.DatabaseError as exc:
        with suppress(Exception):
            repo.conn.rollback()
        return ModificationResult(
            changed=False,
            partial=False,
            malformed=False,
            error=str(exc),
        )

    return ModificationResult(changed=changed, partial=partial)