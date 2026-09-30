"""Objeto de Valor para chunk de texto."""

from pydantic import BaseModel, ConfigDict


class Chunk(BaseModel):
    """Pedaço de texto extraído de um documento, pronto para indexação."""

    model_config = ConfigDict(frozen=True)

    text: str
    source_document: str
    page: int | None = None
    section: str | None = None
    index: int = 0
