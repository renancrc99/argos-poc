"""Porta para operações de storage de objetos (S3, GCS, sistema de arquivos local)."""

from abc import ABC, abstractmethod


class StoragePort(ABC):
    """Interface para upload e download de arquivos."""

    @abstractmethod
    async def upload_file(self, bucket: str, key: str, data: bytes) -> str:
        """Upload de arquivo. Retorna a key do objeto."""
        ...
