"""gui.py -- tkinter によるメイン画面。探索は別スレッドで行い、進捗は Queue 経由で受け取る。
"""

import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import batch
import construct
import export_plan
import favorites
import levels
import render
import shape as S
import solver
import throughput as T

_SUBSHAPE_CYCLE = [None] + list(S.SUBSHAPES)  # mod_config.py で追加された形状も自動で巡回対象になる
_COLORS = list(S.COLORS)
_SUBSHAPE_NAMES = {"C": "丸", "R": "角", "S": "星", "W": "風車"}
_COLOR_NAMES = {"u": "無色", "r": "赤", "g": "緑", "b": "青",
                "y": "黄", "p": "紫", "c": "シアン", "w": "白"}


def _lighten(hex_color: str, amount: float = 0.28) -> str:
    """ホバー時に少し明るくした色を返す(見た目のみのフィードバック)。"""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"

# 配色パレット(shapez.io の落ち着いたダーク系UIを意識した配色)。
_PALETTE = {
    "bg": "#1e222b",
    "panel": "#262b36",
    "panel_alt": "#2f3542",
    "text": "#e8ebf0",
    "text_dim": "#8f97a8",
    "accent": "#4fd1c5",
    "accent_dark": "#2f9e94",
    "accent_fg": "#0c1418",
    "success": "#5cd68c",
    "error": "#ef6a6a",
    "canvas_bg": render.BG,
    "outline": render.OUTLINE,
}

_STATUS_STYLES = {"info": "StatusInfo.TLabel", "run": "StatusRun.TLabel",
                   "ok": "StatusOk.TLabel", "err": "StatusErr.TLabel"}


