"""Frozen release integrity remains enforceable after normal CI stops enforcing it."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_verification", Path(__file__).resolve().parents[1] / "verify_package.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def release(tmp_path):
    document = tmp_path / "README.md"
    document.write_text("Original release\n", encoding="utf-8")
    manifest = {"files": [{"path": "README.md", "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}]}
    (tmp_path / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_explicit_release_verification_accepts_original(tmp_path):
    checks = []
    VERIFIER.verify_release_manifest(release(tmp_path), checks)
    assert "manifest: README.md" in checks


def test_explicit_release_verification_still_detects_edits(tmp_path):
    root = release(tmp_path)
    (root / "README.md").write_text("Edited in GitHub\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="manifest: README.md"):
        VERIFIER.verify_release_manifest(root, [])


def test_explicit_release_verification_requires_manifest(tmp_path):
    with pytest.raises(AssertionError, match="Release manifest is present"):
        VERIFIER.verify_release_manifest(tmp_path, [])
