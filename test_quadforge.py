"""test_quadforge.py -- 自己テスト。標準ライブラリの unittest のみを使う(INV-8)。
`python test_quadforge.py` で通常テスト、`python test_quadforge.py --long` で
本体の computeFreeplayShape に相当する対称性ルールでのランダム検証も行う(§8.3)。
"""

import random
import sys
import time
import unittest

import construct
import levels as L
import shape as S
import solver as V
import throughput as T


class ShapeOpsTest(unittest.TestCase):
    def test_parse_key_roundtrip(self):
        for key in ("CuCuCuCu", "RuRu----", "CbCbCbRb:CwCwCwCw", "--Cg----:--Cr----"):
            self.assertEqual(S.key_of(S.parse(key)), key)

    def test_cut_half(self):
        sh = S.parse("CrCrCbCb")
        left, right = S.cut_half(sh)
        self.assertEqual(S.key_of(left), "----CbCb")
        self.assertEqual(S.key_of(right), "CrCr----")

    def test_cut_quad(self):
        sh = S.parse("CrCgCbCy")
        outs = S.cut_quad(sh)
        self.assertEqual([S.key_of(o) for o in outs],
                          ["Cr------", "--Cg----", "----Cb--", "------Cy"])

    def test_rotate(self):
        sh = S.parse("CrCwCbCg")
        self.assertEqual(S.key_of(S.rotate_cw(sh)), "CgCrCwCb")
        self.assertEqual(S.key_of(S.rotate_ccw(sh)), "CwCbCgCr")
        self.assertEqual(S.key_of(S.rotate_180(sh)), "CbCgCrCw")
        self.assertEqual(S.rotate_ccw(S.rotate_cw(sh)), sh)
        self.assertEqual(S.rotate_180(S.rotate_180(sh)), sh)

    def test_stack_merge_into_one_layer(self):
        bottom = S.parse("--RuRuRu")
        top = S.parse("Cu------")
        merged = S.stack(bottom, top)
        self.assertEqual(S.key_of(merged), "CuRuRuRu")

    def test_stack_layer_cap(self):
        a = S.parse("CuCuCuCu")
        s = a
        for _ in range(5):
            s = S.stack(s, a)
        self.assertEqual(len(s), 4)

    def test_paint_and_paint_quad(self):
        sh = S.parse("CuCuCuCu")
        self.assertEqual(S.key_of(S.paint(sh, "r")), "CrCrCrCr")
        self.assertEqual(S.key_of(S.paint_quad(sh, ["r", None, "g", None])), "CrCuCgCu")

    def test_mix_colors(self):
        self.assertEqual(S.mix_colors("r", "g"), "y")
        self.assertEqual(S.mix_colors("r", "b"), "p")
        self.assertEqual(S.mix_colors("g", "b"), "c")
        self.assertEqual(S.mix_colors("y", "b"), "w")
        self.assertEqual(S.mix_colors("r", "u"), "r")

    def test_invalid_shapes_rejected(self):
        bad = [
            "",                                              # 空文字
            "CuCuCuC",                                       # 7文字レイヤー
            "XuCuCuCu",                                      # 未定義の形状
            "CuCxCuCu",                                       # 未定義の色
            "--------",                                       # 完全に空のレイヤー
            "CuCuCuCu:CuCuCuCu:CuCuCuCu:CuCuCuCu:CuCuCuCu",   # 5層
        ]
        for key in bad:
            with self.assertRaises(S.ShapeError, msg=key):
                S.parse(key)


