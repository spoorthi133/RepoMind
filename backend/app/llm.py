import logging
from collections.abc import AsyncIterator
from functools import lru_cache

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """You are RepoMind, a code-understanding assistant.

Answer the user's question using ONLY the retrieved code context below. Follow these rules strictly:
- Every factual claim about the code must be followed by a citation in the form `file_path:start_line-end_line`, taken exactly from the context headers.
- If the retrieved context does not contain enough information to answer the question, say so explicitly. Never invent files, functions, or behavior that is not shown in the context.
- Be precise and concise."""

DIAGNOSIS_SYSTEM_PROMPT = """You are RepoMind, a code-understanding assistant helping diagnose an error.

You are given: (1) code chunks retrieved because they are relevant to the error, and (2) static analysis findings (from tools like pylint, bandit, mypy, ESLint) linked to those files. Follow these rules strictly:
- You are NOT a standalone bug-detection model. You only reason about likely causes using the retrieved code and the static analysis findings provided — never claim to have independently "found" the bug.
- Every factual claim about the code must be followed by a citation in the form `file_path:start_line-end_line`.
- If a static analysis finding is relevant to your reasoning, mention it explicitly (tool + message).
- If the retrieved context and findings are not enough to explain the error, say so explicitly rather than guessing. Never invent files, functions, or behavior not shown in the context.
- Be precise and concise."""


@lru_cache(maxsize=1)
def _client() -> AsyncGroq:
    return AsyncGroq(api_key=settings.groq_api_key)


def _format_context(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        header = f"### {c['file_path']}:{c['start_line']}-{c['end_line']} ({c['symbol_type']} {c.get('symbol_name') or ''})".strip()
        blocks.append(f"{header}\n```\n{c['code']}\n```")
    return "\n\n".join(blocks) if blocks else "(no relevant code found)"


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = _format_context(chunks)
    return f"{QA_SYSTEM_PROMPT}\n\n# Retrieved code context\n{context}\n\n# Question\n{question}"


def build_diagnosis_prompt(error_text: str, chunks: list[dict], findings: list[dict]) -> str:
    context = _format_context(chunks)
    if findings:
        findings_text = "\n".join(
            f"- [{f['tool']}] {f['file_path']}:{f['line']} ({f.get('severity') or 'unknown'}): {f['message']}"
            for f in findings
        )
    else:
        findings_text = "(no static analysis findings linked to the retrieved files)"
    return (
        f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n"
        f"# Retrieved code context\n{context}\n\n"
        f"# Static analysis findings\n{findings_text}\n\n"
        f"# Error reported by the user\n{error_text}"
    )


async def generate(prompt: str) -> str | None:
    """Non-streaming single-shot generation, used for pre-computed summaries."""
    if not settings.groq_api_key:
        return None
    try:
        response = await _client().chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception:
        logger.exception("LLM generate() call failed")
        return None


async def _stream(prompt: str) -> AsyncIterator[str]:
    if not settings.groq_api_key:
        yield "[LLM not configured: set GROQ_API_KEY in backend/.env]"
        return

    stream = await _client().chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_answer(question: str, chunks: list[dict]) -> AsyncIterator[str]:
    return _stream(build_prompt(question, chunks))


def stream_diagnosis(error_text: str, chunks: list[dict], findings: list[dict]) -> AsyncIterator[str]:
    return _stream(build_diagnosis_prompt(error_text, chunks, findings))
