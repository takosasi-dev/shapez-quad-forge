"""solver.py -- 目標シェイプから構築手順を探索するエンジン(反復深化 + 逆算探索)。
GUI ツールキットは import しない(GUI から独立してテスト・CLI 実行できる)。

コストモデル(AC-5 の既知最小手数から逆算して確認済み):
  採掘(原始)は建物を置かない(地図上の資源パッチの配置は §3 の除外スコープ)ので cost=0, building=None。
  原色(u/r/g/b)の染料も同様に cost=0。混色(y/p/c/w)だけがミキサー(+1)を要する。
  カッター・ロータリーター・スタッカー・ペインターは1手ごとに+1。
"""

import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import shape as S

if sys.getrecursionlimit() < 6000:
    sys.setrecursionlimit(6000)


@dataclass
class Plan:
    kind: str                      # 'shape' | 'color'
    key: str                       # シェイプコード、または色1文字
    op: str                        # 'mine' 'cut0' 'cut1' 'cutQuad0'..'cutQuad3'
                                    # 'rotateCW' 'rotateCCW' 'rotate180'
                                    # 'stack' 'paint' 'paintQuad' 'mix'
    label: str                     # 画面表示用の日本語ラベル
    cost: int                      # この部分木に必要な建物数(延べ)
    building: Optional[str]        # この節点の操作に対応する建物ID。原始は None
    inputs: List["Plan"] = field(default_factory=list)


@dataclass
class SolverConfig:
    quad_cutter: bool = False      # クアッドカッター(Lv16 解禁)
    quad_painter: bool = False     # クアッドペインター(Lv20 / ワイヤー解禁)
    windmill_patch: bool = True    # 風車パッチ(4象限そろった風車ゴミ)を原始として扱う
    max_cost: int = 24
    time_limit: float = 20.0


class _TimeUp(Exception):
    pass


def _check_deadline(deadline: float) -> None:
    if time.time() > deadline:
        raise _TimeUp()


# --- 色の部分木(原色/無色は無償、混色だけミキサーを要する) ---

def _color_plan(color: str) -> Plan:
    recipe = S.color_recipe(color)
    if recipe is None:
        return Plan("color", color, "mine", f"染料:{color}", 0, None, [])
    a, b = recipe
    pa, pb = _color_plan(a), _color_plan(b)
    return Plan("color", color, "mix", f"色{a}+{b}を混色", pa.cost + pb.cost + 1, "mixer", [pa, pb])


# --- シェイプの形状解析ヘルパー ---

def _is_mineable_uniform(shape: S.Shape) -> bool:
    """採掘そのもの: 1層・4象限すべてが同じ(形状,無色)。"""
    if len(shape) != 1:
        return False
    cells = [c for c in shape[0] if c is not None]
    if len(cells) != 4 or len(set(cells)) != 1:
        return False
    return cells[0][1] == "u"


def _single_color(shape: S.Shape) -> Optional[str]:
    colors = {c[1] for layer in shape for c in layer if c is not None}
    if len(colors) == 1:
        return next(iter(colors))
    return None


def _quad_colors(shape: S.Shape) -> Optional[List[Optional[str]]]:
    result: List[Optional[str]] = []
    for q in range(4):
        colors = {layer[q][1] for layer in shape if layer[q] is not None}
        if len(colors) > 1:
            return None
        result.append(next(iter(colors)) if colors else None)
    return result


def _with_uncolored(shape: S.Shape) -> S.Shape:
    return tuple(tuple((c[0], "u") if c is not None else None for c in layer) for layer in shape)


def _occupied_quadrants(shape: S.Shape) -> Tuple[int, ...]:
    occ = set()
    for layer in shape:
        for q, c in enumerate(layer):
            if c is not None:
                occ.add(q)
    return tuple(sorted(occ))


