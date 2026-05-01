# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for glreview.
# Build command:
#   uv run pyinstaller glreview.spec
#
# Output: dist/glreview  (Linux/macOS) or dist/glreview.exe  (Windows)

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- データファイル ---
# Textual の tree-sitter ハイライトファイル（.scm）を同梱する
datas = []
datas += collect_data_files("textual")
# アプリケーション自身の Textual CSS
datas += [("glreview/tui/styles.tcss", "glreview/tui")]

# --- 隠しインポート ---
# PyInstaller が静的解析で見落とす動的インポートを明示する
hiddenimports = []
# Textual のすべてのサブモジュール（ウィジェット・ドライバ等）
hiddenimports += collect_submodules("textual")
# Pygments の lexer はファイル拡張子から動的にロードされるため全件追加
hiddenimports += collect_submodules("pygments.lexers")
hiddenimports += collect_submodules("pygments.formatters")
hiddenimports += collect_submodules("pygments.styles")
# python-gitlab
hiddenimports += collect_submodules("gitlab")
# 標準ライブラリ（tomllib は 3.11 標準）
hiddenimports += [
    "tomllib",
    "_asyncio",
    "asyncio",
]

a = Analysis(
    ["glreview/__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要なモジュールを除外してサイズを削減
        "tkinter",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="glreview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX 圧縮は起動速度に影響するため無効
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # TUI アプリのためコンソールモード必須
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
