from io import BytesIO
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, workspace_owner_id
from app.core.errors import AppError
from app.db.models import Agent, KnowledgeChunk, KnowledgeDocument, User
from app.db.session import get_session
from app.schemas.knowledge import DocumentCreate, DocumentOut, SearchResult

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def split_chunks(content: str) -> list[str]:
    clean = " ".join(content.split())
    return [
        clean[start : start + CHUNK_SIZE] for start in range(0, len(clean), CHUNK_SIZE - CHUNK_OVERLAP)
    ] or [clean]


async def owned_agent(agent_id: str | None, user: User, session: AsyncSession) -> None:
    if agent_id and not await session.scalar(
        select(Agent.id).where(Agent.id == agent_id, Agent.owner_id == workspace_owner_id(user))
    ):
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)


async def index_document(
    title: str, content: str, agent_id: str | None, user: User, session: AsyncSession
) -> KnowledgeDocument:
    await owned_agent(agent_id, user, session)
    chunks = split_chunks(content)
    document = KnowledgeDocument(
        owner_id=workspace_owner_id(user),
        agent_id=agent_id,
        title=title,
        content=content,
        chunk_count=len(chunks),
    )
    session.add(document)
    await session.flush()
    for index, chunk in enumerate(chunks):
        session.add(
            KnowledgeChunk(
                document_id=document.id,
                owner_id=workspace_owner_id(user),
                agent_id=agent_id,
                chunk_index=index,
                content=chunk,
            )
        )
    return document


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.owner_id == workspace_owner_id(user))
                .order_by(KnowledgeDocument.created_at.desc())
            )
        ).all()
    )


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def create_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    document = await index_document(payload.title, payload.content, payload.agent_id, user, session)
    await session.commit()
    await session.refresh(document)
    return document


@router.post("/documents/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    agent_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("DOCUMENT_TOO_LARGE", "Document is larger than 10 MB", 413)
    suffix = Path(file.filename or "").suffix.lower()
    try:
        if suffix in {".txt", ".csv", ".md", ".json"}:
            content = data.decode("utf-8-sig")
        elif suffix == ".pdf":
            from pypdf import PdfReader

            content = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        elif suffix == ".docx":
            from docx import Document as DocxDocument

            content = "\n".join(paragraph.text for paragraph in DocxDocument(BytesIO(data)).paragraphs)
        else:
            raise AppError("UNSUPPORTED_DOCUMENT", "Use TXT, CSV, Markdown, JSON, PDF or DOCX", 415)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("DOCUMENT_PARSE_ERROR", "Could not extract text from document", 422) from exc
    if not content.strip():
        raise AppError("EMPTY_DOCUMENT", "Document contains no readable text", 422)
    document = await index_document(file.filename or "Uploaded document", content, agent_id, user, session)
    await session.commit()
    await session.refresh(document)
    return document


@router.post("/documents/web", response_model=DocumentOut, status_code=201)
async def import_web_page(
    url: str = Query(min_length=12, max_length=500),
    agent_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not url.lower().startswith("https://") or any(
        host in url.lower() for host in ("localhost", "127.0.0.1", "0.0.0.0")
    ):
        raise AppError("INVALID_SOURCE_URL", "Only public HTTPS pages are allowed", 422)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > MAX_UPLOAD_BYTES:
            raise AppError("DOCUMENT_TOO_LARGE", "Web page is larger than 10 MB", 413)
        from bs4 import BeautifulSoup

        content = BeautifulSoup(response.text, "html.parser").get_text("\n", strip=True)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("WEB_IMPORT_FAILED", "Could not fetch web page", 422) from exc
    document = await index_document(url, content, agent_id, user, session)
    document.source_type = "web"
    await session.commit()
    await session.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id, KnowledgeDocument.owner_id == workspace_owner_id(user)
        )
    )
    if not document:
        raise AppError("DOCUMENT_NOT_FOUND", "Knowledge document not found", 404)
    await session.delete(document)
    await session.commit()


@router.get("/search", response_model=list[SearchResult])
async def search_knowledge(
    q: str = Query(min_length=2, max_length=300),
    agent_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    words = [word.lower() for word in q.split() if len(word) > 2][:8]
    if not words:
        return []
    filters = [KnowledgeChunk.owner_id == workspace_owner_id(user)]
    if agent_id:
        filters.append(or_(KnowledgeChunk.agent_id == agent_id, KnowledgeChunk.agent_id.is_(None)))
    rows = list((await session.scalars(select(KnowledgeChunk).where(*filters).limit(100))).all())
    documents = {
        row.id: row.title
        for row in (
            await session.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.owner_id == workspace_owner_id(user))
            )
        ).all()
    }
    results = []
    for row in rows:
        score = sum(word in row.content.lower() for word in words)
        if score:
            results.append(
                SearchResult(
                    document_id=row.document_id,
                    title=documents.get(row.document_id, "Источник"),
                    chunk_index=row.chunk_index,
                    content=row.content,
                    score=score,
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)[:8]
