# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Splat Replay WebView Desktop App."""

from pathlib import Path

block_cipher = None

# プロジェクトルート
project_root = Path(SPECPATH)

# データファイルを収集
datas = [
    # フロントエンドdist
    (str(project_root / 'frontend' / 'dist'), 'frontend/dist'),
    # アセット（アイコン等）
    (str(project_root / 'assets'), 'assets'),
    # 設定ファイル例
    (str(project_root / 'config' / 'settings.example.toml'), 'config'),
    (str(project_root / 'config' / 'image_matching.yaml'), 'config'),
    # cyndilib wrapper binaries (NDI support)
    (str(project_root / '.venv' / 'Lib' / 'site-packages' / 'cyndilib' / 'wrapper' / 'bin'), 'cyndilib/wrapper/bin'),
    (str(project_root / '.venv' / 'Lib' / 'site-packages' / 'cyndilib' / 'wrapper' / 'include'), 'cyndilib/wrapper/include'),
    (str(project_root / '.venv' / 'Lib' / 'site-packages' / 'cyndilib' / 'wrapper' / 'lib'), 'cyndilib/wrapper/lib'),
]

# 隠しインポート（動的インポートされるモジュール）
hiddenimports = [
    'splat_replay.web.app',
    'splat_replay.web.server',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # cyndilib (NDI キャプチャ用) - すべてのコンパイル済みモジュール
    'cyndilib',
    'cyndilib.audio_frame',
    'cyndilib.audio_reference',
    'cyndilib.buffertypes',
    'cyndilib.callback',
    'cyndilib.finder',
    'cyndilib.framesync',
    'cyndilib.locks',
    'cyndilib.metadata_frame',
    'cyndilib.receiver',
    'cyndilib.send_frame_status',
    'cyndilib.sender',
    'cyndilib.video_frame',
    'cyndilib.wrapper',
    'cyndilib.wrapper.common',
    'cyndilib.wrapper.ndi_recv',
    'cyndilib.wrapper.ndi_send',
    'cyndilib.wrapper.ndi_structs',
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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='SplatReplay',
)
