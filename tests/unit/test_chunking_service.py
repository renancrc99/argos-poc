"""Unit tests for ChunkingService."""

import pytest
from app.application.services.chunking_service import ChunkingService


@pytest.fixture
def chunking_service() -> ChunkingService:
    return ChunkingService()


def test_split_short_text_produces_single_chunk(chunking_service: ChunkingService):
    pages = [{"text": "Short text.", "page": 1, "source": "doc.txt"}]
    chunks = chunking_service.split(pages, chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 1
    assert chunks[0].text == "Short text."
    assert chunks[0].source_document == "doc.txt"
    assert chunks[0].page == 1


def test_split_long_text_produces_multiple_chunks(chunking_service: ChunkingService):
    long_text = "word " * 100  # 500 chars > chunk_size=100
    pages = [{"text": long_text, "page": None, "source": "long.txt"}]
    chunks = chunking_service.split(pages, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1


def test_split_empty_text_produces_no_chunks(chunking_service: ChunkingService):
    pages = [{"text": "   ", "page": 1, "source": "empty.txt"}]
    chunks = chunking_service.split(pages, chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 0


def test_chunk_indexes_are_sequential(chunking_service: ChunkingService):
    long_text = "sentence. " * 50
    pages = [{"text": long_text, "page": 1, "source": "doc.txt"}]
    chunks = chunking_service.split(pages, chunk_size=100, chunk_overlap=20)
    for i, chunk in enumerate(chunks):
        assert chunk.index == i


def test_split_multiple_pages(chunking_service: ChunkingService):
    pages = [
        {"text": "Page one content.", "page": 1, "source": "doc.pdf"},
        {"text": "Page two content.", "page": 2, "source": "doc.pdf"},
    ]
    chunks = chunking_service.split(pages, chunk_size=100, chunk_overlap=20)
    assert len(chunks) == 2
    assert chunks[0].page == 1
    assert chunks[1].page == 2