# --- 象限パターンの逆算(カッター/ロータリーターだけでフル象限から目的の
#     象限パターンへ至る最小手数列を、内容を無視してパターンだけでBFSする)。
#     見つかった操作列を逆順にたどり、ミラー(180度回転)で捨てられた側を埋め戻すことで
#     「フル象限版」を再帰的に構築し、そこへ操作列を再適用して目的の形を得る。
#     これにより、複数レイヤーが同じ象限パターンを共有する場合(例: 同じ象限で
#     レイヤーごとに色が違う)も、まとめて1回の分離手順で切り出せる。

_PATTERN_FULL = frozenset((0, 1, 2, 3))
_PATTERN_MAX_OPS = 4
_PATTERN_BUILDING = {
    "cut0": "cutter", "cut1": "cutter",
    "rotateCW": "rotater", "rotateCCW": "rotater_ccw", "rotate180": "rotater_180",
    "cutQuad0": "cutter_quad", "cutQuad1": "cutter_quad",
    "cutQuad2": "cutter_quad", "cutQuad3": "cutter_quad",
}
_PATTERN_LABEL = {
    "cut0": "カッター(左側を確保)", "cut1": "カッター(右側を確保)",
    "rotateCW": "ロータリーター(時計回り)", "rotateCCW": "ロータリーター(反時計回り)",
    "rotate180": "ロータリーター(180度)",
    "cutQuad0": "クアッドカッター(象限0)", "cutQuad1": "クアッドカッター(象限1)",
    "cutQuad2": "クアッドカッター(象限2)", "cutQuad3": "クアッドカッター(象限3)",
}


def _pattern_moves(pat: frozenset, quad_cutter: bool) -> List[Tuple[str, frozenset]]:
    moves = []
    keep01 = pat & {0, 1}
    keep23 = pat & {2, 3}
    if keep01 and keep01 != pat:
        moves.append(("cut1", frozenset(keep01)))
    if keep23 and keep23 != pat:
        moves.append(("cut0", frozenset(keep23)))
    cw = frozenset((i + 1) % 4 for i in pat)
    ccw = frozenset((i - 1) % 4 for i in pat)
    r180 = frozenset((i + 2) % 4 for i in pat)
    if cw != pat:
        moves.append(("rotateCW", cw))
    if ccw != pat:
        moves.append(("rotateCCW", ccw))
    if r180 != pat:
        moves.append(("rotate180", r180))
    if quad_cutter:
        # クアッドカッター: 現在の象限パターンの中から、任意の1象限を直接単独に切り出せる(Lv16解禁)。
        for q in pat:
            single = frozenset((q,))
            if single != pat:
                moves.append((f"cutQuad{q}", single))
    return moves


_pattern_chain_cache: Dict[Tuple[frozenset, bool], Optional[List[str]]] = {}


def _pattern_chain(target: frozenset, quad_cutter: bool) -> Optional[List[str]]:
    cache_key = (target, quad_cutter)
    if cache_key in _pattern_chain_cache:
        return _pattern_chain_cache[cache_key]
    if target == _PATTERN_FULL:
        return []
    visited = {_PATTERN_FULL: (None, None)}
    frontier = deque([(_PATTERN_FULL, 0)])
    result: Optional[List[str]] = None
    while frontier:
        cur, d = frontier.popleft()
        if d >= _PATTERN_MAX_OPS:
            continue
        for op, nxt in _pattern_moves(cur, quad_cutter):
            if nxt in visited:
                continue
            visited[nxt] = (cur, op)
            if nxt == target:
                chain = []
                node = nxt
                while visited[node][0] is not None:
                    p, o = visited[node]
                    chain.append(o)
                    node = p
                chain.reverse()
                result = chain
                frontier.clear()
                break
            frontier.append((nxt, d + 1))
    _pattern_chain_cache[cache_key] = result
    return result


def _shared_pattern(shape: S.Shape) -> Optional[frozenset]:
    patterns = {frozenset(q for q, c in enumerate(layer) if c is not None) for layer in shape}
    if len(patterns) == 1:
        return next(iter(patterns))
    return None


