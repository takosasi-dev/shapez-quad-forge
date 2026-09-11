"""test_batch.py -- batch.py の自己テスト。標準ライブラリの unittest のみを使う(INV-8)。
テストが遅くならないよう、既知の低コストシェイプだけを max_cost/time_limit を絞った
SolverConfig で解く(test_quadforge.py の KnownMinimumTest と同じシェイプコードを流用)。
"""

import unittest

import batch
from solver import SolverConfig


def _fast_cfg() -> SolverConfig:
    return SolverConfig(max_cost=10, time_limit=3.0)


# test_quadforge.py の KnownMinimumTest で最小手数が既知の単純なシェイプ。
_KNOWN_CODES = ["CuCuCuCu", "RuRu----", "Cu----Cu"]


class SolveBatchTest(unittest.TestCase):
    def test_empty_list_returns_empty(self):
        self.assertEqual(batch.solve_batch([], _fast_cfg()), [])

    def test_known_simple_shapes_all_solved(self):
        results = batch.solve_batch(_KNOWN_CODES, _fast_cfg())
        self.assertEqual(len(results), len(_KNOWN_CODES))
        for code, r in zip(_KNOWN_CODES, results):
            self.assertEqual(r.code, code)
            self.assertIsNotNone(r.plan, code)
            self.assertIsNone(r.error, code)

    def test_invalid_codes_do_not_abort_batch(self):
        codes = ["CuCuCuCu", "", "RuRu----", "CuCuCuC"]  # 2,4番目は不正コード
        results = batch.solve_batch(codes, _fast_cfg())
        self.assertEqual(len(results), 4)

        self.assertIsNotNone(results[0].plan)
        self.assertIsNone(results[0].error)

        self.assertIsNone(results[1].plan)
        self.assertFalse(results[1].guaranteed)
        self.assertIsNotNone(results[1].error)

        self.assertIsNotNone(results[2].plan)
        self.assertIsNone(results[2].error)

        self.assertIsNone(results[3].plan)
        self.assertFalse(results[3].guaranteed)
        self.assertIsNotNone(results[3].error)

    def test_progress_callback_called_once_per_code_in_order(self):
        calls = []
        batch.solve_batch(_KNOWN_CODES, _fast_cfg(),
                           progress=lambda i, total, msg: calls.append((i, total, msg)))
        self.assertEqual(len(calls), len(_KNOWN_CODES))
        for expected_index, (i, total, msg) in enumerate(calls, start=1):
            self.assertEqual(i, expected_index)
            self.assertEqual(total, len(_KNOWN_CODES))
            self.assertIsInstance(msg, str)
            self.assertTrue(msg)

    def test_progress_callback_also_called_for_invalid_code(self):
        calls = []
        batch.solve_batch(["", "RuRu----"], _fast_cfg(),
                           progress=lambda i, total, msg: calls.append((i, total, msg)))
        self.assertEqual([c[0] for c in calls], [1, 2])
        self.assertEqual([c[1] for c in calls], [2, 2])


class SummarizeTest(unittest.TestCase):
    def test_empty_list_returns_string_without_raising(self):
        text = batch.summarize([])
        self.assertIsInstance(text, str)
        self.assertIn("0/0", text)

    def test_summary_mentions_each_code_and_solved_ratio(self):
        results = batch.solve_batch(_KNOWN_CODES + [""], _fast_cfg())
        text = batch.summarize(results)
        for code in _KNOWN_CODES:
            self.assertIn(code, text)
        self.assertIn(f"{len(_KNOWN_CODES)}/{len(_KNOWN_CODES) + 1}", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
