"""shape.py -- シェイプ表現と各建物の演算(唯一の真実)。
tobspr-games/shapez.io の shape_definition.js を Python に移植したもの。
ここでの計算結果が本ツール全体の正とする。他のどのモジュールも import しない。
"""

from typing import List, Optional, Sequence, Tuple

SUBSHAPES = "CRSW"          # C=丸 R=角 S=星 W=風車
COLORS = "urgbypcw"         # u=無色 r g b は原色、y p c w は混色
EMPTY_QUAD = "--"

# 象限インデックス(shape_definition.js の TOP_RIGHT/BOTTOM_RIGHT/BOTTOM_LEFT/TOP_LEFT)
TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT, TOP_LEFT = 0, 1, 2, 3

Cell = Optional[Tuple[str, str]]
Layer = Tuple[Cell, Cell, Cell, Cell]
Shape = Tuple[Layer, ...]


class ShapeError(Exception):
    pass


# --- 色のビット合成(colors.js bitfieldToColor 相当) ---
_BITS_TO_COLOR = {
    0: "u",
    1: "r",
    2: "g",
    4: "b",
    1 | 2: "y",
    1 | 4: "p",
    2 | 4: "c",
    1 | 2 | 4: "w",
}
_COLOR_TO_BITS = {v: k for k, v in _BITS_TO_COLOR.items()}


def mix_colors(a: str, b: str) -> str:
    if a not in COLORS or b not in COLORS:
        raise ShapeError(f"未定義の色: {a!r}, {b!r}")
    return _BITS_TO_COLOR[_COLOR_TO_BITS[a] | _COLOR_TO_BITS[b]]


# 混色の代表的な内訳(y/p/c/w のみ持つ。u/r/g/b は資源そのものなので内訳なし)
_COLOR_RECIPES = {"y": ("r", "g"), "p": ("r", "b"), "c": ("g", "b"), "w": ("y", "b")}


def color_recipe(color: str) -> Optional[Tuple[str, str]]:
    return _COLOR_RECIPES.get(color)


# --- パース / シリアライズ ---

def parse(key: str) -> Shape:
    if not key:
        raise ShapeError("空のシェイプコードです")
    layer_strs = key.split(":")
    if len(layer_strs) > 4:
        raise ShapeError(f"レイヤー数が多すぎます(最大4): {key!r}")
    layers: List[Layer] = []
    for layer_str in layer_strs:
        if len(layer_str) != 8:
            raise ShapeError(f"レイヤーは8文字である必要があります: {layer_str!r}")
        cells: List[Cell] = []
        any_filled = False
        for i in range(4):
            pair = layer_str[i * 2 : i * 2 + 2]
            if pair == EMPTY_QUAD:
                cells.append(None)
                continue
            sub, col = pair[0], pair[1]
            if sub not in SUBSHAPES:
                raise ShapeError(f"未定義の形状記号: {sub!r} in {layer_str!r}")
            if col not in COLORS:
                raise ShapeError(f"未定義の色記号: {col!r} in {layer_str!r}")
            cells.append((sub, col))
            any_filled = True
        if not any_filled:
            raise ShapeError(f"完全に空のレイヤーは許可されません: {layer_str!r}")
        layers.append(tuple(cells))
    return tuple(layers)


def key_of(shape: Shape) -> str:
    def cell_str(c: Cell) -> str:
        return EMPTY_QUAD if c is None else c[0] + c[1]

    return ":".join("".join(cell_str(c) for c in layer) for layer in shape)


# --- 象限フィルタ(cloneFilteredByQuadrants 相当。P-3/P-4) ---

def _filter_quadrants(shape: Shape, keep: Sequence[int]) -> Optional[Shape]:
    keep_set = set(keep)
    new_layers = []
    for layer in shape:
        new_layer = tuple(cell if i in keep_set else None for i, cell in enumerate(layer))
        if any(c is not None for c in new_layer):
            new_layers.append(new_layer)
    if not new_layers:
        return None  # 完全に空 = その出力側からは何も出ない(不正ではない)
    return tuple(new_layers)


def cut_half(shape: Shape) -> Tuple[Optional[Shape], Optional[Shape]]:
    """カッター。戻り値は (スキット0=象限2,3側, スキット1=象限0,1側)。"""
    return _filter_quadrants(shape, (2, 3)), _filter_quadrants(shape, (0, 1))


def cut_quad(shape: Shape) -> Tuple[Optional[Shape], Optional[Shape], Optional[Shape], Optional[Shape]]:
    """クアッドカッター。象限0,1,2,3をそれぞれ単独に切り出す。"""
    return tuple(_filter_quadrants(shape, (i,)) for i in range(4))  # type: ignore[return-value]


# --- 回転(shape_definition.js cloneRotateCW 相当) ---

def rotate_cw(shape: Shape) -> Shape:
    return tuple((layer[3], layer[0], layer[1], layer[2]) for layer in shape)


def rotate_ccw(shape: Shape) -> Shape:
    return tuple((layer[1], layer[2], layer[3], layer[0]) for layer in shape)


def rotate_180(shape: Shape) -> Shape:
    return tuple((layer[2], layer[3], layer[0], layer[1]) for layer in shape)


# --- スタック(cloneAndStackWith 相当。P-5/P-6/P-7を厳密に再現) ---

def stack(bottom: Shape, top: Shape) -> Shape:
    if len(bottom) == 0 or len(top) == 0:
        raise ShapeError("空のシェイプはスタックできません")

    bottom_highest = [-1, -1, -1, -1]
    for layer_idx in range(len(bottom) - 1, -1, -1):
        for q in range(4):
            if bottom[layer_idx][q] is not None and bottom_highest[q] < layer_idx:
                bottom_highest[q] = layer_idx

    top_lowest = [4, 4, 4, 4]
    for layer_idx in range(len(top)):
        for q in range(4):
            if top[layer_idx][q] is not None and top_lowest[q] > layer_idx:
                top_lowest[q] = layer_idx

    gaps = [top_lowest[q] - bottom_highest[q] for q in range(4)]
    merge_at = max(1 - min(gaps), 0)

    merged: List[List[Cell]] = [list(layer) for layer in bottom]
    needed = merge_at + len(top)
    while len(merged) < needed:
        merged.append([None, None, None, None])

    for layer_idx in range(len(top)):
        target = merge_at + layer_idx
        for q in range(4):
            top_cell = top[layer_idx][q]
            if top_cell is None:
                continue
            if merged[target][q] is not None:
                raise ShapeError("スタック処理でシェイプが失われました(内部不整合)")
            merged[target][q] = top_cell

    merged = merged[:4]  # P-6: 4層で切り捨て
    return tuple(tuple(layer) for layer in merged)


# --- ペイント(cloneAndPaintWith / cloneAndPaintWith4Colors 相当。P-8) ---

def paint(shape: Shape, color: str) -> Shape:
    if color not in COLORS:
        raise ShapeError(f"未定義の色: {color!r}")
    return tuple(
        tuple((cell[0], color) if cell is not None else None for cell in layer)
        for layer in shape
    )


def paint_quad(shape: Shape, colors: Sequence[Optional[str]]) -> Shape:
    if len(colors) != 4:
        raise ShapeError("paint_quad には象限ごとに4色指定してください")
    for c in colors:
        if c is not None and c not in COLORS:
            raise ShapeError(f"未定義の色: {c!r}")
    return tuple(
        tuple(
            (cell[0], colors[q]) if cell is not None and colors[q] is not None else cell
            for q, cell in enumerate(layer)
        )
        for layer in shape
    )
