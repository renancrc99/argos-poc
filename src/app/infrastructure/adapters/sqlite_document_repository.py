"""Adaptador para persistência de documentos em SQLite."""

import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.entities.document import Document
from app.domain.ports.document_repository_port import DocumentRepositoryPort


class SQLiteDocumentRepository(DocumentRepositoryPort):

    def __init__(self, db_path: str = "/app/data/agents.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                s3_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processed',
                chunk_size INTEGER DEFAULT 512,
                chunk_overlap INTEGER DEFAULT 64,
                chunk_count INTEGER DEFAULT 0,
                chunk_min_chars INTEGER DEFAULT 0,
                chunk_max_chars INTEGER DEFAULT 0,
                chunk_avg_chars REAL DEFAULT 0.0,
                chunk_total_chars INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()
        self._migrate_table()

    def _migrate_table(self) -> None:
        """Adiciona colunas introduzidas após a criação inicial da tabela."""
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(documents)").fetchall()}
        for col, definition in [
            ("chunk_size",   "INTEGER DEFAULT 512"),
            ("chunk_overlap","INTEGER DEFAULT 64"),
            ("file_hash",    "TEXT NOT NULL DEFAULT ''"),
            ("config_hash",  "TEXT NOT NULL DEFAULT ''"),
        ]:
            if col not in existing:
                self._conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {definition}")
        self._conn.commit()

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            agent_id=row["agent_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            s3_key=row["s3_key"],
            status=row["status"],
            chunk_size=row["chunk_size"],
            chunk_overlap=row["chunk_overlap"],
            chunk_count=row["chunk_count"],
            chunk_min_chars=row["chunk_min_chars"],
            chunk_max_chars=row["chunk_max_chars"],
            chunk_avg_chars=row["chunk_avg_chars"],
            chunk_total_chars=row["chunk_total_chars"],
            created_at=datetime.fromisoformat(row["created_at"]),
            file_hash=row["file_hash"] or "",
            config_hash=row["config_hash"] or "",
        )

    async def save(self, document: Document) -> None:
        self._conn.execute(
            """INSERT INTO documents (id, agent_id, filename, content_type, size_bytes,
               s3_key, status, chunk_size, chunk_overlap, chunk_count,
               chunk_min_chars, chunk_max_chars, chunk_avg_chars, chunk_total_chars,
               created_at, file_hash, config_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                document.id, document.agent_id, document.filename,
                document.content_type, document.size_bytes, document.s3_key,
                document.status, document.chunk_size, document.chunk_overlap,
                document.chunk_count,
                document.chunk_min_chars, document.chunk_max_chars,
                document.chunk_avg_chars, document.chunk_total_chars,
                document.created_at.isoformat(),
                document.file_hash, document.config_hash,
            ),
        )
        self._conn.commit()

    async def find_by_config_hash(self, agent_id: str, config_hash: str) -> Document | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE agent_id = ? AND config_hash = ? LIMIT 1",
            (agent_id, config_hash),
        ).fetchone()
        return self._row_to_document(row) if row else None

    async def find_by_agent(self, agent_id: str) -> list[Document]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE agent_id = ? ORDER BY created_at DESC",
            (agent_id,),
        ).fetchall()
        return [self._row_to_document(r) for r in rows]

    async def delete_by_agent(self, agent_id: str) -> None:
        self._conn.execute("DELETE FROM documents WHERE agent_id = ?", (agent_id,))
        self._conn.commit()
