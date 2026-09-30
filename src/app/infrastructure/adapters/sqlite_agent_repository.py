"""Adaptador para persistência de agentes em SQLite."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.entities.agent import Agent
from app.domain.value_objects.agent_config import AgentConfig
from app.domain.ports.agent_repository_port import AgentRepositoryPort


class SQLiteAgentRepository(AgentRepositoryPort):

    def __init__(self, db_path: str = "/app/data/agents.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                config_json TEXT NOT NULL,
                total_documents INTEGER DEFAULT 0,
                total_chunks INTEGER DEFAULT 0,
                memory_version TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _row_to_agent(self, row: sqlite3.Row) -> Agent:
        config_data = json.loads(row["config_json"])
        return Agent(
            name=row["name"],
            description=row["description"],
            config=AgentConfig(**config_data),
            id=row["id"],
            status=row["status"],
            total_documents=row["total_documents"],
            total_chunks=row["total_chunks"],
            memory_version=row["memory_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _config_to_json(self, agent: Agent) -> str:
        return json.dumps({
            "system_prompt": agent.config.system_prompt,
            "persona": agent.config.persona,
            "language": agent.config.language,
            "fallback_message": agent.config.fallback_message,
            "max_context_chunks": agent.config.max_context_chunks,
            "max_history_messages": agent.config.max_history_messages,
            "temperature": agent.config.temperature,
            "enable_multiquery": agent.config.enable_multiquery,
            "multiquery_variants": agent.config.multiquery_variants,
            "use_embeddings": agent.config.use_embeddings,
            "search_mode": agent.config.search_mode,
            "enable_reranker": agent.config.enable_reranker,
        })

    async def save(self, agent: Agent) -> None:
        self._conn.execute(
            """INSERT INTO agents (id, name, description, status, config_json,
               total_documents, total_chunks, memory_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent.id, agent.name, agent.description, agent.status, self._config_to_json(agent),
             agent.total_documents, agent.total_chunks, agent.memory_version,
             agent.created_at.isoformat(), agent.updated_at.isoformat()),
        )
        self._conn.commit()

    async def find_by_id(self, agent_id: str) -> Agent | None:
        row = self._conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return self._row_to_agent(row) if row else None

    async def find_all(self) -> list[Agent]:
        rows = self._conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
        return [self._row_to_agent(r) for r in rows]

    async def update(self, agent: Agent) -> None:
        self._conn.execute(
            """UPDATE agents SET name=?, description=?, status=?, config_json=?,
               total_documents=?, total_chunks=?, memory_version=?, updated_at=?
               WHERE id=?""",
            (agent.name, agent.description, agent.status, self._config_to_json(agent),
             agent.total_documents, agent.total_chunks, agent.memory_version,
             agent.updated_at.isoformat(), agent.id),
        )
        self._conn.commit()

    async def delete(self, agent_id: str) -> None:
        self._conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self._conn.commit()
