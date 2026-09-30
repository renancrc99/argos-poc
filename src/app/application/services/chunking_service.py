"""Serviço de chunking. Divide textos longos em pedaços menores para indexação."""

import structlog

from app.domain.value_objects.chunk import Chunk

logger = structlog.get_logger()

_SEPARATORS = ["\n\n", "\n", ". ", " "]

# Perfis de tamanho por volume de documento (caracteres) — política de
# auto-detecção usada quando chunk_size/chunk_overlap não são informados.
_AUTO_SMALL = (512, 64)      # pequeno: docs focados em Q&A, FAQs
_AUTO_MEDIUM = (1024, 128)   # médio: documentação típica
_AUTO_LARGE = (2048, 256)    # grande: livros, manuais longos
_SMALL_THRESHOLD_CHARS = 50_000
_MEDIUM_THRESHOLD_CHARS = 200_000


class ChunkingService:
    """Divide texto em chunks com overlap usando recursive character splitting."""

    def resolve_params(
        self, chunk_size: int | None, chunk_overlap: int | None, pages: list[dict]
    ) -> tuple[int, int]:
        """
        Retorna (chunk_size, chunk_overlap).
        Se ambos forem fornecidos, usa como estão (modo manual ou preset).
        Se algum for None, detecta automaticamente com base no total de caracteres do documento.
        """
        if chunk_size is not None and chunk_overlap is not None:
            return chunk_size, chunk_overlap

        total_chars = sum(len(p["text"]) for p in pages)
        if total_chars < _SMALL_THRESHOLD_CHARS:
            size, overlap = _AUTO_SMALL
        elif total_chars < _MEDIUM_THRESHOLD_CHARS:
            size, overlap = _AUTO_MEDIUM
        else:
            size, overlap = _AUTO_LARGE

        logger.info("chunk_params_auto", total_chars=total_chars, chunk_size=size, chunk_overlap=overlap)
        return size, overlap

    def split(self, pages: list[dict], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
        """
        Recebe lista de pages (do ParsingService) e retorna Chunks.
        Cada page é {"text": "...", "page": int|None, "source": "filename"}.
        """
        chunks: list[Chunk] = []
        chunk_index = 0

        for page in pages:
            text = page["text"]
            if not text.strip():
                continue

            text_chunks = self._recursive_split(text, chunk_size, chunk_overlap)
            for chunk_text in text_chunks:
                if chunk_text.strip():
                    chunks.append(
                        Chunk(
                            text=chunk_text.strip(),
                            source_document=page["source"],
                            page=page.get("page"),
                            index=chunk_index,
                        )
                    )
                    chunk_index += 1

        return chunks

    def _recursive_split(self, text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        """Divide texto recursivamente usando separadores hierárquicos."""
        if len(text) <= chunk_size:
            return [text]

        for separator in _SEPARATORS:
            parts = text.split(separator)
            if len(parts) == 1:
                continue
            return self._merge_parts(parts, separator, chunk_size, chunk_overlap)

        return self._split_by_size(text, chunk_size, chunk_overlap)

    def _merge_parts(
        self, parts: list[str], separator: str, chunk_size: int, chunk_overlap: int
    ) -> list[str]:
        """Junta partes pequenas em chunks respeitando o tamanho máximo."""
        chunks = []
        current = ""

        for part in parts:
            candidate = f"{current}{separator}{part}" if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = part

        if current:
            chunks.append(current)

        if chunk_overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for i in range(1, len(chunks)):
                overlap_text = chunks[i - 1][-chunk_overlap:]
                overlapped.append(f"{overlap_text} {chunks[i]}")
            return overlapped

        return chunks

    def _split_by_size(self, text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        """Último recurso: corta no tamanho exato com overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - chunk_overlap
        return chunks