def _apply_pattern_op(shape: S.Shape, op: str) -> S.Shape:
    if op == "cut0":
        left, _ = S.cut_half(shape)
        return left
    if op == "cut1":
        _, right = S.cut_half(shape)
        return right
    if op.startswith("cutQuad"):
        idx = int(op[-1])
        return S.cut_quad(shape)[idx]
    if op == "rotateCW":
        return S.rotate_cw(shape)
    if op == "rotateCCW":
        return S.rotate_ccw(shape)
    return S.rotate_180(shape)


def _track_survivors(chain: List[str]) -> Dict[int, int]:
    """chain を象限ラベル0..3について前向きにシミュレートし、カッターで捨てられずに
    最後まで残ったラベルが最終的にどの位置へ来るかを求める。
    戻り値: {最終位置: 元の位置}。"""
    positions = {q: q for q in range(4)}
    for op in chain:
        new_positions: Dict[int, int] = {}
        for label, pos in positions.items():
            if op == "cut1":
                if pos not in (0, 1):
                    continue
                new_positions[label] = pos
            elif op == "cut0":
                if pos not in (2, 3):
                    continue
                new_positions[label] = pos
            elif op.startswith("cutQuad"):
                if pos != int(op[-1]):
                    continue
                new_positions[label] = pos
            elif op == "rotateCW":
                new_positions[label] = (pos + 1) % 4
            elif op == "rotateCCW":
                new_positions[label] = (pos - 1) % 4
            else:
                new_positions[label] = (pos + 2) % 4
        positions = new_positions
    return {pos: label for label, pos in positions.items()}


def _pattern_isolate_plan(shape: S.Shape, cfg: SolverConfig, memo: Dict[str, Plan],
                           deadline: float, budget: int) -> Optional[Plan]:
    pattern = _shared_pattern(shape)
    if pattern is None or not pattern or pattern == _PATTERN_FULL:
        return None
    chain = _pattern_chain(pattern, cfg.quad_cutter)
    if not chain or len(chain) > budget:
        return None

    survivors = _track_survivors(chain)  # {最終位置: 元の位置}
    if set(survivors.keys()) != set(pattern):
        return None
    orig_positions = set(survivors.values())

    full_layers = []
    for layer in shape:
        new_layer: List[S.Cell] = [None, None, None, None]
        filler: S.Cell = None
        for final_pos, orig_pos in survivors.items():
            content = layer[final_pos]
            new_layer[orig_pos] = content
            if content is not None and filler is None:
                filler = content
        for p in range(4):
            if p not in orig_positions:
                new_layer[p] = filler
        full_layers.append(tuple(new_layer))
    virtual = tuple(l for l in full_layers if any(c is not None for c in l))
    if not virtual:
        return None

    full_plan = _solve(virtual, cfg, memo, deadline, budget - len(chain))
    if full_plan is None:
        return None

    cur_shape = virtual
    cur_plan = full_plan
    for op in chain:
        cur_shape = _apply_pattern_op(cur_shape, op)
        if cur_shape is None:
            return None
        cur_plan = Plan("shape", S.key_of(cur_shape), op, _PATTERN_LABEL[op],
                         cur_plan.cost + 1, _PATTERN_BUILDING[op], [cur_plan])

    if S.key_of(cur_shape) != S.key_of(shape):
        return None
    return cur_plan


# --- 反復深化つき再帰探索 ---

def _leaf_candidates(shape: S.Shape, cfg: SolverConfig) -> List[Plan]:
    cands: List[Plan] = []
    if _is_mineable_uniform(shape):
        sub = shape[0][0][0]
        cands.append(Plan("shape", S.key_of(shape), "mine", f"採掘:{sub}u", 0, None, []))
    return cands


