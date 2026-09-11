"""throughput.py -- 建物速度とアップグレード段階から工事見積もりを出す。
数値の出典: tobspr-games/shapez.io src/js/core/config.js の
globalConfig.beltSpeedItemsPerSecond / buildingSpeeds、および
src/js/game/modes/regular.js の fixedImprovements(P-10〜P-12)。
GUI ツールキットは import しない。
"""

import math
from typing import Dict, Tuple

from solver import Plan

BELT_SPEED = 2.0  # 個/秒

# 建物ID -> ベルト速度に対する比率
BUILDING_RATIO: Dict[str, float] = {
    "miner": 1 / 5,
    "cutter": 1 / 4,
    "cutter_quad": 1 / 4,
    "rotater": 1 / 1,
    "stacker": 1 / 8,
    "painter": 1 / 6,
    "painter_quad": 1 / 2,
    "mixer": 1 / 5,
}

# 建物ID -> アップグレード系統(ベルト系/採掘機/加工機/塗装の4系統)
BUILDING_CATEGORY: Dict[str, str] = {
    "miner": "miner",
    "cutter": "processors",
    "cutter_quad": "processors",
    "rotater": "processors",
    "stacker": "processors",
    "mixer": "processors",
    "painter": "painting",
    "painter_quad": "painting",
}

_TIER_MULTIPLIERS = [1.0]
for _step in (0.5, 0.5, 1, 1, 2, 1, 1):
    _TIER_MULTIPLIERS.append(_TIER_MULTIPLIERS[-1] + _step)
# [1.0, 1.5, 2, 3, 4, 6, 7, 8]


def multiplier(upgrade: str, tier: int) -> float:
    if not 0 <= tier <= 7:
        raise ValueError(f"アップグレード段階は0〜7です: {tier}")
    return _TIER_MULTIPLIERS[tier]


def speed(building: str, tiers: Dict[str, int]) -> float:
    ratio = BUILDING_RATIO[building]
    category = BUILDING_CATEGORY[building]
    tier = tiers.get(category, 0)
    return BELT_SPEED * ratio * multiplier(category, tier)


def plan_requirements(plan: Plan, rate: float, tiers: Dict[str, int]) -> Tuple[Dict[str, int], Dict[str, float]]:
    """(建物ID -> 必要棟数, 原材料シェイプ/色キー -> 必要レート) を返す。
    同じ建物IDでも節点ごとに独立した物理的な建物とみなし、節点単位で切り上げてから合算する。
    """
    building_counts: Dict[str, int] = {}
    material_rates: Dict[str, float] = {}

    def visit(p: Plan, r: float) -> None:
        if p.building:
            bspeed = speed(p.building, tiers)
            building_counts[p.building] = building_counts.get(p.building, 0) + math.ceil(r / bspeed)
        if p.op == "mine":
            material_rates[p.key] = material_rates.get(p.key, 0.0) + r
        for child in p.inputs:
            visit(child, r)

    visit(plan, rate)
    return building_counts, material_rates
