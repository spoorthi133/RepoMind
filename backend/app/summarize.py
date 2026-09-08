from pathlib import Path

from app.chunking import CodeChunk
from app.llm import generate

ENTRY_POINT_NAMES = {
    "main.py", "app.py", "wsgi.py", "asgi.py", "manage.py", "cli.py",
    "index.js", "index.ts", "server.js", "app.jsx", "app.tsx", "main.jsx", "main.tsx",
}
README_NAMES = ("README.md", "README.rst", "README.txt", "README")


async def summarize_file(path: str, language: str, chunks: list[CodeChunk]) -> str | None:
    symbol_lines = []
    for c in chunks[:30]:
        line = f"- {c.symbol_type} {c.symbol_name or '(module-level)'}"
        if c.docstring:
            first_line = c.docstring.strip().splitlines()[0][:200]
            line += f": {first_line}"
        symbol_lines.append(line)

    prompt = (
        "Summarize what this source file does in 1-2 concise sentences, for a developer "
        "onboarding onto this codebase. Base the summary only on the symbols and docstrings "
        "listed below — do not invent behavior.\n\n"
        f"File: {path} ({language})\n\nSymbols:\n" + "\n".join(symbol_lines)
    )
    return await generate(prompt)


def find_readme(repo_root: Path) -> str | None:
    for name in README_NAMES:
        candidate = repo_root / name
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace")[:6000]
            except OSError:
                return None
    return None


async def summarize_project(name: str, url: str, readme_text: str | None, file_summaries: list[tuple[str, str]]) -> str | None:
    parts = [f"Repository: {name} ({url})"]
    if readme_text:
        parts.append(f"README excerpt:\n{readme_text}")

    entry_points = [(p, s) for p, s in file_summaries if Path(p).name in ENTRY_POINT_NAMES]
    others = [(p, s) for p, s in file_summaries if Path(p).name not in ENTRY_POINT_NAMES]

    if entry_points:
        listing = "\n".join(f"- {p}: {s}" for p, s in entry_points)
        parts.append(f"Entry-point file summaries:\n{listing}")
    if others:
        listing = "\n".join(f"- {p}: {s}" for p, s in others[:60])
        parts.append(f"Other file summaries:\n{listing}")

    prompt = (
        "Write a concise 3-5 sentence project overview answering 'what does this repository do?' "
        "for a developer seeing it for the first time. Base it only on the information below — "
        "do not invent features or architecture that isn't shown.\n\n" + "\n\n".join(parts)
    )
    return await generate(prompt)
