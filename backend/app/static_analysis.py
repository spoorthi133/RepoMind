"""LLM-independent static analysis wiring for Feature E.

Findings here come entirely from off-the-shelf tools (pylint, bandit, mypy,
ESLint) — the LLM never "detects" anything itself. See app/llm.py's
DIAGNOSIS_SYSTEM_PROMPT for how these findings are used only to ground the
LLM's explanation, never presented as an independent discovery.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PYLINT_TIMEOUT = 180
BANDIT_TIMEOUT = 120
MYPY_TIMEOUT = 180
ESLINT_TIMEOUT = 180

ESLINT_CONFIG_NAMES = (
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
    ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
)


def _relpath(repo_root: Path, raw_path: str) -> str:
    # pylint/mypy report paths relative to the subprocess's cwd (repo_root);
    # bandit/eslint echo back the absolute paths we passed as arguments.
    # Path.resolve() below always resolves against *this* process's cwd, so a
    # cwd-relative raw_path must be joined onto repo_root first.
    p = Path(raw_path)
    if not p.is_absolute():
        p = repo_root / p
    try:
        return p.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return raw_path


def run_pylint(repo_root: Path, python_files: list[Path]) -> list[dict]:
    if not python_files:
        return []
    cmd = [
        sys.executable,
        "-m",
        "pylint",
        "--output-format=json",
        "--disable=all",
        "--enable=E,F,W",
        "--exit-zero",
        *[str(p.resolve()) for p in python_files],
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root.resolve()), timeout=PYLINT_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("pylint skipped: %s", exc)
        return []

    try:
        raw_findings = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning("pylint produced non-JSON output, skipping")
        return []

    findings = []
    for f in raw_findings:
        findings.append(
            {
                "file_path": _relpath(repo_root, f.get("path", "")),
                "line": f.get("line"),
                "severity": f.get("type"),  # convention | refactor | warning | error | fatal
                "message": f.get("message", ""),
                "rule_id": f.get("message-id") or f.get("symbol"),
                "tool": "pylint",
            }
        )
    return findings


def run_bandit(repo_root: Path, python_files: list[Path]) -> list[dict]:
    if not python_files:
        return []
    cmd = [sys.executable, "-m", "bandit", "-f", "json", "-q", *[str(p.resolve()) for p in python_files]]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root.resolve()), timeout=BANDIT_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("bandit skipped: %s", exc)
        return []

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        logger.warning("bandit produced non-JSON output, skipping")
        return []

    findings = []
    for f in payload.get("results", []):
        findings.append(
            {
                "file_path": _relpath(repo_root, f.get("filename", "")),
                "line": f.get("line_number"),
                "severity": f.get("issue_severity"),
                "message": f.get("issue_text", ""),
                "rule_id": f.get("test_id"),
                "tool": "bandit",
            }
        )
    return findings


_MYPY_LINE_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): (?P<severity>error|warning|note): (?P<message>.*)$")


def run_mypy(repo_root: Path, python_files: list[Path]) -> list[dict]:
    if not python_files:
        return []
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--ignore-missing-imports",
        "--no-error-summary",
        "--no-color-output",
        "--follow-imports=silent",
        # Real repos routinely have same-named modules (e.g. multiple
        # conftest.py) in unrelated subtrees with no __init__.py; without this,
        # mypy hard-errors with "Duplicate module named ..." instead of
        # producing any findings.
        "--explicit-package-bases",
        *[str(p.resolve()) for p in python_files],
    ]
    # Force a wide line width so mypy doesn't wrap error messages across
    # lines (it wraps to a default width even when stdout isn't a tty),
    # which would otherwise break the single-line regex below.
    env = {**os.environ, "COLUMNS": "400"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(repo_root.resolve()), timeout=MYPY_TIMEOUT, env=env
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("mypy skipped: %s", exc)
        return []

    findings = []
    for line in (result.stdout or "").splitlines():
        m = _MYPY_LINE_RE.match(line.strip())
        if not m:
            continue
        findings.append(
            {
                "file_path": _relpath(repo_root, m.group("path")),
                "line": int(m.group("line")),
                "severity": m.group("severity"),
                "message": m.group("message"),
                "rule_id": None,
                "tool": "mypy",
            }
        )
    return findings


def _has_eslint_config(repo_root: Path) -> bool:
    return any((repo_root / name).is_file() for name in ESLINT_CONFIG_NAMES)


def run_eslint(repo_root: Path, js_ts_files: list[Path]) -> list[dict]:
    if not js_ts_files:
        return []
    if not _has_eslint_config(repo_root):
        logger.info("No ESLint config found in %s, skipping JS/TS static analysis", repo_root)
        return []

    cmd = ["npx", "--yes", "eslint", "--format", "json", *[str(p.resolve()) for p in js_ts_files]]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root.resolve()), timeout=ESLINT_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("eslint skipped: %s", exc)
        return []

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        logger.warning("eslint produced non-JSON output, skipping")
        return []

    findings = []
    for file_result in payload:
        file_path = _relpath(repo_root, file_result.get("filePath", ""))
        for msg in file_result.get("messages", []):
            severity = {1: "warning", 2: "error"}.get(msg.get("severity"), "info")
            findings.append(
                {
                    "file_path": file_path,
                    "line": msg.get("line"),
                    "severity": severity,
                    "message": msg.get("message", ""),
                    "rule_id": msg.get("ruleId"),
                    "tool": "eslint",
                }
            )
    return findings


def run_static_analysis(repo_root: Path, files_by_language: dict[str, list[Path]]) -> list[dict]:
    python_files = files_by_language.get("python", [])
    js_ts_files = [
        *files_by_language.get("javascript", []),
        *files_by_language.get("typescript", []),
        *files_by_language.get("tsx", []),
    ]

    findings: list[dict] = []
    findings += run_pylint(repo_root, python_files)
    findings += run_bandit(repo_root, python_files)
    findings += run_mypy(repo_root, python_files)
    findings += run_eslint(repo_root, js_ts_files)
    return findings


async def run_static_analysis_async(repo_root: Path, files_by_language: dict[str, list[Path]]) -> list[dict]:
    """Same findings as run_static_analysis, but runs the four tools concurrently
    (each is an independent subprocess) and off the event loop, instead of blocking
    the whole server one tool at a time for the duration of ingestion."""
    python_files = files_by_language.get("python", [])
    js_ts_files = [
        *files_by_language.get("javascript", []),
        *files_by_language.get("typescript", []),
        *files_by_language.get("tsx", []),
    ]
    results = await asyncio.gather(
        asyncio.to_thread(run_pylint, repo_root, python_files),
        asyncio.to_thread(run_bandit, repo_root, python_files),
        asyncio.to_thread(run_mypy, repo_root, python_files),
        asyncio.to_thread(run_eslint, repo_root, js_ts_files),
    )
    findings: list[dict] = []
    for r in results:
        findings += r
    return findings
