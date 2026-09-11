"""favorites.py -- よく使うシェイプコードをお気に入りとしてJSONファイルへ
保存・読み込みする。GUI ツールキットは import しない。
"""

import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class Favorite:
    code: str
    note: str = ""


def _default_path() -> str:
    """exe化(PyInstaller)時は実行ファイルと同じフォルダ、ソース実行時はこのファイルと
    同じフォルダの favorites.json を指す。"""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "favorites.json")


def load(path: Optional[str] = None) -> List[Favorite]:
    """お気に入り一覧を読み込む。ファイルが無い、またはJSONとして壊れている
    (壊れた内容・想定外の形)場合は例外を投げず空リストを返す。"""
    path = path or _default_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("code"), str):
            result.append(Favorite(code=item["code"], note=item.get("note", "")))
    return result


def save(favorites: List[Favorite], path: Optional[str] = None) -> None:
    """お気に入り一覧をJSON配列としてUTF-8で書き出す
    (ensure_ascii=Falseで日本語のnoteもそのまま読める形式)。"""
    path = path or _default_path()
    data = [asdict(f) for f in favorites]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add(code: str, note: str = "", path: Optional[str] = None) -> List[Favorite]:
    """codeをお気に入りに追加する。既に同じcodeがあれば何もせずそのまま返す(重複防止)。"""
    path = path or _default_path()
    result = load(path)
    if not any(f.code == code for f in result):
        result.append(Favorite(code=code, note=note))
        save(result, path)
    return result


def remove(code: str, path: Optional[str] = None) -> List[Favorite]:
    """該当codeのお気に入りを取り除く。"""
    path = path or _default_path()
    result = [f for f in load(path) if f.code != code]
    save(result, path)
    return result
