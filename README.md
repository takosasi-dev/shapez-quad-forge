# shapez.io (QuadForge)

[日本語](#日本語) | [English](#english)

<p align="center">
  <img src="docs/screenshot.png" alt="QuadForge screenshot" width="820">
</p>

---

## 日本語

**QuadForge** は [shapez.io](https://shapez.io/) 用の非公式プレイ支援ツールです。目標のシェイプ(またはレベル)を指定すると、それを作るための建物数最小の構築手順を自動で逆算します。

### 主な機能

- 4層×4象限のグリッドをクリックしてシェイプを直接編集(丸/角/星/風車 × 8色)
- レベル一覧(全26レベル)から目標シェイプ・必要個数をワンクリックで読み込み
- 逆算探索により**最小建物数を保証**する構築手順を算出(不可能な場合のみ実用解にフォールバックし、その旨を明示)
- クアッドカッター(Lv16解禁)・クアッドペインター(Lv20解禁)に対応
- 目標個数から必要な採掘機/処理ライン数(スループット)を計算
- GUI(tkinter)とCLI(`python main.py <シェイプコード>`)の両対応
- 手順図はステップごとに成長しながら表示されるアニメーション付き

### 動作環境

- Python 3.10 以降(Windows標準インストーラなら tkinter 同梱)
- 追加の外部ライブラリは不要(標準ライブラリのみで動作)

### 実行方法

```bash
python main.py                    # GUIを起動
python main.py <シェイプコード>    # CLIで1件だけ計算して終了(例: RuCw--Cw:----Ru--)
```

### ビルド済みexeの入手

ソースを用意しなくても、[Releases](../../releases) から `QuadForge.exe` をダウンロードしてそのまま実行できます。

### ソースからexeをビルドする

```bash
pip install pyinstaller
build.bat
```

`dist\QuadForge.exe` が生成されます。

### テスト

```bash
python -m pytest test_quadforge.py
```

16件のテストが通ります。

### 既知の制限事項

全26レベルのうち、Lv26のみ「浮いたシェイプ」構造(4象限すべてがどこかの層で使用済みで、捨て駒に使える空き象限が存在しない)に対する最小手数保証の解法が未実装です。それ以外の25レベルは最小建物数を保証した解が得られます。

### ライセンス・謝辞

このツールの `shape.py`(シェイプ演算)・`levels.py`(レベルデータ)は、[tobspr-games/shapez.io](https://github.com/tobspr-games/shapez.io)(GPL-3.0)の `shape_definition.js` / `levels.js` を Python に移植したものです。そのため本リポジトリ全体も **GPL-3.0** で公開しています(詳細は [LICENSE](LICENSE))。

本ツールは非公式のファンメイドツールであり、tobspr-games とは関係がなく、公式の承認を受けたものでもありません。shapez.io 本体の画像・音声・その他のアセットは同梱していません。

---

## English

**QuadForge** is an unofficial companion tool for [shapez.io](https://shapez.io/). Given a target shape (or a level), it works backward to compute a construction plan that uses the minimum possible number of buildings.

### Features

- Edit shapes directly by clicking a 4-layer × 4-quadrant grid (circle/rectangle/star/windmill × 8 colors)
- Load any of the 26 official levels' target shape and required count with one click
- Backward search that **guarantees the minimum building count** whenever possible, falling back to a practical (non-minimal) solution only when it must — and says so clearly
- Supports the quad cutter (unlocked at Lv16) and quad painter (unlocked at Lv20)
- Computes required miner/processing throughput from a target quantity
- Both GUI (tkinter) and CLI (`python main.py <shape-code>`) modes
- The construction-plan diagram animates step by step as it reveals

### Requirements

- Python 3.10+ (tkinter ships with the standard Windows installer)
- No third-party dependencies — standard library only

### Running from source

```bash
python main.py                    # launches the GUI
python main.py <shape-code>       # computes one plan on the command line, e.g. RuCw--Cw:----Ru--
```

### Prebuilt executable

Grab `QuadForge.exe` from the [Releases](../../releases) page and run it directly — no Python install needed.

### Building the exe yourself

```bash
pip install pyinstaller
build.bat
```

Produces `dist\QuadForge.exe`.

### Tests

```bash
python -m pytest test_quadforge.py
```

16 tests, all passing.

### Known limitation

Of the 26 official levels, Level 26 is the one case where the "floating shape" structure (all 4 quadrants are occupied somewhere in the shape, leaving no free quadrant to use as a disposable placeholder) isn't yet handled by the minimum-guaranteeing solver. The other 25 levels all produce a guaranteed-minimal plan.

### License & Credits

`shape.py` (shape math) and `levels.py` (level data) are ported from [tobspr-games/shapez.io](https://github.com/tobspr-games/shapez.io) (`shape_definition.js` / `levels.js`), which is licensed under GPL-3.0. Accordingly, this repository is also licensed under **GPL-3.0** (see [LICENSE](LICENSE)).

This is an unofficial, fan-made tool with no affiliation to or endorsement from tobspr-games. No shapez.io game assets (images, audio, etc.) are included.
