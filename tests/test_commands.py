import unittest

from lego_db.core import ModificationPlan
from lego_db.commands import apply_modification_plan


class DummyConn:
    def __init__(self) -> None:
        self.statements = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        return self

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class DummyRepo:
    def __init__(self) -> None:
        self.conn = DummyConn()
        self.existing_sets = {"1000", "2000"}
        self.owned = set()

    def has_set(self, set_num: str) -> bool:
        return set_num in self.existing_sets

    def add_owned(self, set_num: str) -> bool:
        if not self.has_set(set_num) or set_num in self.owned:
            return False
        self.owned.add(set_num)
        return True

    def remove_owned(self, set_num: str) -> bool:
        if set_num in self.owned:
            self.owned.remove(set_num)
            return True
        return False

    def update_condition(self, set_num: str, condition: int) -> bool:
        return set_num in self.owned

    def update_note(self, set_num: str, note: str) -> bool:
        return set_num in self.owned


class ModificationServiceTests(unittest.TestCase):

    def test_apply_modification_plan_success_and_partial(self) -> None:
        repo = DummyRepo()

        plan = ModificationPlan(
            add=["1000"],
            remove=["2000"],
            conditions=[("1000", 2)],
            notes=[("1000", "note")],
        )

        result = apply_modification_plan(repo, plan)

        self.assertTrue(result.changed)
        self.assertTrue(result.partial)
        self.assertFalse(result.malformed)
        self.assertIsNone(result.error)

        self.assertTrue(repo.conn.committed)
        self.assertFalse(repo.conn.rolled_back)

        self.assertIn("1000", repo.owned)

    def test_apply_modification_plan_malformed_skips_transaction(self) -> None:
        repo = DummyRepo()
        plan = ModificationPlan(malformed=True)

        result = apply_modification_plan(repo, plan)

        self.assertFalse(result.changed)
        self.assertFalse(result.partial)
        self.assertTrue(result.malformed)
        self.assertIsNone(result.error)

        self.assertFalse(repo.conn.committed)
        self.assertFalse(repo.conn.rolled_back)
        self.assertEqual(repo.conn.statements, [])


if __name__ == "__main__":
    unittest.main()