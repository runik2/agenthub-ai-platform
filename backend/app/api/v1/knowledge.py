from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db.models import Agent, KnowledgeChunk, KnowledgeDocument, User
from app.db.session import get_session
from app.schemas.knowledge import DocumentCreate, DocumentOut, SearchResult

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


def split_chunks(content: str) -> list[str]:
    clean = " ".join(content.split())
    return [
        clean[start : start + CHUNK_SIZE] for start in range(0, len(clean), CHUNK_SIZE - CHUNK_OVERLAP)
    ] or [clean]


async def owned_agent(agent_id: str | None, user: User, session: AsyncSession) -> None:
    if agent_id and not await session.scalar(
        select(Agent.id).where(Agent.id == agent_id, Agent.owner_id == user.id)
    ):
        raise AppError("AGENT_NOT_FOUND", "Agent not found", 404)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.owner_id == user.id)
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
    await owned_agent(payload.agent_id, user, session)
    chunks = split_chunks(payload.content)
    document = KnowledgeDocument(
        owner_id=user.id,
        agent_id=payload.agent_id,
        title=payload.title,
        content=payload.content,
        chunk_count=len(chunks),
    )
    session.add(document)
    await session.flush()
    for index, content in enumerate(chunks):
        session.add(
            KnowledgeChunk(
                document_id=document.id,
                owner_id=user.id,
                agent_id=payload.agent_id,
                chunk_index=index,
                content=content,
            )
        )
    await session.commit()
    await session.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id, KnowledgeDocument.owner_id == user.id
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
    filters = [KnowledgeChunk.owner_id == user.id]
    if agent_id:
        filters.append(or_(KnowledgeChunk.agent_id == agent_id, KnowledgeChunk.agent_id.is_(None)))
    rows = list((await session.scalars(select(KnowledgeChunk).where(*filters).limit(100))).all())
    documents = {
        row.id: row.title
        for row in (
            await session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.owner_id == user.id))
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
