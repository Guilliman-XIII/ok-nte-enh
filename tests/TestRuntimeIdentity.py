import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.runtime_identity import resolve_runtime_identity


class TestRuntimeIdentity(unittest.TestCase):
    def test_environment_commit_has_priority(self):
        with (
            patch.dict(os.environ, {"OKNTE_BUILD_SHA": "a" * 40}, clear=False),
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            identity = resolve_runtime_identity("dev", Path(temp_dir))

        self.assertEqual(identity.commit, "a" * 12)
        self.assertEqual(identity.source, "env:OKNTE_BUILD_SHA")

    def test_build_commit_file_is_used_without_git(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BUILD_COMMIT").write_text("B" * 40, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                identity = resolve_runtime_identity("1.2.3", root)

        self.assertEqual(identity.version, "1.2.3")
        self.assertEqual(identity.commit, "b" * 12)
        self.assertEqual(identity.source, "BUILD_COMMIT")

    def test_git_is_the_development_fallback(self):
        result = subprocess.CompletedProcess([], 0, stdout="c" * 40 + "\n", stderr="")
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(os.environ, {}, clear=True),
            patch("src.runtime_identity.subprocess.run", return_value=result),
        ):
            identity = resolve_runtime_identity("dev", Path(temp_dir))

        self.assertEqual(identity.commit, "c" * 12)
        self.assertEqual(identity.source, "git")

    def test_unknown_is_explicit_when_no_source_is_available(self):
        result = subprocess.CompletedProcess([], 1, stdout="", stderr="")
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(os.environ, {}, clear=True),
            patch("src.runtime_identity.subprocess.run", return_value=result),
        ):
            identity = resolve_runtime_identity("", Path(temp_dir))

        self.assertEqual(identity.version, "dev")
        self.assertEqual(identity.commit, "unknown")
        self.assertEqual(identity.source, "unavailable")


if __name__ == "__main__":
    unittest.main()
