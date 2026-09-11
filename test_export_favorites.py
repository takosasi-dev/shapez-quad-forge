"""test_export_favorites.py -- export_plan.py と favorites.py の自己テスト。
標準ライブラリの unittest のみを使う(INV-8)。tempfile で一時パスを使い、
実際の favorites.json や作業フォルダには一切触れない。
"""

import os
import tempfile
import unittest

import export_plan
import favorites
from solver import Plan


def _sample_plan() -> Plan:
    """format_plan/plan_to_text の動作確認用に手組みした小さな手順木
    (探索エンジンは動かさない)。"""
    leaf = Plan("shape", "Cu------", "mine", "採掘:Cu", 0, None, [])
    return Plan("shape", "CuCu----", "stack", "スタッカーで積み重ね", 1, "stacker", [leaf, leaf])


class PlanToTextTest(unittest.TestCase):
    def test_contains_key_facts_when_guaranteed(self):
        plan = _sample_plan()
        text = export_plan.plan_to_text(plan, guaranteed=True, unique_cost=1)
        self.assertIn(plan.key, text)
        self.assertIn(f"{plan.cost}", text)
        self.assertIn("建物数(ユニーク): 1", text)
        self.assertIn("最小手数を保証", text)
        # solver.format_plan() の出力(手順ツリー)が含まれること。
        # 注意: format_plan は plan.label ではなく op から _OP_LABEL で表示名を
        # 引き直すため、leaf の実際の行は「採掘: Cu------ (建物 0)」になる。
        self.assertIn("採掘: Cu------", text)

    def test_practical_wording_when_not_guaranteed(self):
        plan = _sample_plan()
        text = export_plan.plan_to_text(plan, guaranteed=False, unique_cost=2)
        self.assertIn("実用解(最小保証なし)", text)
        self.assertNotIn("最小手数を保証", text)

    def test_save_text_roundtrip(self):
        plan = _sample_plan()
        expected = export_plan.plan_to_text(plan, guaranteed=True, unique_cost=1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.txt")
            export_plan.save_text(path, plan, guaranteed=True, unique_cost=1)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        self.assertEqual(content, expected)


class FavoritesTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmpdir.name, "favorites.json")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_add_then_load(self):
        favorites.add("CuCuCuCu", "基本の丸", path=self.path)
        result = favorites.load(self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, "CuCuCuCu")
        self.assertEqual(result[0].note, "基本の丸")

    def test_add_duplicate_code_is_noop(self):
        favorites.add("CuCuCuCu", "1回目", path=self.path)
        favorites.add("CuCuCuCu", "2回目", path=self.path)
        result = favorites.load(self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].note, "1回目")  # 2回目は無視される

    def test_remove_deletes_only_matching_code(self):
        favorites.add("CuCuCuCu", path=self.path)
        favorites.add("RuRu----", path=self.path)
        favorites.remove("CuCuCuCu", path=self.path)
        result = favorites.load(self.path)
        self.assertEqual([f.code for f in result], ["RuRu----"])

    def test_load_missing_file_returns_empty_list(self):
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(favorites.load(self.path), [])

    def test_load_corrupt_json_returns_empty_list(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        self.assertEqual(favorites.load(self.path), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
