# RAG Platform POC

Plataforma de agentes RAG com Memvid, FastAPI, React e LocalStack.

## Pré-requisitos

- Docker e Docker Compose instalados
- **Ollama** rodando localmente com o modelo Qwen (padrão) **ou** chave da API Anthropic

### Instalar o modelo Qwen no Ollama (padrão)

```bash
ollama pull qwen2.5:14b
```

### Instalar o modelo de embeddings 

```bash
ollama pull nomic-embed-text
```

## Como executar

### Com Ollama local (padrão — sem .env necessário)

```bash
docker compose up --build
```

### Com API Anthropic

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
echo "LLM_PROVIDER=anthropic" >> .env
docker compose up --build
```

### Trocar modelo sem mexer no código

```bash
# Outro modelo Ollama
OLLAMA_MODEL=qwen2.5:14b docker compose up --build

# Modelo Anthropic diferente
LLM_PROVIDER=anthropic ANTHROPIC_MODEL=claude-3-5-haiku-20241022 docker compose up --build
```

> **Linux:** o Ollama roda no host, não em `host.docker.internal`. Adicione ao `.env`:
> ```
> OLLAMA_BASE_URL=http://172.17.0.1:11434
> ```

## Acesso

| Serviço   | URL                              |
|-----------|----------------------------------|
| Frontend  | http://localhost:5173            |
| Swagger   | http://localhost:8000/docs       |

---

## Funcionalidades

### 1. Chat com Agente RAG

Crie um agente, ingira documentos (PDF, DOCX, TXT, MD) e converse com ele via chat. O pipeline RAG recupera trechos relevantes dos documentos e os injeta no contexto do LLM.

**Fluxo:**
1. Acesse `http://localhost:5173`
2. Clique em "Novo Agente" e preencha nome, descrição e system prompt
3. Na página do agente, faça upload de um ou mais documentos
4. Aguarde o status mudar para "ready"
5. Clique em "Testar Chat" e faça perguntas sobre os documentos

**Capacidades RAG configuráveis por agente:**
- Busca léxica BM25 (padrão)
- Busca híbrida BM25 + embeddings semânticos (requer Ollama `nomic-embed-text`)
- Multi-query: gera variantes da pergunta para aumentar recall
- Reranker LLM: reordena os chunks recuperados antes de montar o contexto

**Deduplicação de documentos:** o sistema calcula SHA-256 do arquivo e das configurações de chunking. Se o mesmo arquivo já foi ingerido com as mesmas configurações, o upload é ignorado automaticamente.

---

## Verificar se o S3 está funcionando

Após ingerir um documento, o arquivo original enviado deve aparecer no bucket de documentos do LocalStack:

```bash
docker compose exec infra-init \
  aws --endpoint-url=http://localstack:4566 s3 ls s3://rag-platform-docs/ --recursive
```

O índice de busca de cada agente (texto e embeddings dos chunks) fica em `/app/cache` dentro do container do backend (volume `memvid_cache`), não no S3:

```bash
docker compose exec backend ls -la /app/cache/
```
