"""mod_config.py -- mod_config.json による拡張読み込み(カスタム形状・色・レベル)。
バニラ定義(shape.SUBSHAPES/COLORS, render.COLOR_HEX, levels.LEVELS/LEVEL_BY_NUMBER)を
壊さずに拡張する。ファイル不在・JSON破損・スキーマ不正はすべて握りつぶし、可能な範囲だけ適用する。
GUIツールキットは使わない。標準ライブラリのみ。
"""

import json
import re
from typing import List, Optional

import levels as L
import render
import shape as S

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def config_path() -> str:
    """mod_config.json を探すパス。exe化(PyInstaller)時は実行ファイルと同じフォルダ、
    ソース実行時はこのファイルと同じフォルダを見る。"""
    import sys, os
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "mod_config.json")


def _apply_subshapes(raw, messages: List[str]) -> None:
    """半角英大文字1文字のみ有効。既存記号・重複は無視。"""
    if not isinstance(raw, str):
        return
    added = ""
    for ch in raw:
        if "A" <= ch <= "Z" and ch not in S.SUBSHAPES and ch not in added:
            added += ch
    if added:
        S.SUBSHAPES = S.SUBSHAPES + added
        messages.append(f"形状記号を追加しました: {added}")


def _apply_colors(raw, messages: List[str]) -> None:
    """キーは半角英小文字1文字、値は #rrggbb 形式のみ有効。既存記号は無視。"""
    if not isinstance(raw, dict):
        return
    added = []
    for key, hexval in raw.items():
        if not (isinstance(key, str) and len(key) == 1 and "a" <= key <= "z"):
            continue
        if key in S.COLORS:
            continue
        if not (isinstance(hexval, str) and _HEX_RE.match(hexval)):
            continue
        S.COLORS = S.COLORS + key
        render.COLOR_HEX[key] = hexval
        added.append(key)
    if added:
        messages.append(f"色記号を追加しました: {', '.join(added)}")


def _apply_levels(raw, messages: List[str]) -> None:
    """level/shape必須、shapeはS.parse()でバリデーション。不正な1件だけ無視して継続。
    同じlevel番号は上書き。適用後はLEVELSをlevel昇順tupleに再構築する。"""
    if not isinstance(raw, list):
        return
    by_number = dict(L.LEVEL_BY_NUMBER)
    applied = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            level = entry["level"]
            shape_code = entry["shape"]
        except KeyError:
            continue
        if not (isinstance(level, int) and isinstance(shape_code, str)):
            continue
        required = entry.get("required", 1)
        reward = entry.get("reward", "mod")
        per_second = entry.get("per_second", False)
        try:
            S.parse(shape_code)  # 拡張済みのSUBSHAPES/COLORSでバリデーションのみ行う
        except S.ShapeError:
            continue
        by_number[level] = L.LevelGoal(level, shape_code, required, reward, per_second)
        applied.append(level)
    if applied:
        L.LEVEL_BY_NUMBER = by_number
        L.LEVELS = tuple(sorted(by_number.values(), key=lambda lv: lv.level))
        messages.append(f"レベルを追加/上書きしました: {', '.join(str(n) for n in applied)}")


def apply_mod_config(path: Optional[str] = None) -> List[str]:
    """path省略時は config_path() を使う。ファイルが無い/JSONとして壊れている/中身が
    スキーマに合わない場合は例外を投げず、可能な範囲だけ適用して残りは無視する。
    適用した内容を人間可読な日本語メッセージのリストで返す(何も適用しなければ空リスト)。
    呼び出し順序の制約: subshapes/colors の拡張を levels のバリデーションより先に行う
    (mod が追加した記号を使うレベルのシェイプコードを正しく parse できるようにするため)。
    """
    if path is None:
        path = config_path()
    messages: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return messages
    if not isinstance(data, dict):
        return messages

    _apply_subshapes(data.get("subshapes"), messages)
    _apply_colors(data.get("colors"), messages)
    _apply_levels(data.get("levels"), messages)
    return messages