def _stack_split_candidates(shape: S.Shape, cfg: SolverConfig, memo, deadline, budget) -> List[Plan]:
    cands = []
    n = len(shape)
    if n < 2:
        return cands
    for split in range(1, n):
        bottom = shape[:split]
        top = shape[split:]
        if not any(c is not None for layer in top for c in layer):
            continue
        if not any(c is not None for layer in bottom for c in layer):
            continue
        bp = _solve(bottom, cfg, memo, deadline, budget - 1)
        if bp is None:
            continue
        tp = _solve(top, cfg, memo, deadline, budget - 1 - bp.cost)
        if tp is None:
            continue
        rebuilt = S.stack(S.parse(bp.key), S.parse(tp.key))
        if S.key_of(rebuilt) != S.key_of(shape):
            continue
        cost = bp.cost + tp.cost + 1
        if cost <= budget:
            cands.append(Plan("shape", S.key_of(shape), "stack", "スタッカーで積み重ね", cost, "stacker", [bp, tp]))
    return cands


_FLOAT_FILLER: S.Cell = ("C", "u")


def _forced_float_candidates(shape: S.Shape, cfg: SolverConfig, memo, deadline, budget) -> List[Plan]:
    """浮いたシェイプ(P-7)用: layer0とlayers[1:]を素朴にスタックすると、素な象限同士は
    必ず1層に潰れてしまう(D-6での検証済みの数学的事実)。そこで、このshapeが使っていない
    象限を1つ「使い捨ての衝突要員」として両方の断面に一時的に混ぜてスタックすると、
    その象限どうしの衝突が強制的にtop側全体を1層分押し上げる。押し上げられたshape自身の
    層構造はそのまま保たれるので、最後に衝突要員の象限だけをカット(クアッドカッター、
    または半分カット+ロータリーターの組)で捨てればshapeが正しく復元できる。"""
    cands = []
    n = len(shape)
    if n < 2:
        return cands
    pat = frozenset(_occupied_quadrants(shape))
    if not pat or pat == _PATTERN_FULL:
        return cands
    chain = _pattern_chain(pat, cfg.quad_cutter)
    if not chain:
        return cands

    bottom_layer = shape[0]
    rest = shape[1:]
    rest_first = rest[0]

    for qf in range(4):
        if qf in pat:
            continue
        bottom_ext = (tuple(_FLOAT_FILLER if i == qf else c for i, c in enumerate(bottom_layer)),)
        rest_first_ext = tuple(_FLOAT_FILLER if i == qf else c for i, c in enumerate(rest_first))
        top_ext = (rest_first_ext,) + rest[1:]

        bp = _solve(bottom_ext, cfg, memo, deadline, budget - 1 - len(chain))
        if bp is None:
            continue
        tp = _solve(top_ext, cfg, memo, deadline, budget - 1 - len(chain) - bp.cost)
        if tp is None:
            continue

        precursor = S.stack(S.parse(bp.key), S.parse(tp.key))
        stack_cost = bp.cost + tp.cost + 1
        if stack_cost + len(chain) > budget:
            continue

        cur_shape = precursor
        cur_plan = Plan("shape", S.key_of(precursor), "stack", "使い捨て象限で強制的にずらしてスタック",
                         stack_cost, "stacker", [bp, tp])
        chain_ok = True
        for op in chain:
            cur_shape = _apply_pattern_op(cur_shape, op)
            if cur_shape is None:
                chain_ok = False
                break
            cur_plan = Plan("shape", S.key_of(cur_shape), op, _PATTERN_LABEL[op],
                             cur_plan.cost + 1, _PATTERN_BUILDING[op], [cur_plan])
        if not chain_ok:
            continue

        if S.key_of(cur_shape) != S.key_of(shape):
            continue
        if cur_plan.cost <= budget:
            cands.append(cur_plan)
    return cands


_PEEL_PATTERNS = ((0,), (1,), (2,), (3,), (0, 1), (1, 2), (2, 3), (0, 3))