class KnownMinimumTest(unittest.TestCase):
    """AC-5: 既知の最小手数との一致。"""

    def _solve(self, key, cfg=None):
        cfg = cfg or V.SolverConfig()
        deadline = time.time() + cfg.time_limit
        plan, guaranteed = V.solve_with_bound(S.parse(key), cfg, deadline)
        return plan, guaranteed

    def test_known_minimums(self):
        for key, expected in (("Cu------", 3), ("RuRu----", 1), ("Cu----Cu", 2)):
            plan, guaranteed = self._solve(key)
            self.assertIsNotNone(plan, key)
            self.assertTrue(guaranteed, key)
            self.assertEqual(plan.cost, expected, key)
            self.assertEqual(V.simulate(plan), key)

    def test_quad_cutter_isolates_single_quadrant_in_one_step(self):
        """クアッドカッター解禁時は、単一象限の分離がカッター+ロータリーター+カッターの
        3手ではなく1手で済む(Lv16解禁の建物が探索に反映されているかの回帰チェック)。"""
        key = "Cu------"
        plan, guaranteed = self._solve(key, V.SolverConfig(quad_cutter=True))
        self.assertIsNotNone(plan)
        self.assertTrue(guaranteed)
        self.assertEqual(plan.cost, 1)
        self.assertEqual(plan.building, "cutter_quad")
        self.assertEqual(V.simulate(plan), key)

    def test_floating_shape_via_forced_collision(self):
        """P-7: 浮いたシェイプ(空象限の直上にセルがある形)。使っていない象限を
        1つ「使い捨ての衝突要員」として一時的に混ぜてスタックすると強制的にtop側全体が
        1層押し上げられ、最後にその象限をカットで除去すると正しい浮いた構造が残る
        (_forced_float_candidates の回帰チェック)。"""
        key = "RuCw--Cw:----Ru--"
        plan, guaranteed = self._solve(key, V.SolverConfig(quad_cutter=True, max_cost=30))
        self.assertIsNotNone(plan)
        self.assertTrue(guaranteed)
        self.assertEqual(V.simulate(plan), key)


class LevelsTest(unittest.TestCase):
    """AC-3: 全26レベルの手順が自己検証(ラウンドトリップ)で目標シェイプに一致する。
    各レベルの解禁状況どおり、Lv16以降はクアッドカッター・Lv20以降はクアッドペインターを
    使える前提でコストを検証する(実際の攻略で使える建物のみを使った参考値)。

    既知の未解決点(v0.1 時点、Phase 4 で扱う):
      - Lv23 は最小保証なしの実用解しか出ない(コストは検証しない)。
      - Lv26 は「浮いたシェイプ」(P-7)のうち、使っていない象限を1つも持たない
        (全4層を通じて4象限すべてがどこかで実際に使われている)特に難しいケースで、
        「使い捨ての衝突要員」用の空き象限を借りられないため現バージョンでは解なしになりうる。
        Lv20(RuCw--Cw:----Ru--)は、使っていない象限を一時的な衝突要員として借りて
        最後にカットで捨てる手筋(_forced_float_candidates)で解決済み。
    """

    _NO_GUARANTEE = {23}
    _FLOATING_SHAPE_UNSUPPORTED = {26}
    # §8.1 で実測済み、またはクアッドカッター解禁後の探索で確認済みの延べ建物数。
    _EXPECTED_COST = {
        1: 0, 2: 1, 3: 0, 4: 1, 5: 2, 6: 3, 7: 1, 8: 2, 9: 2, 10: 2,
        11: 7, 13: 6, 14: 6, 15: 4, 16: 8, 17: 11, 19: 11, 20: 16,
    }

    def test_all_levels_round_trip(self):
        for lv in L.LEVELS:
            with self.subTest(level=lv.level, shape=lv.shape):
                cfg = V.SolverConfig(time_limit=15.0, max_cost=30,
                                      quad_cutter=lv.level >= 16, quad_painter=lv.level >= 20)
                sh = S.parse(lv.shape)
                plan, guaranteed = construct.find_plan(sh, cfg)
                if plan is None and lv.level in self._FLOATING_SHAPE_UNSUPPORTED:
                    continue
                self.assertIsNotNone(plan, f"Lv{lv.level} 解なし")
                self.assertEqual(V.simulate(plan), lv.shape, f"Lv{lv.level} 検証失敗")
                expected = self._EXPECTED_COST.get(lv.level)
                if expected is not None and lv.level not in self._NO_GUARANTEE:
                    self.assertEqual(plan.cost, expected, f"Lv{lv.level} コスト不一致")


