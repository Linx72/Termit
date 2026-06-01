from fastapi import APIRouter, Depends

from app.domain.schemas import (
    RetrievalIndexResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalChunkResponse,
    RepoMapResponse,
    SymbolSearchRequest,
    SymbolSearchResponse,
    SymbolMatchResponse,
)
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.repo_map_service import RepoMapService
from app.services.symbol_index_service import SymbolIndexService
from app.state import get_code_retrieval_service, get_repo_map_service, get_symbol_index_service

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
    stats = service.stats()
    return RetrievalIndexResponse(
        indexed_files=indexed_files,
        indexed_chunks=indexed_chunks,
        retrieval_mode=str(stats.get("mode", service.mode)),
    )


@router.get("/stats", response_model=RetrievalIndexResponse)
async def retrieval_stats(
    service: CodeRetrievalService = Depends(get_code_retrieval_service),
) -> RetrievalIndexResponse:
    stats = service.stats()
    return RetrievalIndexResponse(
        indexed_files=int(stats["indexed_files"]),
        indexed_chunks=int(stats["indexed_chunks"]),
        retrieval_mode=str(stats.get("mode", service.mode)),
    )


@router.get("/repo-map", response_model=RepoMapResponse)
async def repo_map(
    path_prefix: str = "",
    service: RepoMapService = Depends(get_repo_map_service),
) -> RepoMapResponse:
    return RepoMapResponse(
        summary=service.build_summary(path_prefix=path_prefix),
        root_path=str(service.root),
    )


@router.post("/symbols/search", response_model=SymbolSearchResponse)
async def search_symbols(
    payload: SymbolSearchRequest,
    service: SymbolIndexService = Depends(get_symbol_index_service),
) -> SymbolSearchResponse:
    matches = service.search(payload.query, limit=payload.limit, path_prefix=payload.path_prefix)
    return SymbolSearchResponse(
        query=payload.query,
        total=len(matches),
        matches=[
            SymbolMatchResponse(
                name=item.name,
                kind=item.kind,
                path=item.path,
                line=item.line,
                callers=[
                    service.format_graph_ref(edge.caller_path, edge.caller_line, edge.caller_name)
                    for edge in service.callers_of(item.name, limit=5)
                ],
                callees=[
                    service.format_graph_ref(edge.path, edge.line, edge.callee_name)
                    for edge in service.callees_of(item.name, limit=5)
                ],
            )
            for item in matches
        ],
    )


@router.post("/symbols/reindex")
async def reindex_symbols(
    service: SymbolIndexService = Depends(get_symbol_index_service),
) -> dict[str, int]:
    total = service.reindex()
    return {"symbols": total}