def _quadrant_isolate_candidates(shape: S.Shape, cfg: SolverConfig, memo, deadline, budget) -> List[Plan]:
    """占有象限の一部(単一、または隣接・対角の2象限)を切り出し、残りと
    スタッカーで合成する候補を試す(内容が象限ごとに異なる場合の一般手段)。"""
    cands = []
    occ = set(_occupied_quadrants(shape))
    if len(occ) < 2:
        return cands
    for pat in _PEEL_PATTERNS:
        patset = set(pat)
        if not patset <= occ or patset == occ:
            continue
        piece = S._filter_quadrants(shape, pat)
        remainder = S._filter_quadrants(shape, tuple(sorted(occ - patset)))
        if piece is None or remainder is None:
            continue
        pp = _solve(piece, cfg, memo, deadline, budget - 1)
        if pp is None:
            continue
        rp = _solve(remainder, cfg, memo, deadline, budget - 1 - pp.cost)
        if rp is None:
            continue
        # piece と remainder は互いに素な象限なので、どちらを bottom にしても
        # stack() の gap 計算上マージされて元の形に戻る(念のため両順で確認)。
        rebuilt = S.stack(S.parse(rp.key), S.parse(pp.key))
        if S.key_of(rebuilt) == S.key_of(shape):
            rebuilt_ok = True
        else:
            rebuilt = S.stack(S.parse(pp.key), S.parse(rp.key))
            rebuilt_ok = S.key_of(rebuilt) == S.key_of(shape)
        if not rebuilt_ok:
            continue
        cost = pp.cost + rp.cost + 1
        if cost <= budget:
            cands.append(Plan("shape", S.key_of(shape), "stack", "象限パターンごとに作りスタッカーで合成",
                               cost, "stacker", [rp, pp]))
    return cands


# 回転量k(1=時計回り90度, 2=180度, 3=反時計回り90度)だけ全体を先に回してから
# 標準軸({0,1}|{2,3})で2分割・スタッカー合成し、最後にまとめて逆回転する。
# 各半分を個別に最終位置まで回すより、回転を1回に共有できるため安くなることがある。
_ROTATE_FWD: Dict[int, Callable[[S.Shape], S.Shape]] = {1: S.rotate_cw, 2: S.rotate_180, 3: S.rotate_ccw}
_ROTATE_INV: Dict[int, Tuple[Callable[[S.Shape], S.Shape], str, str]] = {
    1: (S.rotate_ccw, "rotateCCW", "rotater_ccw"),
    2: (S.rotate_180, "rotate180", "rotater_180"),
    3: (S.rotate_cw, "rotateCW", "rotater"),
}


def _rotated_isolate_candidates(shape: S.Shape, cfg: SolverConfig, memo, deadline, budget) -> List[Plan]:
    cands = []
    occ = set(_occupied_quadrants(shape))
    if len(occ) < 2:
        return cands
    for k in (1, 2, 3):
        rotated = _ROTATE_FWD[k](shape)
        rocc = set(_occupied_quadrants(rotated))
        for pat in ((0, 1), (2, 3)):
            patset = set(pat)
            if not patset <= rocc or patset == rocc:
                continue
            piece = S._filter_quadrants(rotated, pat)
            remainder = S._filter_quadrants(rotated, tuple(sorted(rocc - patset)))
            if piece is None or remainder is None:
                continue
            pp = _solve(piece, cfg, memo, deadline, budget - 2)
            if pp is None:
                continue
            rp = _solve(remainder, cfg, memo, deadline, budget - 2 - pp.cost)
            if rp is None:
                continue
            rebuilt = S.stack(S.parse(rp.key), S.parse(pp.key))
            if S.key_of(rebuilt) != S.key_of(rotated):
                rebuilt = S.stack(S.parse(pp.key), S.parse(rp.key))
                if S.key_of(rebuilt) != S.key_of(rotated):
                    continue
            stacked_cost = pp.cost + rp.cost + 1
            inv_fn, inv_op, inv_building = _ROTATE_INV[k]
            final_shape = inv_fn(rebuilt)
            if S.key_of(final_shape) != S.key_of(shape):
                continue
            total = stacked_cost + 1
            if total <= budget:
                stacked_plan = Plan("shape", S.key_of(rebuilt), "stack", "標準軸で分けてスタッカーで合成",
                                     stacked_cost, "stacker", [rp, pp])
                cands.append(Plan("shape", S.key_of(final_shape), inv_op, "最後にまとめて回転",
                                   total, inv_building, [stacked_plan]))
    return cands


