#!/usr/bin/env python3
"""音声文字起こし動作確認スクリプト。

IntegratedSpeechRecognizer（Google + Groq Whisper + LLM統合）の動作を
単独で試すための一時スクリプト。

使い方:
    # 固定秒数録音モード（デフォルト）
    uv run python scripts/test_transcription.py [--seconds 5] [--list-mics]

    # listen()モード（アプリと同じ挙動でフレーズ検出ループ）
    uv run python scripts/test_transcription.py --listen [--count 3]

注意:
    - このスクリプトは一時的な動作確認用です。
    - backend/config/settings.toml の speech_transcriber 設定を使用します。
    - groq_api_key が未設定の場合は --groq-key オプションで渡せます。
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

import speech_recognition as sr
import structlog

from splat_replay.domain.config import SpeechTranscriberSettings
from splat_replay.infrastructure.adapters.audio.integrated_speech_recognition import (
    IntegratedSpeechRecognizer,
)
from splat_replay.infrastructure.config import load_settings_from_toml

log = structlog.get_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="音声文字起こし動作確認スクリプト"
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=5.0,
        help="録音時間（秒）。デフォルト: 5",
    )
    parser.add_argument(
        "--list-mics",
        action="store_true",
        help="利用可能なマイク一覧を表示して終了",
    )
    parser.add_argument(
        "--mic-index",
        type=int,
        default=None,
        help="使用するマイクのインデックス（省略時は settings.toml のデバイス名で自動検索）",
    )
    parser.add_argument(
        "--groq-key",
        type=str,
        default=None,
        help="Groq API キー（省略時は settings.toml から読み込む）",
    )
    parser.add_argument(
        "--no-vad",
        action="store_true",
        help="VAD（無音スキップ）を無効化して強制的に認識を実行する",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="アプリと同じ listen() ループモードで動作する（Ctrl+C で終了）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="listen() モードで認識する回数上限（0=無制限）。デフォルト: 0",
    )
    parser.add_argument(
        "--phrase-time-limit",
        type=float,
        default=None,
        help="listen() モードのフレーズ最大長（秒）。省略時は settings.toml の値を使用",
    )
    parser.add_argument(
        "--energy-threshold",
        type=float,
        default=None,
        help="speech_recognition のエネルギー閾値（高いほど音を拾いにくい）。省略時は adjust_for_ambient_noise で自動設定",
    )
    parser.add_argument(
        "--no-dynamic-energy",
        action="store_true",
        help="dynamic_energy_threshold を無効化する（閾値を固定する）",
    )
    return parser.parse_args()


def list_microphones() -> None:
    print("利用可能なマイク一覧:")
    for i, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"  [{i}] {name}")


def build_settings(args: argparse.Namespace) -> SpeechTranscriberSettings:
    """settings.toml から設定を読み込み、CLI 引数で上書きする。"""
    try:
        app_config = load_settings_from_toml()
        settings = app_config.speech_transcriber
    except Exception as e:
        print(
            f"警告: settings.toml の読み込みに失敗しました ({e})。デフォルト設定を使用します。"
        )
        settings = SpeechTranscriberSettings()

    if args.groq_key:
        from pydantic import SecretStr

        settings = settings.copy(
            update={"groq_api_key": SecretStr(args.groq_key)}
        )

    return settings


async def run_listen_loop(args: argparse.Namespace) -> None:
    """アプリと同じ listen() ベースのループでフレーズ検出・認識を繰り返す。"""
    settings = build_settings(args)
    recognizer = IntegratedSpeechRecognizer(settings=settings, logger=log)

    mic_index = args.mic_index
    if mic_index is None:
        from splat_replay.infrastructure.adapters.audio.speech_transcriber import (
            SpeechTranscriber,
        )

        mic_index = SpeechTranscriber.find_microphone(settings.mic_device_name)
        if mic_index is None:
            print(
                f"マイク '{settings.mic_device_name}' が見つかりません。"
                " --mic-index でインデックスを指定してください。"
            )
            list_microphones()
            sys.exit(1)

    assert mic_index is not None
    phrase_time_limit = args.phrase_time_limit or settings.phrase_time_limit
    listen_timeout = 1  # アプリと同じ値

    print(
        f"使用マイク: [{mic_index}] {sr.Microphone.list_microphone_names()[mic_index]}"
    )
    print(
        f"フレーズ最大長: {phrase_time_limit} 秒 / listen timeout: {listen_timeout} 秒"
    )
    print(
        f"モデル: groq={settings.groq_model}, integrator={settings.integrator_model}"
    )
    limit_msg = (
        str(args.count) + " 回"
        if args.count > 0
        else "無制限（Ctrl+C で終了）"
    )
    print(f"認識回数: {limit_msg}")
    print("-" * 50)

    r = sr.Recognizer()
    if args.no_dynamic_energy:
        r.dynamic_energy_threshold = False
    primary = settings.language.split("-")[0]
    recognized = 0

    with sr.Microphone(device_index=mic_index) as source:
        if args.energy_threshold is not None:
            r.energy_threshold = args.energy_threshold
            print(f"energy_threshold = {r.energy_threshold:.1f}（手動設定）")
        else:
            print("環境音調整中...")
            r.adjust_for_ambient_noise(source)
            print(f"energy_threshold = {r.energy_threshold:.1f}（自動設定）")
        print(f"dynamic_energy_threshold = {r.dynamic_energy_threshold}")
        print("待機中... 話しかけてください")

        while True:
            # listen() はフレーズ検出まで最大 listen_timeout 秒待つ
            try:
                audio = r.listen(
                    source,
                    timeout=listen_timeout,
                    phrase_time_limit=phrase_time_limit,
                )
            except sr.WaitTimeoutError:
                continue
            except KeyboardInterrupt:
                print("\n終了します。")
                break

            print("フレーズ検出。VAD + 認識中...")

            has_voice = (
                recognizer.has_voice_activity(audio)
                if not args.no_vad
                else True
            )
            vad_label = "あり" if has_voice else "なし（無音と判定）"
            print(f"  [VAD       ] {vad_label}")

            if not has_voice:
                print("  → VAD で無音と判定。スキップ。")
                continue

            google_result, groq_result = await asyncio.gather(
                recognizer.recognize_google(audio, settings.language),
                recognizer.recognize_groq(audio, primary),
            )
            print(f"  [Google    ] {google_result!r}")
            print(f"  [Groq      ] {groq_result!r}")

            # recognize() を再度呼ぶと Google/Groq を二重に呼ぶため、
            # 取得済み結果をそのまま統合処理に渡す
            if google_result is None:
                result = None
                print("  → Google が空のためスキップ。")
            else:
                est = await recognizer._estimate_speech(
                    f"google: {google_result}\ngroq: {groq_result}"
                )
                log.info(f"推定: {est.estimated_text} 理由: {est.reason}")
                result = est.estimated_text
            print(f"  [統合結果  ] {result!r}")
            print("-" * 50)

            recognized += 1
            if args.count > 0 and recognized >= args.count:
                print(f"{args.count} 回認識完了。終了します。")
                break


async def run(args: argparse.Namespace) -> None:
    settings = build_settings(args)

    recognizer = IntegratedSpeechRecognizer(settings=settings, logger=log)

    # マイクインデックスの決定
    mic_index = args.mic_index
    if mic_index is None:
        from splat_replay.infrastructure.adapters.audio.speech_transcriber import (
            SpeechTranscriber,
        )

        mic_index = SpeechTranscriber.find_microphone(settings.mic_device_name)
        if mic_index is None:
            print(
                f"マイク '{settings.mic_device_name}' が見つかりません。"
                " --mic-index でインデックスを指定してください。"
            )
            list_microphones()
            sys.exit(1)

    assert mic_index is not None
    print(
        f"使用マイク: [{mic_index}] {sr.Microphone.list_microphone_names()[mic_index]}"
    )
    print(f"録音時間: {args.seconds} 秒")
    print(
        f"モデル: groq={settings.groq_model}, integrator={settings.integrator_model}"
    )
    print("-" * 50)
    print("録音中... 話しかけてください")

    r = sr.Recognizer()
    with sr.Microphone(device_index=mic_index) as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        audio = r.record(source, duration=args.seconds)

    print("録音完了。認識中...")

    # VAD チェック
    if args.no_vad:
        has_voice = True
        print("[VAD] スキップ（--no-vad 指定）")
    else:
        has_voice = recognizer.has_voice_activity(audio)
        print(
            f"[VAD] 音声活動: {'あり' if has_voice else 'なし（無音と判定）'}"
        )
        if not has_voice:
            print(
                "無音のため認識をスキップします。--no-vad オプションで強制実行できます。"
            )
            return

    # Google と Groq を並列実行して個別結果も表示
    primary = settings.language.split("-")[0]
    google_result, groq_result = await asyncio.gather(
        recognizer.recognize_google(audio, settings.language),
        recognizer.recognize_groq(audio, primary),
    )
    print(f"[Google ] {google_result!r}")
    print(f"[Groq   ] {groq_result!r}")

    # 統合推定
    result = await recognizer.recognize(audio, has_voice_activity=True)
    print("-" * 50)
    print(f"[統合結果] {result!r}")


def main() -> None:
    args = parse_args()

    if args.list_mics:
        list_microphones()
        return

    if args.listen:
        asyncio.run(run_listen_loop(args))
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
