# Backend — RAG Platform POC

API do backend da plataforma de agentes RAG, em FastAPI + Python. Este documento cobre só o que está dentro de `backend/` — para o projeto completo (frontend, benchmark, infraestrutura), ver [README.md](README.md).

## Visão geral

Cada **agente** é configurado com um system prompt e parâmetros de recuperação, ingere documentos (PDF/DOCX/TXT/MD), e responde perguntas via chat combinando busca (léxica BM25, semântica por embeddings, ou híbrida) com geração por LLM (Ollama local ou Claude).

## Arquitetura

Arquitetura Hexagonal (Ports & Adapters) + DDD, em 4 camadas:

```
src/app/
├── domain/            # Entidades, Objetos de Valor, Portas (interfaces) — sem dependência de framework
│   ├── entities/         Agent, Document
│   ├── value_objects/    AgentConfig, Chunk
│   ├── ports/            AgentRepositoryPort, DocumentRepositoryPort, StoragePort,
│   │                     MemoryPort, LLMPort, EmbeddingPort
│   └── exceptions.py
├── application/       # Casos de uso e serviços — orquestra o domínio, não conhece infraestrutura concreta
│   ├── use_cases/        CreateAgent, GetAgent, ListAgents, DeleteAgent,
│   │                     IngestDocuments, ChatWithAgent, ListDocuments
│   ├── services/         ParsingService, ChunkingService, PromptBuilder, text_analysis, benchmark_timing
│   └── dtos/             DTOs de entrada/saída de cada caso de uso
├── infrastructure/    # Adapters — implementações concretas das Portas
│   └── adapters/         S3StorageAdapter, MemvidMemoryAdapter (BM25 + JSON),
│                         OllamaLLMAdapter, ClaudeLLMAdapter, OllamaEmbeddingAdapter,
│                         SQLiteAgentRepository, SQLiteDocumentRepository
├── presentation/api/  # Routers FastAPI — tradução HTTP ↔ casos de uso
│   ├── agents_router.py, documents_router.py, chat_router.py, debug_router.py
├── container.py       # Composition root: instancia adapters e monta os casos de uso (injeção de dependência)
├── settings.py        # Configuração via variáveis de ambiente (pydantic-settings)
└── main.py            # Entrypoint FastAPI
```

Regra de dependência: `presentation → application → domain`, e `infrastructure` implementa as portas do `domain`. Nenhuma camada de dentro (domain/application) importa nada de infrastructure ou presentation.

## Stack tecnológica

| Categoria | Biblioteca |
|---|---|
| Framework web | FastAPI + Uvicorn |
| Validação/config | Pydantic v2 + pydantic-settings |
| Banco relacional | SQLite (via `sqlite3`, sem ORM) |
| Object storage | boto3 (S3 / LocalStack) |
| Parsing de documentos | PyMuPDF (`fitz`) para PDF, `python-docx` para DOCX |
| Busca léxica | BM25 artesanal (IDF/TF próprio) |
| LLM | Ollama (`httpx` direto) ou Anthropic (`anthropic` SDK) |
| Logs | `structlog` |
| Testes | `pytest` + `pytest-asyncio` |

## Como rodar

O backend não tem `docker-compose.yml` próprio — faz parte do compose da raiz do projeto (`rag-platform-poc/docker-compose.yml`), junto com LocalStack e frontend:

```bash
cd rag-platform-poc
docker compose up --build backend localstack infra-init
```

A API sobe em `http://localhost:8000` (Swagger em `/docs`). Precisa do Ollama rodando no host (`ollama pull qwen2.5:14b` e, se for usar busca semântica, `ollama pull nomic-embed-text`) — ver [README.md](README.md) para o passo a passo completo de pré-requisitos.

**Rodar sem Docker** (desenvolvimento local): `pip install -e ".[dev]"` a partir de `backend/`, depois `uvicorn app.main:app --reload --app-dir src`. Atenção: o `[build-system]` do `pyproject.toml` (`setuptools.backends.legacy:build`) falha em algumas combinações de `pip`/`setuptools` mais novas fora do container (observado nesta máquina) — se `pip install -e .` falhar com `ModuleNotFoundError: No module named 'setuptools.backends'`, rode dentro do container mesmo, ou atualize o `[build-system]`.

## Configuração

Todas as variáveis vêm de `settings.py` (prefixo vazio, case-insensitive). As que realmente afetam o comportamento do backend:

