import os
import re
import shutil
import stat
import subprocess
from pathlib import Path


def repo_name_from_url(url: str) -> str:
    last_segment = url.rstrip("/").split("/")[-1]
    name = re.sub(r"\.git$", "", last_segment)
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return name or "repo"


def _force_remove_readonly(func, path, _exc_info):
    # git's .git/objects/pack/*.idx and *.pack files are written read-only,
    # which makes shutil.rmtree raise PermissionError on Windows.
    os.chmod(path, stat.S_IWRITE)
    func(path)


def clone_repo(url: str, storage_dir: Path) -> Path:
    if not url or url.startswith("-"):
        raise ValueError(f"Invalid repo URL: {url!r}")

    storage_dir.mkdir(parents=True, exist_ok=True)
    target = storage_dir / repo_name_from_url(url)
    if target.exists():
        shutil.rmtree(target, onerror=_force_remove_readonly)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--", url, str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

    return target
