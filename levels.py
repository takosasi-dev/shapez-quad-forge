"""levels.py -- 全26レベルの目標シェイプ・必要個数・報酬(本体データそのまま転記)。
出典: tobspr-games/shapez.io src/js/game/modes/levels.js の STANDALONE_LEVELS。
中国版限定シェイプ(china variant)は使わず、通常版のシェイプ文字列を採用している。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LevelGoal:
    level: int
    shape: str          # 目標シェイプコード
    required: int       # 必要個数(Lv14のみ「個/秒」、他は延べ個数)
    reward: str          # 報酬ID(本体の enumHubGoalRewards のキー名そのまま)
    per_second: bool = False  # Lv14 は throughputOnly


LEVELS = (
    LevelGoal(1, "CuCuCuCu", 30, "reward_cutter_and_trash"),
    LevelGoal(2, "----CuCu", 40, "no_reward"),
    LevelGoal(3, "RuRuRuRu", 70, "reward_balancer"),
    LevelGoal(4, "RuRu----", 70, "reward_rotater"),
    LevelGoal(5, "Cu----Cu", 170, "reward_tunnel"),
    LevelGoal(6, "Cu------", 270, "reward_painter"),
    LevelGoal(7, "CrCrCrCr", 300, "reward_rotater_ccw"),
    LevelGoal(8, "RbRb----", 480, "reward_mixer"),
    LevelGoal(9, "CpCpCpCp", 600, "reward_merger"),
    LevelGoal(10, "ScScScSc", 800, "reward_stacker"),
    LevelGoal(11, "CgScScCg", 1000, "reward_miner_chainable"),
    LevelGoal(12, "CbCbCbRb:CwCwCwCw", 1000, "reward_blueprints"),
    LevelGoal(13, "RpRpRpRp:CwCwCwCw", 3800, "reward_underground_belt_tier_2"),
    LevelGoal(14, "--Cg----:--Cr----", 8, "reward_belt_reader", per_second=True),
    LevelGoal(15, "SrSrSrSr:CyCyCyCy", 10000, "reward_storage"),
    LevelGoal(16, "SrSrSrSr:CyCyCyCy:SwSwSwSw", 6000, "reward_cutter_quad"),
    LevelGoal(17, "CbRbRbCb:CwCwCwCw:WbWbWbWb", 20000, "reward_painter_double"),
    LevelGoal(18, "Sg----Sg:CgCgCgCg:--CyCy--", 20000, "reward_rotater_180"),
    LevelGoal(19, "CpRpCp--:SwSwSwSw", 25000, "reward_splitter"),
    LevelGoal(20, "RuCw--Cw:----Ru--", 25000, "reward_wires_painter_and_levers"),
    LevelGoal(21, "CrCwCrCw:CwCrCwCr:CrCwCrCw:CwCrCwCr", 25000, "reward_filter"),
    LevelGoal(22, "Cg----Cr:Cw----Cw:Sy------:Cy----Cy", 25000, "reward_constant_signal"),
    LevelGoal(23, "CcSyCcSy:SyCcSyCc:CcSyCcSy", 25000, "reward_display"),
    LevelGoal(24, "CcRcCcRc:RwCwRwCw:Sr--Sw--:CyCyCyCy", 25000, "reward_logic_gates"),
    LevelGoal(25, "Rg--Rg--:CwRwCwRw:--Rg--Rg", 25000, "reward_virtual_processing"),
    LevelGoal(26, "CbCuCbCu:Sr------:--CrSrCr:CwCwCwCw", 50000, "reward_freeplay"),
)

LEVEL_BY_NUMBER = {lv.level: lv for lv in LEVELS}
