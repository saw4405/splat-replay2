#!/usr/bin/env python3
"""固定した自己署名証明書で macOS アプリを署名・検証する。"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


IDENTITY_COMMON_NAME = "Splat Replay Local Code Signing"
EXPECTED_CERTIFICATE_SHA256 = (
    "2B617E1206573418DF294B7CB8F256F0AA0EE5ED556DF9BE32064774DE8D20B5"
)
BUNDLE_IDENTIFIER = "io.github.saw4405.splatreplay"
CERTIFICATE_PATTERN = re.compile(
    rb"-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----",
    re.DOTALL,
)
IDENTITY_PATTERN = re.compile(
    r'^\s*\d+\)\s+([0-9A-Fa-f]{40})\s+"([^"]+)"(?:\s+\(.*\))?\s*$'
)


class SigningError(RuntimeError):
    """macOS署名の前提または署名内容が無効。"""


@dataclass(frozen=True)
class SigningIdentity:
    common_name: str
    sha1: str
    sha256: str
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    basic_constraints: str
    key_usage: str
    extended_key_usage: str


@dataclass(frozen=True)
class IdentityRecord:
    sha1: str
    common_name: str


def parse_identity_records(output: str) -> list[IdentityRecord]:
    """security find-identity の行から証明書と秘密鍵の組を読む。"""
    records: list[IdentityRecord] = []
    for line in output.splitlines():
        match = IDENTITY_PATTERN.match(line)
        if match:
            records.append(
                IdentityRecord(
                    sha1=match.group(1).upper(), common_name=match.group(2)
                )
            )
    return records


def validate_pinned_identity(
    identity: SigningIdentity,
    records: list[IdentityRecord],
    *,
    now: datetime | None = None,
) -> IdentityRecord:
    """証明書属性と login Keychain の秘密鍵対応を固定値へ照合する。"""
    if not re.fullmatch(r"[0-9A-F]{64}", EXPECTED_CERTIFICATE_SHA256):
        raise SigningError("固定証明書の SHA-256 指紋が設定されていません")
    if identity.common_name != IDENTITY_COMMON_NAME:
        raise SigningError("固定署名証明書の Common Name が一致しません")
    if identity.sha256 != EXPECTED_CERTIFICATE_SHA256:
        raise SigningError("固定署名証明書の SHA-256 指紋が一致しません")
    if identity.subject != identity.issuer:
        raise SigningError("固定署名証明書が自己署名ではありません")
    current_time = now or datetime.now(UTC)
    if (
        current_time < identity.not_before
        or current_time >= identity.not_after
    ):
        raise SigningError("固定署名証明書が有効期間外です")
    if "CA:FALSE" not in identity.basic_constraints:
        raise SigningError("固定署名証明書の CA 制約が不正です")
    if "digital signature" not in identity.key_usage.lower():
        raise SigningError(
            "固定署名証明書に digitalSignature 用途がありません"
        )
    if "code signing" not in identity.extended_key_usage.lower():
        raise SigningError("固定署名証明書に Code Signing 用途がありません")

    named_records = [
        record
        for record in records
        if record.common_name == IDENTITY_COMMON_NAME
    ]
    if len(named_records) != 1:
        raise SigningError(
            "login Keychain の固定署名 identity が一意ではありません"
        )
    record = named_records[0]
    if record.sha1 != identity.sha1:
        raise SigningError(
            "固定証明書に対応する秘密鍵が login Keychain にありません"
        )
    return record


def requirement_matches(output: str, identity_sha1: str) -> bool:
    """署名済みコードのDRが bundle ID と固定証明書を指定することを確認する。"""
    expected = (
        f'designated => identifier "{BUNDLE_IDENTIFIER}" and '
        f'certificate leaf = h"{identity_sha1.upper()}"'
    ).lower()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    designated = [
        line.lower() for line in lines if line.startswith("designated =>")
    ]
    if len(designated) != 1 or designated[0] != expected:
        return False
    return all(
        line.startswith("Executable=") or line.startswith("designated =>")
        for line in lines
    )


def signature_has_hardened_runtime(output: str) -> bool:
    """署名表示にruntime optionが追加されていないことを判定する。"""
    return bool(
        re.search(r"(?im)^.*flags=[^\n]*\bruntime\b", output)
        or re.search(r"(?im)^Runtime Version=", output)
    )


def _run(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        args,
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        command = Path(args[0]).name
        raise SigningError(
            f"{command} が失敗しました (exit {result.returncode})"
        )
    return result.stdout + result.stderr


def _parse_certificate(pem: bytes, openssl_path: str) -> SigningIdentity:
    blocks = CERTIFICATE_PATTERN.findall(pem)
    if len(blocks) != 1:
        raise SigningError("login Keychain から証明書を一意に取得できません")
    der = base64.b64decode(re.sub(rb"\s+", b"", blocks[0]), validate=True)
    output = _run(
        [
            openssl_path,
            "x509",
            "-noout",
            "-nameopt",
            "RFC2253",
            "-subject",
            "-issuer",
            "-dates",
            "-text",
        ],
        input_bytes=pem,
    ).decode("utf-8", errors="replace")
    subject = _single_openssl_value(output, "subject")
    issuer = _single_openssl_value(output, "issuer")
    common_name_match = re.fullmatch(r"CN=(.+)", subject)
    if common_name_match is None:
        common_name = ""
    else:
        common_name = common_name_match.group(1)
    return SigningIdentity(
        common_name=common_name,
        sha1=hashlib.sha1(der).hexdigest().upper(),
        sha256=hashlib.sha256(der).hexdigest().upper(),
        subject=subject,
        issuer=issuer,
        not_before=_parse_openssl_date(
            _single_openssl_value(output, "notBefore")
        ),
        not_after=_parse_openssl_date(
            _single_openssl_value(output, "notAfter")
        ),
        basic_constraints=_extension_contents(
            output, "X509v3 Basic Constraints:"
        ),
        key_usage=_extension_contents(output, "X509v3 Key Usage:"),
        extended_key_usage=_extension_contents(
            output, "X509v3 Extended Key Usage:"
        ),
    )


def _single_openssl_value(output: str, key: str) -> str:
    matches = re.findall(rf"^{re.escape(key)}=\s*(.+)$", output, re.MULTILINE)
    if len(matches) != 1:
        raise SigningError(f"証明書の {key} を読み取れません")
    return matches[0].strip()


def _parse_openssl_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=UTC
        )
    except ValueError as exc:
        raise SigningError("証明書の有効期間を読み取れません") from exc


def _extension_contents(output: str, heading: str) -> str:
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if heading in line:
            contents: list[str] = []
            for following in lines[index + 1 :]:
                value = following.strip()
                if value.startswith("X509v3 "):
                    break
                if value:
                    contents.append(value)
            return " ".join(contents)
    return ""


def _login_keychain() -> Path:
    keychain = Path.home() / "Library" / "Keychains" / "login.keychain-db"
    if not keychain.is_file():
        raise SigningError("login Keychain が見つかりません")
    return keychain


def _load_signing_identity() -> tuple[SigningIdentity, IdentityRecord, Path]:
    if sys.platform != "darwin":
        raise SigningError("macOS でのみ署名 identity を確認できます")
    keychain = _login_keychain()
    security_path = "/usr/bin/security"
    openssl_path = shutil.which("openssl")
    if openssl_path is None:
        raise SigningError("openssl が見つかりません")
    identity_output = _run(
        [security_path, "find-identity", "-p", "codesigning", str(keychain)]
    ).decode("utf-8", errors="replace")
    certificate_output = _run(
        [
            security_path,
            "find-certificate",
            "-a",
            "-c",
            IDENTITY_COMMON_NAME,
            "-p",
            str(keychain),
        ]
    )
    certificate = _parse_certificate(certificate_output, openssl_path)
    record = validate_pinned_identity(
        certificate, parse_identity_records(identity_output)
    )
    return certificate, record, keychain


def _run_codesign(*args: str) -> bytes:
    return _run(["/usr/bin/codesign", *args])


def _verify_app(
    app: Path, certificate: SigningIdentity, identity: IdentityRecord
) -> None:
    if not app.is_dir() or app.suffix != ".app":
        raise SigningError("検証対象の .app が見つかりません")
    _run_codesign("--verify", "--deep", "--strict", str(app))
    display = _run_codesign("-d", "--verbose=4", str(app)).decode(
        "utf-8", errors="replace"
    )
    if "Signature=adhoc" in display:
        raise SigningError("ad hoc 署名は使用できません")
    if f"Identifier={BUNDLE_IDENTIFIER}" not in display:
        raise SigningError("署名済み bundle identifier が一致しません")
    if signature_has_hardened_runtime(display):
        raise SigningError("hardened runtime option は追加できません")
    if not requirement_matches(
        _run_codesign("-d", "-r-", str(app)).decode("utf-8", errors="replace"),
        identity.sha1,
    ):
        raise SigningError(
            "署名済み DR が固定 bundle ID と証明書を指定しません"
        )

    with tempfile.TemporaryDirectory(
        prefix="splat-replay-signature-"
    ) as temp_root:
        certificate_prefix = Path(temp_root) / "certificate-"
        _run_codesign(
            "-d",
            f"--extract-certificates={certificate_prefix}",
            str(app),
        )
        leaf_certificate = Path(f"{certificate_prefix}0")
        if not leaf_certificate.is_file():
            raise SigningError(
                "署名済みアプリの leaf certificate がありません"
            )
        leaf_sha256 = (
            hashlib.sha256(leaf_certificate.read_bytes()).hexdigest().upper()
        )
        if leaf_sha256 != certificate.sha256:
            raise SigningError(
                "署名済みアプリの leaf certificate が一致しません"
            )


def _sign_app(
    app: Path,
    certificate: SigningIdentity,
    identity: IdentityRecord,
    keychain: Path,
) -> None:
    if not app.is_dir() or app.suffix != ".app":
        raise SigningError("署名対象の .app が見つかりません")
    requirement = (
        f'=designated => identifier "{BUNDLE_IDENTIFIER}" and '
        f'certificate leaf = H"{identity.sha1}"'
    )
    _run_codesign(
        "--force",
        "--sign",
        identity.sha1,
        "--timestamp=none",
        "--identifier",
        BUNDLE_IDENTIFIER,
        "--requirements",
        requirement,
        "--keychain",
        str(keychain),
        str(app),
    )
    _verify_app(app, certificate, identity)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "sign", "verify"))
    parser.add_argument("app", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        certificate, identity, keychain = _load_signing_identity()
        if args.action == "preflight":
            print(
                "署名 identity を確認しました: "
                f"{certificate.common_name} / SHA-256 {certificate.sha256}"
            )
            return 0
        if args.app is None:
            parser.error("sign / verify には .app のパスが必要です")
        if args.action == "sign":
            _sign_app(args.app, certificate, identity, keychain)
        else:
            _verify_app(args.app, certificate, identity)
        print(f"固定証明書署名を確認しました: {args.app}")
        return 0
    except SigningError as exc:
        print(f"macOS 署名を停止しました: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
