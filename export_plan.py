"""export_plan.py -- 探索結果の構築手順をテキストファイルへ書き出す。
GUI ツールキットは import しない。手順ツリーの整形自体は solver.format_plan() を
再利用し(再実装しない)、ここではレポートの見出し部分の組み立てと保存だけを行う。
"""

import solver
from solver import Plan


def plan_to_text(plan: Plan, guaranteed: bool, unique_cost: int) -> str:
    """探索結果を人間が読めるレポート文字列にする。"""
    guarantee_text = "最小手数を保証" if guaranteed else "実用解(最小保証なし)"
    lines = [
        "QuadForge 構築手順レポート",
        f"目標シェイプ: {plan.key}",
        f"建物数(延べ): {plan.cost}",
        f"建物数(ユニーク): {unique_cost}",
        guarantee_text,
        "",
        solver.format_plan(plan),
    ]
    return "\n".join(lines)


def save_text(path: str, plan: Plan, guaranteed: bool, unique_cost: int) -> None:
    """plan_to_text() の結果をUTF-8でpathに書き出す。
    書き込み失敗(OSError)は呼び出し側が利用者にエラー表示できるよう、
    ここでは握りつぶさずそのまま伝播させる(黙って保存に失敗すると気付けないため)。
    """
    text = plan_to_text(plan, guaranteed, unique_cost)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