def _paint_candidates(shape: S.Shape, cfg: SolverConfig, memo, deadline, budget) -> List[Plan]:
    cands = []
    color = _single_color(shape)
    if color is not None and color != "u":
        base = _with_uncolored(shape)
        if S.key_of(base) != S.key_of(shape):
            bp = _solve(base, cfg, memo, deadline, budget - 1)
            if bp is not None:
                cp = _color_plan(color)
                cost = bp.cost + cp.cost + 1
                if cost <= budget:
                    cands.append(Plan("shape", S.key_of(shape), "paint", f"ペインターで{color}に塗装",
                                       cost, "painter", [bp, cp]))

    if cfg.quad_painter:
        qc = _quad_colors(shape)
        if qc is not None and any(c is not None and c != "u" for c in qc):
            base = _with_uncolored(shape)
            if S.key_of(base) != S.key_of(shape):
                bp = _solve(base, cfg, memo, deadline, budget - 1)
                if bp is not None:
                    color_plans = [_color_plan(c) if c else None for c in qc]
                    extra = sum(cp.cost for cp in color_plans if cp is not None)
                    cost = bp.cost + extra + 1
                    if cost <= budget:
                        cands.append(Plan("shape", S.key_of(shape), "paintQuad", "クアッドペインターで象限ごとに塗装",
                                           cost, "painter_quad",
                                           [bp] + [cp for cp in color_plans if cp is not None]))
    return cands


_FAILED_KEY = "\x00failed\x00"


def _solve(shape: Optional[S.Shape], cfg: SolverConfig, memo: Dict[str, Plan],
           deadline: float, budget: int) -> Optional[Plan]:
    if shape is None or budget < 0:
        return None
    _check_deadline(deadline)
    key = S.key_of(shape)

    cached = memo.get(key)
    if cached is not None and cached.cost <= budget:
        return cached

    # 「このシェイプは予算X以下では解なし」を記録し、反復深化で予算が小さいまま
    # 再訪されたときに同じ探索をやり直さないようにする(健全性: 予算が増えれば再探索する)。
    failed: Dict[str, int] = memo.setdefault(_FAILED_KEY, {})  # type: ignore[assignment]
    if budget <= failed.get(key, -1):
        return None

    best: Optional[Plan] = None

    def consider(p: Optional[Plan]) -> None:
        nonlocal best
        if p is not None and p.cost <= budget and (best is None or p.cost < best.cost):
            best = p

    for p in _leaf_candidates(shape, cfg):
        consider(p)

    consider(_pattern_isolate_plan(shape, cfg, memo, deadline, budget))

    for p in _paint_candidates(shape, cfg, memo, deadline, budget):
        consider(p)

    for p in _stack_split_candidates(shape, cfg, memo, deadline, budget):
        consider(p)

    for p in _forced_float_candidates(shape, cfg, memo, deadline, budget):
        consider(p)

    for p in _quadrant_isolate_candidates(shape, cfg, memo, deadline, budget):
        consider(p)

    for p in _rotated_isolate_candidates(shape, cfg, memo, deadline, budget):
        consider(p)

    if best is not None:
        if cached is None or best.cost < cached.cost:
            memo[key] = best
    else:
        failed[key] = max(failed.get(key, -1), budget)
    return best


def solve_with_bound(shape: S.Shape, cfg: SolverConfig, deadline: float,
                      memo: Optional[Dict[str, Plan]] = None) -> Tuple[Optional[Plan], bool]:
    """反復深化本体。(プラン, 最小手数を保証できたか) を返す。
    memo を渡すと後続の実用解探索(construct.find_plan のフォールバック)と
    キャッシュを共有できる。"""
    if memo is None:
        memo = {}
    try:
        for bound in range(0, cfg.max_cost + 1):
            _check_deadline(deadline)
            result = _solve(shape, cfg, memo, deadline, bound)
            if result is not None:
                return result, True
    except _TimeUp:
        pass
    key = S.key_of(shape)
    return memo.get(key), False


