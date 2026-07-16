import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")


@dataclass(frozen=True)
class RuntimeIdentity:
    version: str
    commit: str
    source: str

    def format_log(self) -> str:
        return f"OKNTE runtime version={self.version} commit={self.commit} source={self.source}"


def _normalize_sha(value) -> str:
    value = str(value or "").strip()
    return value.lower() if SHA_PATTERN.fullmatch(value) else ""


def _read_build_commit(root: Path) -> str:
    path = root / "BUILD_COMMIT"
    try:
        return _normalize_sha(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _read_git_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return _normalize_sha(result.stdout)


def resolve_runtime_identity(version="dev", root: Path | None = None) -> RuntimeIdentity:
    root = root or Path(__file__).resolve().parents[1]
    version = str(version or "dev").strip() or "dev"

    for env_name in ("OKNTE_BUILD_SHA", "GITHUB_SHA"):
        commit = _normalize_sha(os.environ.get(env_name))
        if commit:
            return RuntimeIdentity(version, commit[:12], f"env:{env_name}")

    commit = _read_build_commit(root)
    if commit:
        return RuntimeIdentity(version, commit[:12], "BUILD_COMMIT")

    commit = _read_git_commit(root)
    if commit:
        return RuntimeIdentity(version, commit[:12], "git")

    return RuntimeIdentity(version, "unknown", "unavailable")
