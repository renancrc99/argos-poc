"""Routes para chat com o agente."""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.container import container
from app.application.dtos.chat_dtos import ChatInput
from app.domain.exceptions import (
    AgentNotFoundError,
    AgentNotReadyError,
    LLMCompletionError,
    MemoryIngestionError,
    StorageError,
)

router = APIRouter(prefix="/agents/{agent_id}/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


@router.post("", responses={404: {"description": "Agent not found"}, 400: {"description": "Agent not ready"}, 500: {"description": "Internal server error"}})
async def chat(
    agent_id: str,
    req: ChatRequest,
    x_benchmark: bool = Header(default=False),
    x_benchmark_bm25_weight: float | None = Header(default=None),
):
    try:
        return await container.chat_with_agent.execute(
            ChatInput(
                agent_id=agent_id,
                message=req.message,
                conversation_history=req.conversation_history,
                benchmark_mode=x_benchmark,
                bm25_weight_override=x_benchmark_bm25_weight,
            )
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except AgentNotReadyError:
        raise HTTPException(status_code=400, detail="Agent has no documents yet. Upload documents first.")
    except (StorageError, MemoryIngestionError, LLMCompletionError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