def solve_practical(shape: S.Shape, cfg: SolverConfig, deadline: float,
                     memo: Optional[Dict[str, Plan]] = None, budget: int = 120) -> Optional[Plan]:
    """最小保証なしの実用解探索(D-7 のフォールバック)。時間切れは None を返す。"""
    if memo is None:
        memo = {}
    try:
        return _solve(shape, cfg, memo, deadline, budget)
    except _TimeUp:
        return memo.get(S.key_of(shape))


# --- シミュレーション(自己検証用) ---

def simulate(plan: Plan) -> str:
    if plan.kind == "color":
        if plan.op == "mine":
            return plan.key
        a, b = (simulate(i) for i in plan.inputs)
        return S.mix_colors(a, b)

    if plan.op == "mine":
        return plan.key
    if plan.op in ("cut0", "cut1"):
        parent = S.parse(simulate(plan.inputs[0]))
        left, right = S.cut_half(parent)
        out = left if plan.op == "cut0" else right
        if out is None:
            raise S.ShapeError("シミュレーション不整合: カット結果が空です")
        return S.key_of(out)
    if plan.op.startswith("cutQuad"):
        idx = int(plan.op[-1])
        parent = S.parse(simulate(plan.inputs[0]))
        out = S.cut_quad(parent)[idx]
        if out is None:
            raise S.ShapeError("シミュレーション不整合: クアッドカット結果が空です")
        return S.key_of(out)
    if plan.op == "rotateCW":
        return S.key_of(S.rotate_cw(S.parse(simulate(plan.inputs[0]))))
    if plan.op == "rotateCCW":
        return S.key_of(S.rotate_ccw(S.parse(simulate(plan.inputs[0]))))
    if plan.op == "rotate180":
        return S.key_of(S.rotate_180(S.parse(simulate(plan.inputs[0]))))
    if plan.op == "stack":
        bottom = S.parse(simulate(plan.inputs[0]))
        top = S.parse(simulate(plan.inputs[1]))
        return S.key_of(S.stack(bottom, top))
    if plan.op == "paint":
        base = S.parse(simulate(plan.inputs[0]))
        color = simulate(plan.inputs[1])
        return S.key_of(S.paint(base, color))
    if plan.op == "paintQuad":
        base = S.parse(simulate(plan.inputs[0]))
        colors = _quad_colors(S.parse(plan.key))
        return S.key_of(S.paint_quad(base, colors))
    raise S.ShapeError(f"未知の操作です: {plan.op}")


_OP_LABEL = {
    "mine": "採掘",
    "cut0": "カッター(左)",
    "cut1": "カッター(右)",
    "rotateCW": "ロータリーター(時計回り)",
    "rotateCCW": "ロータリーター(反時計回り)",
    "rotate180": "ロータリーター(180度)",
    "stack": "スタッカー",
    "paint": "ペインター",
    "paintQuad": "クアッドペインター",
    "mix": "カラーミキサー",
}


def format_plan(plan: Plan, indent: int = 0) -> str:
    prefix = "  " * indent
    label = _OP_LABEL.get(plan.op, plan.op)
    if plan.op.startswith("cutQuad"):
        label = f"クアッドカッター(象限{plan.op[-1]})"
    line = f"{prefix}{label}: {plan.key} (建物 {plan.cost})"
    lines = [line]
    for i in plan.inputs:
        lines.append(format_plan(i, indent + 1))
    return "\n".join(lines)


def ordered_steps(plan: Plan) -> List[Plan]:
    steps: List[Plan] = []
    for i in plan.inputs:
        steps.extend(ordered_steps(i))
    steps.append(plan)
    return steps
