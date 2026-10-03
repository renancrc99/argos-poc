"""Exceções de domínio."""


class LLMCompletionError(Exception):
    """Levantada quando um adapter de LLM falha ao gerar uma resposta."""


class StorageError(Exception):
    """Levantada quando um adapter de storage falha ao ler ou gravar um arquivo."""


class AgentNotFoundError(Exception):
    def __init__(self, agent_id: str):
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class AgentNotReadyError(Exception):
    def __init__(self, agent_id: str):
        super().__init__(f"Agent is not ready for chat: {agent_id}")
        self.agent_id = agent_id


class DocumentParsingError(Exception):
    def __init__(self, filename: str, reason: str):
        super().__init__(f"Failed to parse {filename}: {reason}")
        self.filename = filename


class MemoryIngestionError(Exception):
    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"Failed to ingest memory for agent {agent_id}: {reason}")