| Variável | Default | Efeito |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `"ollama"` ou `"anthropic"` — escolhe o adapter de LLM |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Endpoint do Ollama |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Modelo de chat no Ollama |
| `ANTHROPIC_API_KEY` | `""` | Necessária se `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Modelo Claude |
| `EMBEDDING_ENABLED` | `false` | Habilita geração de embeddings na ingestão (necessário pra busca semântica/híbrida) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Modelo de embedding no Ollama |
| `MEMVID_CACHE_DIR` | `/app/cache` | Onde ficam os índices `{agent_id}.json` |
| `S3_BUCKET_NAME` | `rag-platform-docs` | Bucket onde os arquivos originais são armazenados |
| `AWS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | — | Config do client S3 (aponta pro LocalStack em dev) |

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/agents` | Cria agente |
| GET | `/agents` | Lista agentes |
| GET | `/agents/{id}` | Detalhe de um agente |
| DELETE | `/agents/{id}` | Remove agente, documentos e memória |
| POST | `/agents/{id}/documents` | Ingere um documento (multipart) |
| GET | `/agents/{id}/documents` | Lista documentos ingeridos |
| POST | `/agents/{id}/chat` | Envia mensagem, recebe resposta RAG |
| GET | `/agents/{id}/debug/search` | Inspeciona o que o retriever recupera pra uma query |
| GET | `/agents/{id}/debug/multiquery` | Testa a expansão de query do multiquery |

`/agents/{id}/chat` e `/agents/{id}/documents` aceitam o header `X-Benchmark: true` (e `/chat` também `X-Benchmark-Bm25-Weight`) para ativar cronometragem por etapa na resposta — usado pela ferramenta em `benchmark/`, sem efeito no comportamento normal quando ausente.

## Modelo de domínio

- **`Agent`** (entidade) — nome, descrição, `status` (`created`/`ready`/`error`), contadores, e uma `AgentConfig`.
- **`AgentConfig`** (objeto de valor, imutável) — system prompt, persona, idioma, `search_mode` (`bm25`/`semantic`/`hybrid`), `use_embeddings`, multiquery, reranker, temperatura. Valida os próprios limites (`Field(ge=..., le=...)`) — é sempre válido por construção.
- **`Document`** (entidade) — metadados de um arquivo ingerido: hash de conteúdo, hash de configuração (usado para deduplicação), estatísticas de chunk.
- **`Chunk`** (objeto de valor) — um pedaço de texto pronto pra indexação.

Persistência: `Agent`/`Document` em SQLite (`SQLiteAgentRepository`/`SQLiteDocumentRepository`, um arquivo `agents.db`); o índice de busca (texto + embeddings dos chunks) em JSON por agente (`MemvidMemoryAdapter`, apesar do nome não usa a biblioteca Memvid real — ver `divergencias-especificacao-vs-implementacao.md` na raiz do projeto); arquivos originais no S3/LocalStack.

## Pipeline RAG (`ChatWithAgentUseCase`)

1. Resolve o modo de busca efetivo e o peso BM25 (heurística adaptativa por query, ou fixo se vier de `X-Benchmark-Bm25-Weight`)
2. Se `enable_multiquery`: pede ao LLM variações da pergunta, busca com todas (`search_multi`)
3. Senão: busca direta (`search`)
4. Se `enable_reranker`: pede ao LLM uma nota de relevância por chunk e reordena
5. `PromptBuilder` monta as mensagens (system + histórico + pergunta) a partir do contexto recuperado
6. Chama o LLM configurado e retorna a resposta com as fontes citadas

## Testes

```bash
docker compose run --rm backend python -m pytest tests/ -v
```

11 testes (unitários: `chat_with_agent`, `chunking_service`, `create_agent`; integração: fluxo completo de ingestão). Não cobrem os routers HTTP nem os adapters de infraestrutura (S3, Ollama, Claude) diretamente.

## Ver também

- [README.md](README.md) — projeto completo (frontend, pré-requisitos, como acessar)
- [CODEBASE.md](CODEBASE.md) — referência técnica mais detalhada, arquivo por arquivo
- [divergencias-especificacao-vs-implementacao.md](../divergencias-especificacao-vs-implementacao.md) — onde a implementação diverge da especificação da monografia
- [benchmark/README.md](benchmark/README.md) — ferramenta de benchmark (pacote separado)
