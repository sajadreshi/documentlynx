"""API routes for document and question management."""

import logging
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import authenticate_client
from app.database import get_db
from app.models import ClientCredential, Document, Question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documently/api/v1", tags=["Documents & Questions"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DocumentListItem(BaseModel):
    id: str
    filename: str
    status: str
    question_count: int
    file_type: Optional[str] = None
    created_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentDetail(BaseModel):
    id: str
    user_id: str
    filename: str
    source_url: Optional[str] = None
    status: str
    question_count: int
    file_type: Optional[str] = None
    public_markdown: Optional[str] = None
    created_at: Optional[str] = None


class QuestionListItem(BaseModel):
    id: str
    question_number: Optional[int] = None
    question_type: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    preview: str = ""


class QuestionListResponse(BaseModel):
    questions: list[QuestionListItem]
    total: int
    page: int
    page_size: int


class QuestionDetail(BaseModel):
    id: str
    document_id: str
    user_id: str
    question_number: Optional[int] = None
    question_text: str
    question_type: Optional[str] = None
    options: Optional[dict] = None
    correct_answer: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    grade_level: Optional[str] = None
    cognitive_level: Optional[str] = None
    tags: Optional[list] = None
    is_classified: bool = False
    image_urls: Optional[list] = None
    created_at: Optional[str] = None


class QuestionUpdateRequest(BaseModel):
    question_text: str = Field(..., min_length=1)
    options: Optional[Dict[str, str]] = None
    correct_answer: Optional[str] = None
    re_embed: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    user_id: str = Query(..., description="User ID to list documents for"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    client: ClientCredential = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """List documents for a user (paginated)."""
    query = db.query(Document).filter(Document.user_id == user_id)
    total = query.count()

    docs = (
        query.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return DocumentListResponse(
        documents=[
            DocumentListItem(
                id=str(d.id),
                filename=d.filename,
                status=d.status or "processed",
                question_count=d.question_count or 0,
                file_type=d.file_type,
                created_at=d.created_at.isoformat() if d.created_at else None,
            )
            for d in docs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    client: ClientCredential = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Get document detail (metadata + markdown)."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    doc = db.query(Document).filter(Document.id == doc_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail(
        id=str(doc.id),
        user_id=doc.user_id,
        filename=doc.filename,
        source_url=doc.source_url,
        status=doc.status or "processed",
        question_count=doc.question_count or 0,
        file_type=doc.file_type,
        public_markdown=doc.public_markdown,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.get(
    "/documents/{document_id}/questions",
    response_model=QuestionListResponse,
)
async def list_questions(
    document_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    client: ClientCredential = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Paginated question list for a document."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    query = db.query(Question).filter(Question.document_id == doc_uuid)
    total = query.count()

    questions = (
        query.order_by(Question.question_number.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return QuestionListResponse(
        questions=[
            QuestionListItem(
                id=str(q.id),
                question_number=q.question_number,
                question_type=q.question_type,
                topic=q.topic,
                difficulty=q.difficulty,
                preview=(q.question_text or "")[:200],
            )
            for q in questions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/documents/{document_id}/questions/{question_id}",
    response_model=QuestionDetail,
)
async def get_question(
    document_id: str,
    question_id: str,
    client: ClientCredential = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Get full question data including markdown."""
    try:
        q_uuid = uuid.UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid question ID format")

    question = db.query(Question).filter(Question.id == q_uuid).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    return QuestionDetail(
        id=str(question.id),
        document_id=str(question.document_id),
        user_id=question.user_id,
        question_number=question.question_number,
        question_text=question.question_text,
        question_type=question.question_type,
        options=question.options,
        correct_answer=question.correct_answer,
        difficulty=question.difficulty,
        topic=question.topic,
        subtopic=question.subtopic,
        grade_level=question.grade_level,
        cognitive_level=question.cognitive_level,
        tags=question.tags,
        is_classified=question.is_classified or False,
        image_urls=question.image_urls,
        created_at=question.created_at.isoformat() if question.created_at else None,
    )


@router.put(
    "/documents/{document_id}/questions/{question_id}",
    response_model=QuestionDetail,
)
async def update_question(
    document_id: str,
    question_id: str,
    body: QuestionUpdateRequest,
    client: ClientCredential = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Update question text, optionally re-embed and re-classify."""
    try:
        q_uuid = uuid.UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid question ID format")

    question = db.query(Question).filter(Question.id == q_uuid).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    question.question_text = body.question_text
    if body.options is not None:
        question.options = body.options
    if body.correct_answer is not None:
        question.correct_answer = body.correct_answer

    # Optionally re-embed
    if body.re_embed:
        try:
            from app.services.embedding_service import EmbeddingService

            svc = EmbeddingService()
            text = svc.build_question_text(question)
            embedding = svc.embed_text(text)
            question.embedding = embedding
            question.is_embedded = True
        except Exception as e:
            logger.warning(f"Re-embedding failed for question {question_id}: {e}")

    db.commit()
    db.refresh(question)

    return QuestionDetail(
        id=str(question.id),
        document_id=str(question.document_id),
        user_id=question.user_id,
        question_number=question.question_number,
        question_text=question.question_text,
        question_type=question.question_type,
        options=question.options,
        correct_answer=question.correct_answer,
        difficulty=question.difficulty,
        topic=question.topic,
        subtopic=question.subtopic,
        grade_level=question.grade_level,
        cognitive_level=question.cognitive_level,
        tags=question.tags,
        is_classified=question.is_classified or False,
        image_urls=question.image_urls,
        created_at=question.created_at.isoformat() if question.created_at else None,
    )
