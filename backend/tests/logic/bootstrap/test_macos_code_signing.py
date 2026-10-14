from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[4] / "scripts" / "macos_code_signing.py"
)
MODULE_NAME = "macos_code_signing_for_test"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[MODULE_NAME] = MODULE
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
CERTIFICATE = MODULE.SigningIdentity(
    common_name="Splat Replay Local Code Signing",
    sha1="095DFCDC9664970C0103C27C06E0B27DD4C5AE29",
    sha256="2B617E1206573418DF294B7CB8F256F0AA0EE5ED556DF9BE32064774DE8D20B5",
    subject="CN=Splat Replay Local Code Signing",
    issuer="CN=Splat Replay Local Code Signing",
    not_before=datetime(2026, 10, 9, 8, 45, tzinfo=UTC),
    not_after=datetime(2036, 10, 6, 8, 45, tzinfo=UTC),
    basic_constraints="CA:FALSE",
    key_usage="Digital Signature",
    extended_key_usage="Code Signing",
)
IDENTITY_RECORD = MODULE.IdentityRecord(
    sha1=CERTIFICATE.sha1,
    common_name=CERTIFICATE.common_name,
)


def test_validate_pinned_identity_accepts_exact_valid_keychain_identity() -> (
    None
):
    identity = MODULE.validate_pinned_identity(
        CERTIFICATE, [IDENTITY_RECORD], now=NOW
    )

    assert identity == IDENTITY_RECORD


@pytest.mark.parametrize(
    "records",
    [[], [IDENTITY_RECORD, IDENTITY_RECORD]],
    ids=["missing-private-key", "ambiguous-private-key"],
)
def test_validate_pinned_identity_rejects_missing_or_ambiguous_key(
    records: list[MODULE.IdentityRecord],
) -> None:
    with pytest.raises(MODULE.SigningError):
        MODULE.validate_pinned_identity(CERTIFICATE, records, now=NOW)


@pytest.mark.parametrize(
    "certificate",
    [
        replace(CERTIFICATE, sha256="0" * 64),
        replace(CERTIFICATE, not_after=NOW),
        replace(CERTIFICATE, extended_key_usage="Client Authentication"),
        replace(CERTIFICATE, issuer="CN=Other Issuer"),
    ],
    ids=["wrong-fingerprint", "expired", "wrong-usage", "not-self-signed"],
)
def test_validate_pinned_identity_rejects_wrong_certificate(
    certificate: MODULE.SigningIdentity,
) -> None:
    with pytest.raises(MODULE.SigningError):
        MODULE.validate_pinned_identity(
            certificate, [IDENTITY_RECORD], now=NOW
        )


def test_requirement_matches_only_pinned_bundle_and_certificate() -> None:
    valid_requirement = (
        'designated => identifier "io.github.saw4405.splatreplay" and '
        'certificate leaf = H"095DFCDC9664970C0103C27C06E0B27DD4C5AE29"'
    )
    cdhash_only_requirement = (
        'designated => identifier "io.github.saw4405.splatreplay" and '
        'cdhash H"0123456789ABCDEF"'
    )
    appended_requirement = valid_requirement + "\nor true"

    assert MODULE.requirement_matches(valid_requirement, CERTIFICATE.sha1)
    assert not MODULE.requirement_matches(
        cdhash_only_requirement, CERTIFICATE.sha1
    )
    assert not MODULE.requirement_matches(
        appended_requirement, CERTIFICATE.sha1
    )


@pytest.mark.parametrize(
    ("signature", "has_runtime"),
    [
        ("CodeDirectory v=20500 flags=0x0(none)", False),
        ("CodeDirectory v=20500 flags=0x10000(runtime)", True),
        ("Runtime Version=2.0", True),
    ],
)
def test_signature_runtime_detection(
    signature: str, has_runtime: bool
) -> None:
    assert MODULE.signature_has_hardened_runtime(signature) is has_runtime
