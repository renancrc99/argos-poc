"""Entrypoint da aplicação FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.presentation.api.agents_router import router as agents_router
from app.presentation.api.documents_router import router as documents_router
from app.presentation.api.chat_router import router as chat_router
from app.presentation.api.debug_router import router as debug_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)

app = FastAPI(
    title="RAG Platform POC",
    description="Plataforma de agentes RAG com Memvid",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(debug_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
