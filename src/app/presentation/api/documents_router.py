"""Routes para ingestão e listagem de documentos."""

from typing import Optional

from fastapi import APIRouter, Header, UploadFile, File, Form, HTTPException

from app.container import container
from app.application.dtos.document_dtos import IngestDocumentInput, DocumentRecord
from app.domain.exceptions import AgentNotFoundError, LLMCompletionError, MemoryIngestionError, StorageError

router = APIRouter(prefix="/agents/{agent_id}/documents", tags=["documents"])


@router.post("", status_code=201)
async def upload_document(
    agent_id: str,
    file: UploadFile = File(...),
    chunk_size: Optional[int] = Form(default=None),
    chunk_overlap: Optional[int] = Form(default=None),
    x_benchmark: bool = Header(default=False),
):
    try:
        file_data = await file.read()
        result = await container.ingest_documents.execute(
            IngestDocumentInput(
                agent_id=agent_id,
                filename=file.filename or "unknown",
                content_type=file.content_type or "application/octet-stream",
                file_data=file_data,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                benchmark_mode=x_benchmark,
            )
        )
        return result
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except (StorageError, MemoryIngestionError, LLMCompletionError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[DocumentRecord])
async def list_documents(agent_id: str):
    try:
        return await container.list_documents.execute(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
