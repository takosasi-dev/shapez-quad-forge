"""batch.py -- 複数の目標シェイプコードをまとめて construct.find_plan で解く(GUIのバッチタブ用)。
GUI ツールキットは import しない(solver.py/throughput.py/construct.py と同じ方針)。
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

import construct
import shape as S
from solver import Plan, SolverConfig


@dataclass
class BatchResult:
    code: str                    # 入力されたシェイプコード(そのまま)
    plan: Optional[Plan]         # 解けたPlan。解なし/エラー時はNone
    guaranteed: bool             # 最小手数を保証できたか(解なし/エラー時はFalse)
    error: Optional[str] = None  # 不正なシェイプコード等のエラーメッセージ(正常時はNone)


def solve_batch(codes: List[str], cfg: SolverConfig,
                 progress: Optional[Callable[[int, int, str], None]] = None) -> List[BatchResult]:
    """codes を順番に1件ずつ construct.find_plan で解く。
    1件が不正なシェイプコード(ShapeError)でも処理を止めず、その件だけ
    BatchResult(error=...) にして次へ進む。
    progress が渡されていれば、1件処理し終えるたびに
    progress(何件目か(1始まり), 全体件数, その件の短い日本語メッセージ) を呼ぶ
    (個々の探索内部の進捗までは渡さなくてよい、1件完了ごとの通知だけでよい)。"""
    total = len(codes)
    results: List[BatchResult] = []
    for i, code in enumerate(codes, start=1):
        try:
            sh = S.parse(code)
        except S.ShapeError as e:
            results.append(BatchResult(code, None, False, error=str(e)))
            if progress:
                progress(i, total, f"{code!r}: エラー({e})")
            continue

        plan, guaranteed = construct.find_plan(sh, cfg)
        results.append(BatchResult(code, plan, guaranteed))
        if progress:
            if plan is None:
                msg = f"{code}: 解が見つかりませんでした"
            elif guaranteed:
                msg = f"{code}: 最小手数を保証(建物 延べ{plan.cost})"
            else:
                msg = f"{code}: 実用解(最小保証なし、建物 延べ{plan.cost})"
            progress(i, total, msg)
    return results


def summarize(results: List[BatchResult]) -> str:
    """結果一覧を日本語の人間可読レポート文字列にする。各行に「コード: 状態(建物延べ数 or 解なし or エラー内容)」、
    最後に解けた件数/全体件数と、解けた分の plan.cost の合計(延べ建物数の単純合計)を書く。
    空リストを渡しても例外にならない。"""
    lines: List[str] = []
    solved = 0
    total_cost = 0
    for r in results:
        if r.error is not None:
            lines.append(f"{r.code}: エラー({r.error})")
        elif r.plan is None:
            lines.append(f"{r.code}: 解なし")
        else:
            status = "最小手数を保証" if r.guaranteed else "実用解(最小保証なし)"
            lines.append(f"{r.code}: 建物 延べ{r.plan.cost}({status})")
            solved += 1
            total_cost += r.plan.cost
    lines.append(f"解けた件数: {solved}/{len(results)}")
    lines.append(f"建物数合計(延べ、解けた分のみ): {total_cost}")
    return "\n".join(lines)
