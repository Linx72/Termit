from fastapi import APIRouter, Depends

from app.domain.schemas import (
    RetrievalIndexResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalChunkResponse,
)
from app.services.code_retrieval_service import CodeRetrievalService
from app.state import get_code_retrieval_service

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalSearchResponse)
async def search_code(
    payload: RetrievalSearchRequest,
    service: CodeRetrievalService = Depends(get_code_retrieval_service),
) -> RetrievalSearchResponse:
    chunks = service.search(
        payload.query,
        limit=payload.limit,
        path_prefix=payload.path_prefix,
    )
    return RetrievalSearchResponse(
        query=payload.query,
        total=len(chunks),
        chunks=[
            RetrievalChunkResponse(
                path=item.path,
                score=round(item.score, 4),
                line_start=item.line_start,
                line_end=item.line_end,
                excerpt=item.excerpt,
            )
            for item in chunks
        ],
    )


@router.post("/reindex", response_model=RetrievalIndexResponse)
async def reindex_codebase(
    service: CodeRetrievalService = Depends(get_code_retrieval_service),
) -> RetrievalIndexResponse:
    indexed_files, indexed_chunks = service.reindex()
    return RetrievalIndexResponse(
        indexed_files=indexed_files,
        indexed_chunks=indexed_chunks,
    )


@router.get("/stats", response_model=RetrievalIndexResponse)
async def retrieval_stats(
    service: CodeRetrievalService = Depends(get_code_retrieval_service),
) -> RetrievalIndexResponse:
    stats = service.stats()
    return RetrievalIndexResponse(
        indexed_files=stats["indexed_files"],
        indexed_chunks=stats["indexed_chunks"],
    )
