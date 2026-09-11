"""render.py -- Canvas へのシェイプ描画。本体と同じ配色・同心円レイヤー表現を単純化して再現する。
"""

import math
from typing import Sequence, Union

import shape as S

_COLOR_HEX = {
    "u": "#c8c8c8",
    "r": "#e34545",
    "g": "#54c064",
    "b": "#4a7dda",
    "y": "#e0d030",
    "p": "#c34ad0",
    "c": "#3fc7d0",
    "w": "#f4f4f4",
}

_BG = "#333846"
_OUTLINE = "#11141a"

# gui.py 等、他モジュールから配色を揃えるための公開エイリアス。
COLOR_HEX = _COLOR_HEX
BG = _BG
OUTLINE = _OUTLINE

# 象限ごとの開始角(tkinter create_arc は東=0度・反時計回り)
_QUAD_START = {0: 0, 1: 270, 2: 180, 3: 90}


def draw_subshape_icon(canvas, cx: float, cy: float, s: float, sub: str, fill: str,
                        outline: str = None, tags: Sequence[str] = ()) -> None:
    """(cx,cy) を中心にサイズ s で形状アイコン(丸/角/星/風車)を単独描画する。
    シェイプ描画中の象限マーカーと、GUIの早見表パネルの両方から使う共通部品。"""
    outline = _OUTLINE if outline is None else outline
    if sub == "C":
        canvas.create_oval(cx - s, cy - s, cx + s, cy + s, fill=fill, outline=outline, tags=tags)
    elif sub == "R":
        canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s, fill=fill, outline=outline, tags=tags)
    elif sub == "S":
        pts = []
        for k in range(10):
            rad = s if k % 2 == 0 else s * 0.45
            a = math.pi / 2 + k * math.pi / 5
            pts += [cx + rad * math.cos(a), cy - rad * math.sin(a)]
        canvas.create_polygon(pts, fill=fill, outline=outline, tags=tags)
    else:  # W windmill
        pts = [cx, cy - s, cx + s * 0.9, cy + s * 0.2, cx - s * 0.9, cy + s * 0.2]
        canvas.create_polygon(pts, fill=fill, outline=outline, tags=tags)


def _subshape_marker(canvas, cx: float, cy: float, r: float, q: int, sub: str, fill: str,
                      tags: Sequence[str] = ()) -> None:
    """象限中心付近に、形状を示す小さな目印を重ねて描く(丸/角/星/風車を見分けるため)。"""
    ang = {0: -45, 1: 45, 2: 135, 3: -135}[q]
    mx = cx + r * 0.55 * math.cos(math.radians(-ang))
    my = cy - r * 0.55 * math.sin(math.radians(-ang))
    s = max(3.0, r * 0.14)
    draw_subshape_icon(canvas, mx, my, s, sub, fill, tags=tags)


def draw_shape(canvas, key_or_shape: Union[str, S.Shape], cx: float, cy: float,
               radius: float, tags: Sequence[str] = (), background: bool = True) -> None:
    """(cx,cy) を中心に半径 radius でシェイプを描く。layer0(採掘直後)が内側、上に行くほど外側。"""
    shape = S.parse(key_or_shape) if isinstance(key_or_shape, str) else key_or_shape
    tags = tuple(tags)

    if background:
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                            fill=_BG, outline=_OUTLINE, tags=tags)

    n = len(shape)
    if n == 0:
        return
    for layer_idx in range(n - 1, -1, -1):
        band_r = radius * (layer_idx + 1) / n
        layer = shape[layer_idx]
        for q in range(4):
            cell = layer[q]
            if cell is None:
                continue
            sub, color = cell
            fill = _COLOR_HEX.get(color, _COLOR_HEX["u"])
            canvas.create_arc(cx - band_r, cy - band_r, cx + band_r, cy + band_r,
                               start=_QUAD_START[q], extent=90, style="pieslice",
                               fill=fill, outline=_OUTLINE, tags=tags)
    for layer_idx in range(n):
        band_r = radius * (layer_idx + 1) / n
        layer = shape[layer_idx]
        for q in range(4):
            cell = layer[q]
            if cell is None:
                continue
            sub, color = cell
            _subshape_marker(canvas, cx, cy, band_r, q, sub, fill=_COLOR_HEX.get(color, _COLOR_HEX["u"]),
                              tags=tags)
