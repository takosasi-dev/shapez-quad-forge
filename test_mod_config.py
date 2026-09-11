"""test_mod_config.py -- mod_config.py の自己テスト。標準ライブラリの unittest のみを使う。
shape.SUBSHAPES/COLORS, levels.LEVELS/LEVEL_BY_NUMBER, render.COLOR_HEX はグローバルな
モジュール状態なので、各テストの前後で元の値を退避・復元する(他のテストファイルへの
影響漏れを防ぐため)。
"""

import json
import os
import tempfile
import unittest

import levels as L
import mod_config as M
import render
import shape as S


class ModConfigTest(unittest.TestCase):
    def setUp(self):
        self._subshapes = S.SUBSHAPES
        self._colors = S.COLORS
        self._levels = L.LEVELS
        self._level_by_number = L.LEVEL_BY_NUMBER
        self._color_hex = dict(render.COLOR_HEX)

    def tearDown(self):
        S.SUBSHAPES = self._subshapes
        S.COLORS = self._colors
        L.LEVELS = self._levels
        L.LEVEL_BY_NUMBER = self._level_by_number
        # COLOR_HEXは辞書(可変)。render.pyの_COLOR_HEXと同一オブジェクトなので
        # 差し替えではなくその場で内容を戻す。
        render.COLOR_HEX.clear()
        render.COLOR_HEX.update(self._color_hex)

    def _write_json(self, tmpdir, data):
        path = os.path.join(tmpdir, "mod_config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_missing_file_returns_empty_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = os.path.join(tmpdir, "does_not_exist.json")
            self.assertFalse(os.path.exists(missing))
            result = M.apply_mod_config(path=missing)
        self.assertEqual(result, [])
        self.assertEqual(S.SUBSHAPES, self._subshapes)
        self.assertEqual(S.COLORS, self._colors)
        self.assertEqual(L.LEVEL_BY_NUMBER, self._level_by_number)

    def test_valid_config_applies_subshapes_colors_and_levels(self):
        config = {
            "subshapes": "X",
            "colors": {"m": "#ff8800"},
            "levels": [
                {"level": 27, "shape": "XmXmXmXm", "required": 500,
                 "reward": "mod_reward_1", "per_second": False}
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, config)
            result = M.apply_mod_config(path=path)

        self.assertNotEqual(result, [])
        self.assertIn("X", S.SUBSHAPES)
        self.assertIn("m", S.COLORS)
        self.assertEqual(render.COLOR_HEX.get("m"), "#ff8800")

        # 新記号を使ったシェイプコードがparseできる
        parsed = S.parse("XmXmXmXm")
        self.assertEqual(S.key_of(parsed), "XmXmXmXm")

        self.assertIn(27, L.LEVEL_BY_NUMBER)
        self.assertEqual(L.LEVEL_BY_NUMBER[27].shape, "XmXmXmXm")
        self.assertEqual(L.LEVEL_BY_NUMBER[27].required, 500)
        self.assertEqual(L.LEVEL_BY_NUMBER[27].reward, "mod_reward_1")
        # levels昇順tupleに保たれている(新規追加は末尾)
        self.assertEqual(L.LEVELS[-1].level, 27)

    def test_broken_json_returns_empty_without_raising(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "mod_config.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{this is not valid json")
            result = M.apply_mod_config(path=path)
        self.assertEqual(result, [])

    def test_one_invalid_level_entry_is_skipped_others_applied(self):
        config = {
            "levels": [
                {"level": 30, "shape": "CuCuCuCu", "required": 10, "reward": "mod_ok"},
                {"level": 31, "shape": "ZzZzZzZz"},  # Z/zは未定義記号 -> ShapeErrorで無視
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, config)
            result = M.apply_mod_config(path=path)

        self.assertNotEqual(result, [])
        self.assertIn(30, L.LEVEL_BY_NUMBER)
        self.assertEqual(L.LEVEL_BY_NUMBER[30].reward, "mod_ok")
        self.assertNotIn(31, L.LEVEL_BY_NUMBER)

    def test_existing_level_number_is_overwritten(self):
        config = {
            "levels": [
                {"level": 1, "shape": "RuRuRuRu", "required": 99, "reward": "mod_over"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, config)
            result = M.apply_mod_config(path=path)

        self.assertNotEqual(result, [])
        self.assertEqual(L.LEVEL_BY_NUMBER[1].shape, "RuRuRuRu")
        self.assertEqual(L.LEVEL_BY_NUMBER[1].required, 99)
        self.assertEqual(L.LEVEL_BY_NUMBER[1].reward, "mod_over")
        # 上書きなので件数は増えない
        self.assertEqual(len(L.LEVELS), len(self._levels))


if __name__ == "__main__":
    unittest.main(verbosity=2)
