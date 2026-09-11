"""main.py -- エントリポイント。引数なしなら GUI 起動、シェイプコードを渡せば
その場でコマンドラインだけで1件計測して終わる(FR-19)。
mod_config.json があれば、GUI/CLIいずれでも起動時に一度だけ適用する。
"""

import sys


def _cli(code: str) -> int:
    import construct
    import shape as S
    import solver

    try:
        sh = S.parse(code)
    except S.ShapeError as e:
        print(f"シェイプコードが不正です: {e}")
        return 1

    cfg = solver.SolverConfig()
    plan, guaranteed = construct.find_plan(sh, cfg, progress=print)
    if plan is None:
        print("解が見つかりませんでした。")
        return 1

    sim = solver.simulate(plan)
    if sim != code:
        print("検証に失敗しました(内部エラー)。")
        return 1

    print()
    print(solver.format_plan(plan))
    print()
    print(f"建物数(延べ): {plan.cost}")
    print(f"建物数(ユニーク): {construct.unique_cost(plan)}")
    print("最小手数を保証" if guaranteed else "実用解(最小保証なし)")
    return 0


def main() -> int:
    import mod_config
    mod_messages = mod_config.apply_mod_config()
    for msg in mod_messages:
        print(f"[mod_config] {msg}")

    if len(sys.argv) > 1:
        return _cli(sys.argv[1])
    import gui
    gui.main(mod_messages=mod_messages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