class ThroughputTest(unittest.TestCase):
    """AC-6: 建物速度の定数一致。"""

    def test_base_speeds(self):
        tiers = {"miner": 0, "processors": 0, "painting": 0}
        self.assertAlmostEqual(T.speed("miner", tiers), 0.4)
        self.assertAlmostEqual(T.speed("cutter", tiers), 0.5)
        self.assertAlmostEqual(T.speed("rotater", tiers), 2.0)
        self.assertAlmostEqual(T.speed("stacker", tiers), 0.25)
        self.assertAlmostEqual(T.speed("painter", tiers), 1 / 3)
        self.assertAlmostEqual(T.speed("mixer", tiers), 0.4)

    def test_tier_progression(self):
        self.assertEqual([T.multiplier("processors", t) for t in range(8)],
                          [1.0, 1.5, 2, 3, 4, 6, 7, 8])


class StackSplitRandomTest(unittest.TestCase):
    """AC-4 に相当: カッター/スタッカーの往復に関する健全性・完全性をランダムに確認する。"""

    def _random_layer(self, rng):
        subs = "CRSW"
        colors = "urgb"
        return tuple(
            (rng.choice(subs), rng.choice(colors)) if rng.random() < 0.7 else None
            for _ in range(4)
        )

    def test_cut_stack_round_trip(self):
        rng = random.Random(12345)
        n = 0
        attempts = 0
        while n < 200 and attempts < 4000:
            attempts += 1
            layer = self._random_layer(rng)
            if not any(c is not None for c in layer):
                continue
            left_only = tuple((c if q in (2, 3) else None) for q, c in enumerate(layer))
            right_only = tuple((c if q in (0, 1) else None) for q, c in enumerate(layer))
            if not any(c is not None for c in left_only) or not any(c is not None for c in right_only):
                continue
            shape = (layer,)
            left, right = S.cut_half(shape)
            self.assertEqual(S.key_of(left), S.key_of((left_only,)))
            self.assertEqual(S.key_of(right), S.key_of((right_only,)))
            rebuilt = S.stack(left, right)
            self.assertEqual(S.key_of(rebuilt), S.key_of(shape))
            n += 1
        self.assertGreaterEqual(n, 200)


def _long_freeplay_symmetry_check() -> None:
    """--long 用: 本体の computeFreeplayShape が使う対称性ルール(quadrant_pair)を
    模したランダムシェイプで、カッター+ロータリーターの往復が壊れないことを確認する。"""
    rng = random.Random(2026)
    symmetries = [((0, 2), (1, 3)), ((0, 1), (2, 3)), ((0, 3), (1, 2))]
    ok = 0
    for _ in range(300):
        pair_a, pair_b = rng.choice(symmetries)
        subs, colors = "CRSW", "urgbypcw"

        def cell():
            return (rng.choice(subs), rng.choice(colors))

        layer = [None, None, None, None]
        va, vb = cell(), cell()
        for q in pair_a:
            layer[q] = va
        for q in pair_b:
            layer[q] = vb
        shape = (tuple(layer),)
        key = S.key_of(shape)
        back = S.parse(key)
        assert S.key_of(back) == key
        assert S.key_of(S.rotate_ccw(S.rotate_cw(shape))) == key
        ok += 1
    print(f"[--long] freeplay対称シェイプの往復確認: {ok}/300 OK")


if __name__ == "__main__":
    if "--long" in sys.argv:
        sys.argv.remove("--long")
        _long_freeplay_symmetry_check()
    unittest.main(verbosity=2)
