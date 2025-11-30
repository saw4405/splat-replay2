# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Splat Replay WebView Desktop App."""

from pathlib import Path

block_cipher = None

# プロジェクトルート
project_root = Path(SPECPATH)

# データファイルを収集
import certifi

datas = [
    # フロントエンドdist（_internal内に配置）
    (str(project_root / 'frontend' / 'dist'), 'frontend/dist'),
    # certifi SSL certificates（_internal内に配置）
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
    # cyndilib (NDI capture support) - Cython compiled modules
    'cyndilib',
    'cyndilib.finder',
    'cyndilib.receiver',
    'cyndilib.video_frame',
    'cyndilib.audio_frame',
    'cyndilib.framesync',
    'cyndilib.sender',
    'cyndilib.wrapper',
    'cyndilib.wrapper.common',
    'cyndilib.wrapper.ndi_recv',
    'cyndilib.wrapper.ndi_send',
    'cyndilib.wrapper.ndi_structs',
]

import glob

# cyndilib の .pyd ファイルを収集
cyndilib_binaries = []
cyndilib_path = project_root / '.venv' / 'Lib' / 'site-packages' / 'cyndilib'
if cyndilib_path.exists():
    for pyd_file in cyndilib_path.glob('**/*.pyd'):
        rel_path = pyd_file.relative_to(cyndilib_path.parent)
        dest_dir = str(rel_path.parent)
        cyndilib_binaries.append((str(pyd_file), dest_dir))

a = Analysis(
    [str(project_root / 'src' / 'splat_replay' / 'gui' / 'webview_app.py')],
    pathex=[],
    binaries=cyndilib_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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

# Note: assetsは_internalの外（実行ファイルと同じ階層）に配置したいため、
# COLLECTには含めず、ビルドスクリプトで手動コピーする
