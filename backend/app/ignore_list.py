IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "target",
    "__pycache__", ".venv", "venv", "env", ".idea", ".vscode",
    "vendor", ".next", "coverage", ".pytest_cache", ".mypy_cache",
    "site-packages", ".tox", "egg-info",
}

IGNORED_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "Cargo.lock", "composer.lock", "go.sum",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".wav", ".mov",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".exe", ".dll", ".so", ".dylib", ".class", ".jar",
    ".min.js", ".min.css", ".map",
    ".lock",
}

# extension -> tree-sitter-languages language name
LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
}


def should_ignore_dir(dirname: str) -> bool:
    return dirname in IGNORED_DIRS or dirname.startswith(".")


def should_ignore_file(filename: str) -> bool:
    if filename in IGNORED_FILENAMES:
        return True
    for ext in IGNORED_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False


def detect_language(filename: str) -> str | None:
    for ext, lang in LANGUAGE_BY_EXTENSION.items():
        if filename.endswith(ext):
            return lang
    return None
