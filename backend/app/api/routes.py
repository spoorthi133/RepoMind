import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db import get_pool
from app.ingest import ingest_repo
from app.llm import stream_answer, stream_diagnosis
from app.retrieval import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestRequest(BaseModel):
    url: str


class RepoOut(BaseModel):
    id: int
    url: str
    name: str
    status: str
    error_message: str | None = None


class ChatRequest(BaseModel):
    question: str
    k: int = 8


class DiagnoseRequest(BaseModel):
    error_text: str
    k: int = 6


@router.post("/repos", response_model=RepoOut)
async def create_repo(payload: IngestRequest, background_tasks: BackgroundTasks):
    pool = get_pool()
    name = payload.url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]

    row = await pool.fetchrow(
        """
        INSERT INTO repos (url, name, status)
        VALUES ($1, $2, 'pending')
        ON CONFLICT (url) DO UPDATE SET status = 'pending', error_message = NULL, updated_at = now()
        RETURNING id, url, name, status, error_message
        """,
        payload.url,
        name,
    )
    background_tasks.add_task(ingest_repo, pool, row["id"], payload.url)
    return dict(row)


@router.get("/repos/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: int):
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT id, url, name, status, error_message FROM repos WHERE id = $1", repo_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="repo not found")
    return dict(row)


@router.post("/repos/{repo_id}/chat")
async def chat(repo_id: int, payload: ChatRequest):
    pool = get_pool()
    repo = await pool.fetchrow("SELECT status FROM repos WHERE id = $1", repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="repo not found")
    if repo["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"repo is not ready (status={repo['status']})")

    chunks = await hybrid_search(pool, repo_id, payload.question, k=payload.k)

    async def event_stream():
        citations = [
            {
                "file_path": c["file_path"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "symbol_name": c["symbol_name"],
            }
            for c in chunks
        ]
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"

        try:
            async for token in stream_answer(payload.question, chunks):
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        except Exception as exc:
            logger.exception("LLM streaming failed for chat")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/repos/{repo_id}/summary")
async def get_summary(repo_id: int):
    pool = get_pool()
    repo = await pool.fetchrow("SELECT summary, status FROM repos WHERE id = $1", repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="repo not found")

    files = await pool.fetch(
        "SELECT path, summary FROM files WHERE repo_id = $1 AND summary IS NOT NULL ORDER BY path", repo_id
    )
    return {
        "repo_summary": repo["summary"],
        "status": repo["status"],
        "files": [dict(f) for f in files],
    }


@router.get("/repos/{repo_id}/chunk")
async def get_chunk_source(repo_id: int, file_path: str, start_line: int, end_line: int):
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT c.code
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        WHERE c.repo_id = $1 AND f.path = $2 AND c.start_line = $3 AND c.end_line = $4
        LIMIT 1
        """,
        repo_id,
        file_path,
        start_line,
        end_line,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    return {"code": row["code"]}


@router.post("/repos/{repo_id}/diagnose")
async def diagnose(repo_id: int, payload: DiagnoseRequest):
    """Feature E's error-diagnosis flow: retrieval + linked static-analysis findings,
    reasoned about by the LLM. This is LLM-assisted diagnosis grounded in retrieved
    code and static analysis output — not standalone bug detection."""
    pool = get_pool()
    repo = await pool.fetchrow("SELECT status FROM repos WHERE id = $1", repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="repo not found")
    if repo["status"] != "ready":
        raise HTTPException(status_code=409, detail=f"repo is not ready (status={repo['status']})")

    chunks = await hybrid_search(pool, repo_id, payload.error_text, k=payload.k)
    file_ids = list({c["file_id"] for c in chunks})

    findings_rows = []
    if file_ids:
        findings_rows = await pool.fetch(
            """
            SELECT f.path AS file_path, sf.tool, sf.severity, sf.line, sf.message
            FROM static_findings sf
            JOIN files f ON f.id = sf.file_id
            WHERE sf.file_id = ANY($1::int[])
            ORDER BY sf.severity, sf.line
            """,
            file_ids,
        )
    findings = [dict(r) for r in findings_rows]

    async def event_stream():
        citations = [
            {
                "file_path": c["file_path"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "symbol_name": c["symbol_name"],
            }
            for c in chunks
        ]
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
        yield f"event: findings\ndata: {json.dumps(findings)}\n\n"

        try:
            async for token in stream_diagnosis(payload.error_text, chunks, findings):
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        except Exception as exc:
            logger.exception("LLM streaming failed for diagnose")
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