def _apply_theme(root: tk.Tk) -> None:
    """ttk.Style と既定フォントをまとめて設定する(見た目のみで、挙動は変えない)。"""
    base_font = ("Yu Gothic UI", 10)
    heading_font = ("Yu Gothic UI", 11, "bold")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=base_font[0], size=base_font[1])
        except tk.TclError:
            pass
    root.option_add("*Font", base_font)
    root.configure(bg=_PALETTE["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    p = _PALETTE
    style.configure(".", background=p["bg"], foreground=p["text"], font=base_font)
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("TLabelframe", background=p["panel"], foreground=p["text"], relief="flat", borderwidth=1)
    style.configure("TLabelframe.Label", background=p["panel"], foreground=p["accent"], font=heading_font)
    style.configure("TNotebook", background=p["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=p["panel"], foreground=p["text_dim"],
                    padding=(16, 8), font=base_font)
    style.map("TNotebook.Tab",
              background=[("selected", p["accent"])],
              foreground=[("selected", p["accent_fg"])])
    style.configure("TButton", background=p["accent"], foreground=p["accent_fg"],
                    padding=(10, 6), relief="flat", font=heading_font)
    style.map("TButton",
              background=[("disabled", p["text_dim"]), ("active", p["accent_dark"])],
              foreground=[("disabled", p["panel"])])
    style.configure("TEntry", fieldbackground=p["panel_alt"], foreground=p["text"],
                    insertcolor=p["text"], bordercolor=p["accent_dark"])
    style.configure("TSpinbox", fieldbackground=p["panel_alt"], foreground=p["text"],
                     arrowcolor=p["text"])
    style.configure("TCheckbutton", background=p["panel"], foreground=p["text"])
    style.map("TCheckbutton", background=[("active", p["panel"])], indicatorcolor=[("selected", p["accent"])])
    style.configure("TRadiobutton", background=p["panel"], foreground=p["text"])
    style.map("TRadiobutton", background=[("active", p["panel"])], indicatorcolor=[("selected", p["accent"])])
    style.configure("TScrollbar", background=p["panel"], troughcolor=p["bg"], arrowcolor=p["text"])
    style.configure("Treeview", background=p["panel_alt"], fieldbackground=p["panel_alt"],
                    foreground=p["text"], rowheight=24, font=base_font)
    style.configure("Treeview.Heading", background=p["panel"], foreground=p["accent"], font=heading_font)
    style.map("Treeview", background=[("selected", p["accent_dark"])], foreground=[("selected", p["text"])])

    style.configure("StatusInfo.TLabel", background=p["bg"], foreground=p["text_dim"])
    style.configure("StatusRun.TLabel", background=p["bg"], foreground=p["accent"])
    style.configure("StatusOk.TLabel", background=p["bg"], foreground=p["success"], font=heading_font)
    style.configure("StatusErr.TLabel", background=p["bg"], foreground=p["error"], font=heading_font)
    style.configure("ResultBig.TLabel", background=p["panel"], foreground=p["text"], font=heading_font)
    style.configure("Hint.TLabel", background=p["panel"], foreground=p["text_dim"], font=("Yu Gothic UI", 8))

    # LabelFrame の内側(パネル背景)に置く部品専用のスタイル。
    style.configure("Panel.TFrame", background=p["panel"])
    style.configure("Panel.TLabel", background=p["panel"], foreground=p["text"])

    # 探索中であることを動きで示すプログレスバー。
    style.configure("Horizontal.TProgressbar", troughcolor=p["panel_alt"], background=p["accent"],
                    bordercolor=p["panel_alt"], lightcolor=p["accent"], darkcolor=p["accent"])

    # 結果パネルは成功/失敗で枠の色ごと変える(状態がひと目で分かるように)。
    for tag, col in (("Ok", p["success"]), ("Err", p["error"])):
        style.configure(f"Result{tag}.TLabelframe", background=p["panel"], relief="flat", borderwidth=2)
        style.configure(f"Result{tag}.TLabelframe.Label", background=p["panel"], foreground=col, font=heading_font)


def _cell_button_colors(cell) -> tuple:
    """グリッド編集ボタンの背景/文字色を、置かれている色に合わせて決める(見た目だけの追加情報)。"""
    if cell is None:
        return _PALETTE["panel_alt"], _PALETTE["text_dim"]
    _, color = cell
    bg = render.COLOR_HEX.get(color, render.COLOR_HEX["u"])
    fg = "#14181d" if color in ("u", "y", "w", "g") else "#f4f4f4"
    return bg, fg


class QuadForgeApp:
    def __init__(self, root: tk.Tk, mod_messages: Optional[List[str]] = None) -> None:
        self.root = root
        root.title("QuadForge -- shapez.io 工程計算ツール")
        root.geometry("1220x930")
        root.minsize(1000, 700)
        _apply_theme(root)

        self.grid_cells = [[None for _ in range(4)] for _ in range(4)]  # [layer][quad] -> (sub,color) or None
        self.current_color = tk.StringVar(value="u")
        self.quad_cutter = tk.BooleanVar(value=False)
        self.quad_painter = tk.BooleanVar(value=False)
        self.windmill_patch = tk.BooleanVar(value=True)
        self.time_limit = tk.DoubleVar(value=20.0)
        self.max_cost = tk.IntVar(value=24)
        self.status_text = tk.StringVar(value="待機中")
        self.code_var = tk.StringVar(value="")

        self.last_plan = None
        self.last_guaranteed = False
        self._search_thread = None
        self._progress_queue: "queue.Queue[object]" = queue.Queue()
        self._search_buttons = []
        self._diagram_gen = 0
        self.favorites: List[favorites.Favorite] = favorites.load()
        self._batch_thread = None
        self._batch_queue: "queue.Queue[object]" = queue.Queue()
        self._last_batch_results = []

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True)
        self.tab_solve = ttk.Frame(nb)
        self.tab_throughput = ttk.Frame(nb)
        self.tab_levels = ttk.Frame(nb)
        self.tab_batch = ttk.Frame(nb)
        nb.add(self.tab_solve, text="シェイプ編集・探索")
        nb.add(self.tab_throughput, text="生産比率")
        nb.add(self.tab_levels, text="レベル一覧")
        nb.add(self.tab_batch, text="バッチ計算")

        self._build_solve_tab()
        self._build_throughput_tab()
        self._build_levels_tab()
        self._build_batch_tab()

        self._sync_grid_to_code()
        if mod_messages:
            self._set_status(f"mod設定を適用しました({len(mod_messages)}件): " + " / ".join(mod_messages), "ok")

    # --- タブ1: シェイプ編集・探索 ---

    def _build_solve_tab(self) -> None:
        f = self.tab_solve
        p = _PALETTE

        left = ttk.Frame(f)
        left.pack(side="left", fill="y", padx=10, pady=10)

        code_frame = ttk.Frame(left)
        code_frame.pack(fill="x")
        ttk.Label(code_frame, text="シェイプコード:").pack(side="left")
        entry = ttk.Entry(code_frame, textvariable=self.code_var, width=28)
        entry.pack(side="left", padx=4)
        ttk.Button(code_frame, text="読込", command=self._load_code_into_grid).pack(side="left")

        fav_frame = ttk.Frame(left)
        fav_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(fav_frame, text="★ お気に入りに追加", command=self._add_favorite).pack(side="left")
        self.favorite_var = tk.StringVar()
        self.favorite_combo = ttk.Combobox(fav_frame, textvariable=self.favorite_var, state="readonly", width=20)
        self.favorite_combo.pack(side="left", padx=4)
        ttk.Button(fav_frame, text="読込", command=self._load_favorite).pack(side="left")
        ttk.Button(fav_frame, text="削除", command=self._remove_favorite).pack(side="left")
        self._refresh_favorite_combo()

        grid_frame = ttk.LabelFrame(left, text="① 4層×4象限クリック編集(層0=採掘直後/内側)", padding=8)
        grid_frame.pack(fill="x", pady=6)
        self.cell_buttons = []
        for layer in range(4):
            row = []
            rf = ttk.Frame(grid_frame, style="Panel.TFrame")
            rf.pack(pady=1)
            ttk.Label(rf, text=f"層{layer}", width=4, style="Panel.TLabel").pack(side="left")
            for q in range(4):
                b = tk.Button(rf, text="空", width=5, relief="flat", bd=0,
                               font=("Yu Gothic UI", 10, "bold"),
                               bg=p["panel_alt"], fg=p["text_dim"],
                               activebackground=p["accent_dark"], activeforeground=p["accent_fg"],
                               highlightthickness=1, highlightbackground=p["outline"],
                               cursor="hand2",
                               command=lambda l=layer, qq=q: self._cycle_cell(l, qq))
                b.pack(side="left", padx=2, pady=2)
                b.bind("<Enter>", lambda e, l=layer, qq=q: self._on_cell_hover(l, qq, True))
                b.bind("<Leave>", lambda e, l=layer, qq=q: self._on_cell_hover(l, qq, False))
                row.append(b)
            self.cell_buttons.append(row)
        ttk.Label(grid_frame, text="クリックのたびに 空→丸→角→星→風車→空 と切り替わります",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        color_frame = ttk.LabelFrame(left, text="② 配置する色を選ぶ", padding=6)
        color_frame.pack(fill="x", pady=6)
        color_row = ttk.Frame(color_frame, style="Panel.TFrame")
        color_row.pack()
        self.color_buttons = {}
        for c in _COLORS:
            hexcol = render.COLOR_HEX.get(c, render.COLOR_HEX["u"])
            fg = "#14181d" if c in ("u", "y", "w", "g") else "#f4f4f4"
            b = tk.Button(color_row, text=_COLOR_NAMES.get(c, c), width=5, relief="flat", bd=0,
                           font=("Yu Gothic UI", 9, "bold"), bg=hexcol, fg=fg,
                           activebackground=hexcol, activeforeground=fg,
                           highlightthickness=1, highlightbackground=p["panel"],
                           cursor="hand2", command=lambda cc=c: self._select_color(cc))
            b.pack(side="left", padx=2, pady=2)
            b.bind("<Enter>", lambda e, cc=c: self._on_color_hover(cc, True))
            b.bind("<Leave>", lambda e, cc=c: self._on_color_hover(cc, False))
            self.color_buttons[c] = b
        self._select_color(self.current_color.get())

        self._build_legend(left)

        opt_frame = ttk.LabelFrame(left, text="③ 解禁状況・探索設定", padding=6)
        opt_frame.pack(fill="x", pady=6)
        ttk.Checkbutton(opt_frame, text="クアッドカッター(Lv16)", variable=self.quad_cutter).pack(anchor="w")
        ttk.Checkbutton(opt_frame, text="クアッドペインター(Lv20)", variable=self.quad_painter).pack(anchor="w")
        ttk.Checkbutton(opt_frame, text="風車パッチを原始として扱う", variable=self.windmill_patch).pack(anchor="w")
        tf = ttk.Frame(opt_frame, style="Panel.TFrame")
        tf.pack(fill="x", pady=(6, 0))
        ttk.Label(tf, text="制限時間(秒)", style="Panel.TLabel").pack(side="left")
        ttk.Entry(tf, textvariable=self.time_limit, width=6).pack(side="left", padx=(4, 12))
        ttk.Label(tf, text="最大建物数", style="Panel.TLabel").pack(side="left")
        ttk.Entry(tf, textvariable=self.max_cost, width=6).pack(side="left", padx=4)
        ttk.Label(opt_frame, text="※レベル一覧から読み込むと到達レベルに応じて自動設定されます",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=4)
        search_btn = ttk.Button(btn_frame, text="④ 探索開始", command=self._start_search)
        search_btn.pack(side="left")
        self._search_buttons.append(search_btn)
        export_btn = ttk.Button(btn_frame, text="手順を書き出し", command=self._export_plan)
        export_btn.pack(side="left", padx=(6, 0))
        self.progress_bar = ttk.Progressbar(btn_frame, mode="indeterminate", length=150)
        self.status_label = ttk.Label(left, textvariable=self.status_text, style="StatusInfo.TLabel")
        self.status_label.pack(anchor="w", pady=4)

        right = ttk.Frame(f)
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        preview_frame = ttk.LabelFrame(right, text="プレビュー", padding=10)
        preview_frame.pack(fill="x")
        self.preview_canvas = tk.Canvas(preview_frame, width=140, height=140,
                                          bg=p["canvas_bg"], highlightthickness=0)
        self.preview_canvas.pack()

        self.result_frame = ttk.LabelFrame(right, text="結果", padding=10)
        self.result_frame.pack(fill="both", pady=8)
        self.result_label = ttk.Label(self.result_frame, text="まだ探索していません", style="ResultBig.TLabel")
        self.result_label.pack(anchor="w")

        diagram_frame = ttk.LabelFrame(right, text="手順図(入力シェイプ -> 建物 -> 出力シェイプ)", padding=6)
        diagram_frame.pack(fill="both", expand=True)
        self.diagram_canvas = tk.Canvas(diagram_frame, bg=p["canvas_bg"], highlightthickness=0, height=160)
        diagram_scroll = ttk.Scrollbar(diagram_frame, orient="horizontal", command=self.diagram_canvas.xview)
        self.diagram_canvas.configure(xscrollcommand=diagram_scroll.set)
        self.diagram_canvas.pack(fill="both", expand=True, side="top")
        diagram_scroll.pack(fill="x", side="bottom")

        tree_frame = ttk.LabelFrame(right, text="ツリー表示", padding=6)
        tree_frame.pack(fill="both", expand=True, pady=8)
        self.tree_text = tk.Text(tree_frame, height=10, relief="flat", bd=0, wrap="none",
                                   bg=p["panel_alt"], fg=p["text"], insertbackground=p["text"],
                                   font=("Consolas", 10), padx=8, pady=6)
        self.tree_text.pack(fill="both", expand=True)

    def _build_legend(self, parent: tk.Widget) -> None:
        """形状(丸/角/星/風車)と色の記号早見表。グリッド編集の記号が何を表すか一目で分かるように。"""
        p = _PALETTE
        legend = ttk.LabelFrame(parent, text="形・色 早見表", padding=6)
        legend.pack(fill="x", pady=6)

        def swatch_rows(items, columns):
            for start in range(0, len(items), columns):
                rf = ttk.Frame(legend, style="Panel.TFrame")
                rf.pack(fill="x", pady=2)
                for draw_icon, code, name in items[start:start + columns]:
                    cell = ttk.Frame(rf, style="Panel.TFrame")
                    cell.pack(side="left", padx=6)
                    cv = tk.Canvas(cell, width=24, height=24, bg=p["panel"], highlightthickness=0)
                    cv.pack()
                    draw_icon(cv)
                    ttk.Label(cell, text=f"{code}:{name}", style="Panel.TLabel",
                              font=("Yu Gothic UI", 9)).pack()

        shape_items = [
            (lambda cv, sub=sub: render.draw_subshape_icon(cv, 12, 12, 9, sub, p["text"]),
             sub, _SUBSHAPE_NAMES.get(sub, sub))
            for sub in S.SUBSHAPES
        ]
        swatch_rows(shape_items, 4)

        color_items = [
            (lambda cv, col=col: cv.create_oval(3, 3, 21, 21, fill=render.COLOR_HEX.get(col, render.COLOR_HEX["u"]), outline=p["outline"]),
             col, _COLOR_NAMES.get(col, col))
            for col in _COLORS
        ]
        swatch_rows(color_items, 4)

        def small_swatch(parent_, code):
            cell = tk.Canvas(parent_, width=16, height=16, bg=p["panel"], highlightthickness=0)
            cell.pack(side="left")
            cell.create_oval(2, 2, 14, 14, fill=render.COLOR_HEX.get(code, render.COLOR_HEX["u"]), outline=p["outline"])

        ttk.Label(legend, text="混色の作り方(ミキサーで合成)", style="Panel.TLabel",
                  font=("Yu Gothic UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
        mixed = [col for col in _COLORS if S.color_recipe(col) is not None]
        for start in range(0, len(mixed), 2):
            pair_row = ttk.Frame(legend, style="Panel.TFrame")
            pair_row.pack(fill="x", pady=1)
            for col in mixed[start:start + 2]:
                a, b = S.color_recipe(col)
                entry = ttk.Frame(pair_row, style="Panel.TFrame")
                entry.pack(side="left", padx=(0, 14))
                small_swatch(entry, col)
                ttk.Label(entry, text=f"{col}=", style="Panel.TLabel",
                          font=("Yu Gothic UI", 9)).pack(side="left")
                small_swatch(entry, a)
                ttk.Label(entry, text="+", style="Panel.TLabel",
                          font=("Yu Gothic UI", 9)).pack(side="left")
                small_swatch(entry, b)

    def _select_color(self, c: str) -> None:
        self.current_color.set(c)
        for cc, btn in self.color_buttons.items():
            selected = cc == c
            btn.config(highlightbackground=_PALETTE["accent"] if selected else _PALETTE["panel"],
                       highlightthickness=3 if selected else 1)

    def _on_color_hover(self, c: str, entering: bool) -> None:
        btn = self.color_buttons[c]
        base = render.COLOR_HEX.get(c, render.COLOR_HEX["u"])
        btn.config(bg=_lighten(base) if entering else base)

    def _on_cell_hover(self, layer: int, q: int, entering: bool) -> None:
        btn = self.cell_buttons[layer][q]
        bg, _fg = _cell_button_colors(self.grid_cells[layer][q])
        btn.config(bg=_lighten(bg) if entering else bg)

    def _cycle_cell(self, layer: int, q: int) -> None:
        cur = self.grid_cells[layer][q]
        idx = _SUBSHAPE_CYCLE.index(cur[0]) if cur else 0
        nxt = _SUBSHAPE_CYCLE[(idx + 1) % len(_SUBSHAPE_CYCLE)]
        self.grid_cells[layer][q] = None if nxt is None else (nxt, self.current_color.get())
        self._refresh_cell_buttons()
        self._sync_grid_to_code()

    def _refresh_cell_buttons(self) -> None:
        for layer in range(4):
            for q in range(4):
                cell = self.grid_cells[layer][q]
                btn = self.cell_buttons[layer][q]
                bg, fg = _cell_button_colors(cell)
                text = "空" if cell is None else cell[0] + cell[1]
                btn.config(text=text, bg=bg, fg=fg, activebackground=bg)

    def _grid_to_shape_or_none(self):
        layers = []
        for layer in range(4):
            row = self.grid_cells[layer]
            if not any(c is not None for c in row):
                continue
            layers.append(tuple(row))
        if not layers:
            return None
        return tuple(layers)

    def _sync_grid_to_code(self) -> None:
        sh = self._grid_to_shape_or_none()
        self.code_var.set(S.key_of(sh) if sh else "")
        self._update_preview()

    def _load_code_into_grid(self) -> None:
        code = self.code_var.get().strip()
        if not code:
            return
        try:
            sh = S.parse(code)
        except S.ShapeError as e:
            messagebox.showerror("不正なシェイプコード", str(e))
            return
        self.grid_cells = [[None, None, None, None] for _ in range(4)]
        for layer_idx, layer in enumerate(sh):
            for q in range(4):
                self.grid_cells[layer_idx][q] = layer[q]
        self._refresh_cell_buttons()
        self._update_preview()

    # --- お気に入り ---

    def _favorite_display(self, fav: favorites.Favorite) -> str:
        return f"{fav.code} ({fav.note})" if fav.note else fav.code

    def _refresh_favorite_combo(self) -> None:
        values = [self._favorite_display(f) for f in self.favorites]
        self.favorite_combo.configure(values=values)
        if not values:
            self.favorite_var.set("")
        elif self.favorite_var.get() not in values:
            self.favorite_var.set(values[0])

    def _add_favorite(self) -> None:
        code = self.code_var.get().strip()
        if not code:
            messagebox.showinfo("お気に入り", "シェイプコードが空です。")
            return
        try:
            S.parse(code)
        except S.ShapeError as e:
            messagebox.showerror("不正なシェイプコード", str(e))
            return
        try:
            self.favorites = favorites.add(code)
        except OSError as e:
            messagebox.showerror("保存に失敗しました", str(e))
            return
        self._refresh_favorite_combo()

    def _load_favorite(self) -> None:
        sel = self.favorite_var.get()
        for fav in self.favorites:
            if self._favorite_display(fav) == sel:
                self.code_var.set(fav.code)
                self._load_code_into_grid()
                return

    def _remove_favorite(self) -> None:
        sel = self.favorite_var.get()
        for fav in self.favorites:
            if self._favorite_display(fav) == sel:
                try:
                    self.favorites = favorites.remove(fav.code)
                except OSError as e:
                    messagebox.showerror("削除に失敗しました", str(e))
                    return
                self._refresh_favorite_combo()
                return

    def _update_preview(self) -> None:
        self.preview_canvas.delete("all")
        code = self.code_var.get().strip()
        if not code:
            return
        try:
            sh = S.parse(code)
        except S.ShapeError:
            return
        render.draw_shape(self.preview_canvas, sh, 70, 70, 60)

    def _set_status(self, text: str, kind: str = "info") -> None:
        self.status_text.set(text)
        self.status_label.configure(style=_STATUS_STYLES.get(kind, "StatusInfo.TLabel"))

    def _current_config(self) -> solver.SolverConfig:
        return solver.SolverConfig(
            quad_cutter=self.quad_cutter.get(),
            quad_painter=self.quad_painter.get(),
            windmill_patch=self.windmill_patch.get(),
            max_cost=max(1, int(self.max_cost.get())),
            time_limit=max(0.5, float(self.time_limit.get())),
        )

    def _start_search(self) -> None:
        if self._search_thread is not None and self._search_thread.is_alive():
            return
        code = self.code_var.get().strip()
        try:
            sh = S.parse(code)
        except S.ShapeError as e:
            messagebox.showerror("不正なシェイプコード", str(e))
            return

        cfg = self._current_config()
        for b in self._search_buttons:
            b.config(state="disabled")
        self._set_status("探索を開始します...", "run")
        self.result_frame.configure(style="TLabelframe")
        self.progress_bar.pack(side="left", padx=(10, 0))
        self.progress_bar.start(12)
        self._progress_queue = queue.Queue()

        def progress(msg: str) -> None:
            self._progress_queue.put(("progress", msg))

        def worker() -> None:
            try:
                plan, guaranteed = construct.find_plan(sh, cfg, progress=progress)
                self._progress_queue.put(("done", (plan, guaranteed)))
            except Exception as exc:  # 探索スレッドの例外をUIに伝える
                self._progress_queue.put(("error", str(exc)))

        self._search_thread = threading.Thread(target=worker, daemon=True)
        self._search_thread.start()
        self.root.after(100, self._poll_search)

    def _poll_search(self) -> None:
        try:
            while True:
                kind, payload = self._progress_queue.get_nowait()
                if kind == "progress":
                    self._set_status(payload, "run")
                elif kind == "done":
                    self._on_search_done(*payload)
                    return
                elif kind == "error":
                    self._set_status(f"エラー: {payload}", "err")
                    self.result_frame.configure(style="ResultErr.TLabelframe")
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                    for b in self._search_buttons:
                        b.config(state="normal")
                    return
        except queue.Empty:
            pass
        if self._search_thread is not None and self._search_thread.is_alive():
            self.root.after(100, self._poll_search)

    def _on_search_done(self, plan, guaranteed: bool) -> None:
        for b in self._search_buttons:
            b.config(state="normal")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        if plan is None:
            self._set_status("解が見つかりませんでした(制限時間・建物数を増やしてください)", "err")
            self.result_frame.configure(style="ResultErr.TLabelframe")
            self.result_label.config(text="解なし")
            return

        target_key = self.code_var.get().strip()
        try:
            sim = solver.simulate(plan)
        except S.ShapeError as e:
            self._set_status(f"検証エラー: {e}", "err")
            self.result_frame.configure(style="ResultErr.TLabelframe")
            return
        if sim != target_key:
            self._set_status("検証に失敗しました(結果が目標シェイプと一致しません)", "err")
            self.result_frame.configure(style="ResultErr.TLabelframe")
            messagebox.showerror("検証失敗", "求めた手順を再実行しても目標シェイプと一致しませんでした。")
            return

        self.last_plan = plan
        self.last_guaranteed = guaranteed
        uniq = construct.unique_cost(plan)
        guarantee_text = "最小手数を保証" if guaranteed else "実用解(最小保証なし)"
        self._set_status(f"完了: {guarantee_text}", "ok")
        self.result_frame.configure(style="ResultOk.TLabelframe")
        self.result_label.config(
            text=(f"建物数(延べ): {plan.cost}    建物数(ユニーク): {uniq}\n"
                  f"{guarantee_text} ・ 自己検証: OK")
        )
        self.tree_text.delete("1.0", "end")
        self.tree_text.insert("1.0", solver.format_plan(plan))
        self._draw_diagram(plan)

    def _export_plan(self) -> None:
        if self.last_plan is None:
            messagebox.showinfo("未探索", "先に探索を実行してください。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("テキストファイル", "*.txt"), ("すべてのファイル", "*.*")],
            initialfile="quadforge_plan.txt",
        )
        if not path:
            return
        uniq = construct.unique_cost(self.last_plan)
        try:
            export_plan.save_text(path, self.last_plan, self.last_guaranteed, uniq)
        except OSError as e:
            messagebox.showerror("書き出しに失敗しました", str(e))
            return
        self._set_status(f"手順を書き出しました: {path}", "ok")

    def _draw_diagram(self, plan) -> None:
        self.diagram_canvas.delete("all")
        self._diagram_gen += 1
        gen = self._diagram_gen
        steps = solver.ordered_steps(plan)
        shape_steps = [s for s in steps if s.kind == "shape"]
        r = 30
        positions = [(20 + i * 100, 80, step) for i, step in enumerate(shape_steps)]
        end_x = (positions[-1][0] + r + 20) if positions else 100
        self.diagram_canvas.configure(scrollregion=(0, 0, end_x, 160))

        def reveal(i: int) -> None:
            if gen != self._diagram_gen or i >= len(positions):
                return
            x, y, step = positions[i]
            tag = f"dstep{i}"
            if i > 0:
                px = positions[i - 1][0]
                self.diagram_canvas.create_line(px + r + 4, y, x - r - 4, y,
                                                 fill=_PALETTE["accent"], arrow="last", width=2, tags=(tag,))
            self.diagram_canvas.create_text(x, y + r + 14, text=step.op, fill=_PALETTE["text"],
                                             font=("Yu Gothic UI", 9), tags=(tag,))
            self._animate_grow(self.diagram_canvas, step.key, x, y, r, tag, gen, 1, 4)
            self.root.after(150, lambda: reveal(i + 1))

        reveal(0)

    def _animate_grow(self, canvas: tk.Canvas, key, x: float, y: float, target_r: float,
                       tag: str, gen: int, step: int, steps: int) -> None:
        """図形を小さい半径から段階的に拡大表示し、結果の出現に動きをつける。"""
        if gen != self._diagram_gen:
            return
        shape_tag = f"{tag}shape"
        canvas.delete(shape_tag)
        try:
            render.draw_shape(canvas, key, x, y, target_r * step / steps, tags=(tag, shape_tag))
        except S.ShapeError:
            pass
        if step < steps:
            self.root.after(18, lambda: self._animate_grow(canvas, key, x, y, target_r, tag, gen, step + 1, steps))

    # --- タブ2: 生産比率 ---

    def _build_throughput_tab(self) -> None:
        f = self.tab_throughput
        ttk.Label(f, text="直近の探索結果に対して、目標レート(個/秒)から必要建物数を計算します。",
                  wraplength=500).pack(anchor="w", padx=8, pady=8)

        form = ttk.Frame(f)
        form.pack(anchor="w", padx=8)
        self.rate_var = tk.DoubleVar(value=1.0)
        ttk.Label(form, text="目標レート(個/秒)").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.rate_var, width=8).grid(row=0, column=1)

        self.tier_vars = {}
        for i, cat in enumerate(("miner", "processors", "painting")):
            ttk.Label(form, text=f"{cat} 段階(0-7)").grid(row=1 + i, column=0, sticky="w")
            v = tk.IntVar(value=0)
            self.tier_vars[cat] = v
            ttk.Spinbox(form, from_=0, to=7, textvariable=v, width=5).grid(row=1 + i, column=1)

        ttk.Button(f, text="計算", command=self._compute_throughput).pack(anchor="w", padx=8, pady=6)
        self.throughput_text = tk.Text(f, height=16, relief="flat", bd=0,
                                         bg=_PALETTE["panel_alt"], fg=_PALETTE["text"],
                                         insertbackground=_PALETTE["text"],
                                         font=("Consolas", 10), padx=8, pady=6)
        self.throughput_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _compute_throughput(self) -> None:
        if self.last_plan is None:
            messagebox.showinfo("未探索", "先にシェイプ編集タブで探索を実行してください。")
            return
        tiers = {k: v.get() for k, v in self.tier_vars.items()}
        rate = max(0.0, float(self.rate_var.get()))
        buildings, materials = T.plan_requirements(self.last_plan, rate, tiers)
        lines = [f"目標レート: {rate} 個/秒"]
        lines.append("-- 必要建物数 --")
        for k, v in sorted(buildings.items()):
            lines.append(f"  {k}: {v} 棟")
        lines.append("-- 必要な原材料レート --")
        for k, v in sorted(materials.items()):
            lines.append(f"  {k}: {v:.3f} 個/秒")
        self.throughput_text.delete("1.0", "end")
        self.throughput_text.insert("1.0", "\n".join(lines))

    # --- タブ3: レベル一覧 ---

    def _build_levels_tab(self) -> None:
        f = self.tab_levels
        columns = ("level", "shape", "required", "reward")
        tv = ttk.Treeview(f, columns=columns, show="headings", height=20)
        for c, w in zip(columns, (50, 320, 90, 220)):
            tv.heading(c, text={"level": "Lv", "shape": "目標シェイプ", "required": "必要数",
                                 "reward": "報酬"}[c])
            tv.column(c, width=w)
        for lv in levels.LEVELS:
            req = f"{lv.required}/秒" if lv.per_second else str(lv.required)
            tv.insert("", "end", iid=str(lv.level), values=(lv.level, lv.shape, req, lv.reward))
        tv.pack(fill="both", expand=True, padx=8, pady=8)
        tv.bind("<Double-1>", lambda e: self._load_level(tv))
        ttk.Button(f, text="選択したレベルを探索タブへ読み込んで探索開始",
                   command=lambda: self._load_level(tv)).pack(pady=4)
        ttk.Button(f, text="選択したレベルをバッチ計算タブへ追加(複数選択可)",
                   command=lambda: self._add_levels_to_batch(tv)).pack(pady=(0, 8))

    def _load_level(self, tv: ttk.Treeview) -> None:
        sel = tv.selection()
        if not sel:
            return
        lv = levels.LEVEL_BY_NUMBER[int(sel[0])]
        self.code_var.set(lv.shape)
        self._load_code_into_grid()
        self.quad_cutter.set(lv.level >= 16)
        self.quad_painter.set(lv.level >= 20)
        self._start_search()

    def _add_levels_to_batch(self, tv: ttk.Treeview) -> None:
        sel = tv.selection()
        if not sel:
            messagebox.showinfo("未選択", "レベル一覧から追加したい行を選択してください(複数選択可)。")
            return
        codes = [levels.LEVEL_BY_NUMBER[int(iid)].shape for iid in sel]
        current = self.batch_input.get("1.0", "end").strip()
        text = (current + "\n" if current else "") + "\n".join(codes)
        self.batch_input.delete("1.0", "end")
        self.batch_input.insert("1.0", text)

    # --- タブ4: バッチ計算 ---

    def _build_batch_tab(self) -> None:
        f = self.tab_batch
        p = _PALETTE
        ttk.Label(f, text="シェイプコードを1行に1つずつ入力(またはレベル一覧タブから追加)して、まとめて構築手順を計算します。",
                  wraplength=560).pack(anchor="w", padx=8, pady=8)

        self.batch_input = tk.Text(f, height=8, relief="flat", bd=0, wrap="none",
                                     bg=p["panel_alt"], fg=p["text"], insertbackground=p["text"],
                                     font=("Consolas", 10), padx=8, pady=6)
        self.batch_input.pack(fill="x", padx=8)

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", padx=8, pady=6)
        self.batch_button = ttk.Button(btn_frame, text="まとめて計算", command=self._start_batch)
        self.batch_button.pack(side="left")
        self.batch_progress = ttk.Progressbar(btn_frame, mode="determinate", length=200)

        self.batch_status_text = tk.StringVar(value="待機中")
        ttk.Label(f, textvariable=self.batch_status_text, style="StatusInfo.TLabel").pack(anchor="w", padx=8)

        self.batch_result_text = tk.Text(f, height=16, relief="flat", bd=0,
                                           bg=p["panel_alt"], fg=p["text"], insertbackground=p["text"],
                                           font=("Consolas", 10), padx=8, pady=6)
        self.batch_result_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _start_batch(self) -> None:
        if self._batch_thread is not None and self._batch_thread.is_alive():
            return
        raw = self.batch_input.get("1.0", "end")
        codes = [line.strip() for line in raw.splitlines() if line.strip()]
        if not codes:
            messagebox.showinfo("入力なし", "シェイプコードを1行に1つずつ入力してください。")
            return

        cfg = self._current_config()
        self.batch_button.config(state="disabled")
        self.batch_status_text.set(f"0/{len(codes)} 件処理中...")
        self.batch_progress.configure(maximum=len(codes), value=0)
        self.batch_progress.pack(side="left", padx=(10, 0))
        self._batch_queue = queue.Queue()

        def progress(i: int, total: int, msg: str) -> None:
            self._batch_queue.put(("progress", (i, total, msg)))

        def worker() -> None:
            try:
                results = batch.solve_batch(codes, cfg, progress=progress)
                self._batch_queue.put(("done", results))
            except Exception as exc:  # バッチスレッドの例外をUIに伝える
                self._batch_queue.put(("error", str(exc)))

        self._batch_thread = threading.Thread(target=worker, daemon=True)
        self._batch_thread.start()
        self.root.after(100, self._poll_batch)

    def _poll_batch(self) -> None:
        try:
            while True:
                kind, payload = self._batch_queue.get_nowait()
                if kind == "progress":
                    i, total, msg = payload
                    self.batch_status_text.set(f"{i}/{total} 件処理中... 直近: {msg}")
                    self.batch_progress.configure(value=i)
                elif kind == "done":
                    self._on_batch_done(payload)
                    return
                elif kind == "error":
                    self.batch_status_text.set(f"エラー: {payload}")
                    self.batch_progress.pack_forget()
                    self.batch_button.config(state="normal")
                    return
        except queue.Empty:
            pass
        if self._batch_thread is not None and self._batch_thread.is_alive():
            self.root.after(100, self._poll_batch)

    def _on_batch_done(self, results) -> None:
        self.batch_button.config(state="normal")
        self.batch_progress.pack_forget()
        self._last_batch_results = results
        solved = sum(1 for r in results if r.error is None and r.plan is not None)
        self.batch_status_text.set(f"完了: {solved}/{len(results)} 件解けました")
        self.batch_result_text.delete("1.0", "end")
        self.batch_result_text.insert("1.0", batch.summarize(results))


def main(mod_messages: Optional[List[str]] = None) -> None:
    root = tk.Tk()
    QuadForgeApp(root, mod_messages=mod_messages)
    root.mainloop()


if __name__ == "__main__":
    main()
