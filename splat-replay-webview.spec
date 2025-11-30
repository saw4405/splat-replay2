# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Splat Replay WebView Desktop App."""

from pathlib import Path

block_cipher = None

# プロジェクトルート
project_root = Path(SPECPATH)

# データファイルを収集
import certifi

datas = [
    # フロントエンドdist
    (str(project_root / 'frontend' / 'dist'), 'frontend/dist'),
    # アセット（アイコン等）
    (str(project_root / 'assets'), 'assets'),
    # certifi SSL certificates
    (certifi.where(), 'certifi'),
]

# 隠しインポート（動的インポートされるモジュール）
hiddenimports = [
    'splat_replay.web.app',
    'splat_replay.web.server',
    # uvicorn関連 - 本体を先にインポート
    'uvicorn',
    'uvicorn.config',
    'uvicorn.main',
    'uvicorn.server',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # httpx, h11などのuvicorn依存関係
    'httpx',
    'httpcore',
    'h11',
    'wsproto',
    'websockets',
    'websockets.asyncio',
    'websockets.asyncio.client',
    'websockets.asyncio.server',
    'websockets.client',
    'websockets.server',
    'websockets.headers',
    'websockets.imports',
    'click',
    'anyio',
    'sniffio',
    'certifi',
    # obswsc依存関係
    'obswsc',
    'obswsc.client',
    'obswsc.data',
    # pydantic dependencies
    'pydantic',
    'pydantic.dataclasses',
    'pydantic.fields',
    'pydantic.main',
    'pydantic.types',
    'pydantic.validators',
    # pywin32 dependencies (pre-import to reduce startup time)
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'pythoncom',
    'pywintypes',
]

a = Analysis(
    [str(project_root / 'src' / 'splat_replay' / 'gui' / 'webview_app.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cyndilib'],  # NDI support excluded - requires runtime libraries
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SplatReplay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX圧縮を無効化して起動速度を向上
    console=True,  # デバッグ用にコンソールを表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'icon.ico'),  # アイコン設定（ICO形式）
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # UPX圧縮を無効化して起動速度を向上
    upx_exclude=[],
    name='SplatReplay',
)
