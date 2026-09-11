"""construct.py -- solver.py への統合窓口。時間内に最小手数が証明できない場合は
予算を大きく取った1回探索で「実用解(最小保証なし)」を返す(D-7)。
"""

import time
from typing import Callable, Dict, Optional, Tuple

import shape as S
import solver
from solver import Plan, SolverConfig

_FALLBACK_BUDGET = 120


def find_plan(sh: S.Shape, cfg: Optional[SolverConfig] = None,
              progress: Optional[Callable[[str], None]] = None) -> Tuple[Optional[Plan], bool]:
    cfg = cfg or SolverConfig()
    deadline = time.time() + cfg.time_limit
    memo: Dict[str, Plan] = {}

    if progress:
        progress("最小手数を反復深化で探索中...")
    plan, guaranteed = solver.solve_with_bound(sh, cfg, deadline, memo)
    if plan is not None and guaranteed:
        if progress:
            progress(f"最小手数を保証して発見(建物 延べ{plan.cost})")
        return plan, True

    if progress:
        progress("時間内に最小手数を保証できないため、実用解を構成します...")
    fallback_deadline = time.time() + max(cfg.time_limit, 5.0)
    fallback = solver.solve_practical(sh, cfg, fallback_deadline, memo, _FALLBACK_BUDGET)
    if fallback is not None:
        if plan is None or fallback.cost <= plan.cost:
            plan = fallback
    if progress:
        if plan is not None:
            progress(f"実用解(最小保証なし): 建物 延べ{plan.cost}")
        else:
            progress("解が見つかりませんでした")
    return plan, False


def unique_cost(plan: Plan) -> int:
    """ブループリント共有を仮定したユニーク建物数(D-9)。"""
    seen = set()

    def visit(p: Plan) -> int:
        ident = (p.kind, p.key, p.op)
        if ident in seen:
            return 0
        seen.add(ident)
        own = p.cost - sum(c.cost for c in p.inputs)
        return own + sum(visit(c) for c in p.inputs)

    return visit(plan)
