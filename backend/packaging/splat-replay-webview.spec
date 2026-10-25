# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Splat Replay WebView Desktop App."""

from pathlib import Path
import platform
import sys

block_cipher = None

# パス解決
spec_root = Path(SPECPATH).resolve()
backend_root = spec_root.parent
repo_root = backend_root.parent
backend_src = backend_root / 'src'
is_macos = sys.platform == 'darwin'

if is_macos and platform.machine() != 'arm64':
    raise SystemExit('macOS packaging requires an arm64 Python environment')

if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

from splat_replay.bootstrap.pyinstaller_hiddenimports import (  # noqa: E402
    collect_pyinstaller_hiddenimports,
)

# 出力先をプロジェクトルートの dist/ に変更
dist_root = repo_root / 'dist'

# データファイルを収集
import certifi

pythonnet_runtime_dir = (
    backend_root / '.venv' / 'Lib' / 'site-packages' / 'pythonnet' / 'runtime'
)

datas = [
    # フロントエンドdist（_internal内に配置）
    (str(repo_root / 'frontend' / 'dist'), 'frontend/dist'),
    # certifi SSL certificates（_internal内に配置）
    (certifi.where(), 'certifi'),
]

if is_macos:
    assets_root = backend_root / 'assets'
    datas.extend(
        (
            str(path),
            str(Path('assets') / path.relative_to(assets_root).parent),
        )
        for path in assets_root.rglob('*')
        if path.is_file()
    )
    datas.append(
        (str(backend_root / 'config' / 'image_matching.yaml'), 'config')
    )

# setuptools._vendor.jaraco.text が参照するデータファイル（pkg_resources runtime hook 用）
_jaraco_text_dir = (
    backend_root / '.venv' / 'Lib' / 'site-packages'
    / 'setuptools' / '_vendor' / 'jaraco' / 'text'
)
_lorem_ipsum = _jaraco_text_dir / 'Lorem ipsum.txt'
if _lorem_ipsum.exists():
    datas.append((str(_lorem_ipsum), 'setuptools/_vendor/jaraco/text'))

# pythonnet ランタイム依存ファイルを明示同梱（Python.Runtime.deps.json 欠落対策）
_pythonnet_deps_json = pythonnet_runtime_dir / 'Python.Runtime.deps.json'
if _pythonnet_deps_json.exists():
    datas.append((str(_pythonnet_deps_json), 'pythonnet/runtime'))

hiddenimports = [
    'splat_replay.bootstrap.web_app',
    'splat_replay.interface.web.server',
    # DI コンテナ（直接 import だが frozen module で検出漏れするため明示）
    'splat_replay.infrastructure.di',
    'splat_replay.infrastructure.di.adapters',
    'splat_replay.infrastructure.di.app_services',
    'splat_replay.infrastructure.di.config',
    'splat_replay.infrastructure.di.domain_services',
    'splat_replay.infrastructure.di.use_cases',
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
    # cyndilib (NDI capture support) - Cython compiled modules
    'cyndilib',
    'cyndilib.finder',
    'cyndilib.receiver',
    'cyndilib.video_frame',
    'cyndilib.audio_frame',
    'cyndilib.framesync',
    'cyndilib.sender',
    # audio_frame の Cython extension が実行時に import する
    'cyndilib.buffertypes',
    'cyndilib.send_frame_status',
    'cyndilib.wrapper',
    'cyndilib.wrapper.common',
    'cyndilib.wrapper.ndi_recv',
    'cyndilib.wrapper.ndi_send',
    'cyndilib.wrapper.ndi_structs',
]
if sys.platform == 'win32':
    # pywin32 dependencies (pre-import to reduce startup time)
    hiddenimports.extend(
        [
            'win32api',
            'win32con',
            'win32gui',
            'win32process',
            'pythoncom',
            'pywintypes',
        ]
    )
if is_macos:
    hiddenimports.extend(['Foundation', 'Security', 'UserNotifications'])
hiddenimports.extend(collect_pyinstaller_hiddenimports())
hiddenimports = list(dict.fromkeys(hiddenimports))

import glob

# cyndilib の .pyd ファイルを収集
cyndilib_binaries = []
cyndilib_path = backend_root / '.venv' / 'Lib' / 'site-packages' / 'cyndilib'
if cyndilib_path.exists():
    for pyd_file in cyndilib_path.glob('**/*.pyd'):
        rel_path = pyd_file.relative_to(cyndilib_path.parent)
        dest_dir = str(rel_path.parent)
        cyndilib_binaries.append((str(pyd_file), dest_dir))

a = Analysis(
    [str(backend_root / 'src' / 'splat_replay' / 'bootstrap' / 'webview.py')],
    pathex=[str(backend_src)],
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

if is_macos:
    a.binaries = [
        entry for entry in a.binaries if entry[0] != 'speech_recognition/flac-mac'
    ]

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
    console=False,  # デスクトップ GUI のためコンソールを表示しない
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64' if is_macos else None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(
        backend_root / 'assets' / ('icon.png' if is_macos else 'icon.ico')
    ),
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

if is_macos:
    app = BUNDLE(
        coll,
        name='SplatReplay.app',
        icon=str(backend_root / 'assets' / 'icon.png'),
        bundle_identifier='io.github.saw4405.splatreplay',
        info_plist={
            'CFBundleName': 'Splat Replay',
            'CFBundleDisplayName': 'Splat Replay',
            'NSCameraUsageDescription': (
                '選択した映像入力機器の映像を録画画面でプレビューするために使用します。'
            ),
            'NSMicrophoneUsageDescription': (
                '録画中の音声をマイクから取得し、音声認識による字幕作成に使用します。'
            ),
            'NSLocalNetworkUsageDescription': (
                '家庭内 LAN の接続候補を確認するために利用します。'
            ),
        },
    )

# Windows の assets は _internal 外へ置くため、ビルド後に手動コピーする。
# macOS は assets を app bundle の Resources に収録し、実行時には変更しない。
