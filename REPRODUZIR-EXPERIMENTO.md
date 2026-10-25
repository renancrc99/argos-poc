# Como reproduzir o experimento

Guia de reprodução da avaliação experimental do *pipeline* de recuperação da plataforma
Argos, correspondente ao Capítulo 6 da monografia. Qualquer pessoa com os pré-requisitos
abaixo deve conseguir obter os mesmos artefatos a partir deste repositório.

> **O que o experimento mede.** A qualidade da etapa de recuperação de informação
> (*recall*), o comportamento do mecanismo de contingência, a latência decomposta por
> etapa do ciclo de interação e o consumo de *tokens* por interação — em quatro
> configurações de *pipeline* e duas condições de organização do índice.
>
> O experimento **não** avalia a qualidade das respostas geradas pelo modelo de
> linguagem. Esse recorte é deliberado e está justificado na Seção 4.3 da monografia.

---

## 1. Pré-requisitos

### Software

| Item | Versão | Observação |
|---|---|---|
| Docker e Docker Compose | qualquer recente | sobe os quatro serviços da aplicação |
| Python | 3.11 ou superior | para a ferramenta de *benchmark* |
| Ollama | qualquer recente | roda no **host**, não em contêiner |

### Modelos

```bash
ollama pull qwen2.5:14b        # geração de respostas
ollama pull nomic-embed-text   # geração de embeddings
```

### Hardware

O modelo `qwen2.5:14b` exige aproximadamente 10 GB de memória de vídeo para rodar em
GPU. Sem isso, o Ollama executa em CPU e os tempos medidos deixam de representar o
sistema como projetado — ver a Seção 5 deste guia.

Reserve de **3 a 6 horas** de máquina para a execução completa. São 384 interações com
o modelo de linguagem, a cerca de 15 a 30 segundos cada, mais o tempo de ingestão do
corpus a cada configuração.

---

## 2. O que está neste repositório

```
argos-poc/
├─ docker-compose.yml          4 serviços: localstack, infra-init, backend, frontend
├─ REPRODUZIR-EXPERIMENTO.md   este guia
├─ dataset/
│  ├─ corpus/                  os 4 documentos do corpus, como foram ingeridos
│  ├─ corpus.json              manifesto do corpus
│  ├─ queries-consolidado.json 48 consultas para a condição consolidada
│  ├─ queries-segmentado.json  48 consultas para a condição segmentada
│  ├─ queries-smoke.json       5 consultas, para o teste de fumaça (ver 3.5)
│  └─ benchmark-perguntas.jsonl  conjunto de origem, legível por humanos
└─ benchmark/
   ├─ run_experimento.py       orquestrador das duas condições
   ├─ PATCH-runner-modo-indice.md  alterações necessárias para a condição segmentada
   ├─ cli.py                   interface de linha de comando da ferramenta
   └─ runs/                    saída de cada execução
```

### O corpus

Quatro documentos, 211 páginas, 50.907 palavras. Todos de uso livre: os textos legais
não constituem objeto de proteção autoral, conforme o art. 8º da Lei nº 9.610/1998, e os
demais são materiais de divulgação pública.

| Identificador | Documento | Formato |
|---|---|---|
| `cdc` | Código de Defesa do Consumidor e legislação correlata (compilação da Câmara dos Deputados) | PDF |
| `lgpd` | Lei nº 13.709/2018, texto atualizado | PDF |
| `mei` | Perguntas e Respostas — MEI e Simei (CGSN) | PDF |
| `pix` | Perguntas frequentes sobre o Pix (Caixa Econômica Federal) | TXT |

### O conjunto de consultas

48 consultas, 40 com resposta presente no corpus e 8 sem. As 40 com resposta possuem
verdade de referência anotada: 31 com um trecho e 9 com dois, totalizando 49 trechos.

As perguntas foram escritas **a partir dos trechos**, e não o contrário. Lê-se uma
passagem do documento e formula-se a pergunta que ela responde. Essa ordem impede que a
saída do sistema seja consultada durante a anotação, o que produziria métricas
artificialmente elevadas.

### As duas condições de índice

| Condição | Organização | Consultas fora da base |
|---|---|---|
| **Consolidado** | um agente com os quatro documentos | 8 perguntas sobre assuntos ausentes de todo o corpus |
| **Segmentado** | quatro agentes, um documento cada | 8 perguntas cruzadas: pergunta-se a um agente algo que só existe no corpus de outro |

No modo segmentado, as perguntas cruzadas cumprem duplo propósito: medem o acionamento
do mecanismo de contingência e verificam o isolamento entre *tenants*. Resposta
substantiva a qualquer uma delas caracterizaria vazamento entre agentes.

### As quatro configurações

| ID | Configuração | Vetorial | Léxica | Fusão | Expansão | Reordenação |
|---|---|:-:|:-:|:-:|:-:|:-:|
| A | Vetorial isolada | x | | | | |
| B | Léxica isolada | | x | | | |
| C | Híbrida | x | x | x | | |
| F | Completa | x | x | x | x | x |

A ferramenta também implementa as configurações D e E, que isolam individualmente a
expansão e a reordenação. Elas não integram o experimento da monografia, mas podem ser
acrescentadas com `--configs A B C D E F`.

---

## 3. Passo a passo

> **Convenções de terminal.** Todos os comandos deste guia estão escritos com **barra
> normal** (`/`) nos caminhos e em **uma única linha**. Nessa forma, são idênticos em
> PowerShell, Prompt de Comando, Git Bash, WSL, Linux e macOS — basta copiar e colar.
> As diferenças aparecem apenas quando se quer quebrar um comando longo em várias linhas
> ou definir variáveis de ambiente:
>
> | | PowerShell / Prompt de Comando | Git Bash / WSL / Linux / macOS |
> |---|---|---|
> | Separador de caminho | `dataset/corpus.json` ou `dataset\corpus.json` | **somente** `dataset/corpus.json` |
> | Quebra de linha | acento grave `` ` `` ao fim da linha | contrabarra `\` ao fim da linha |
> | Variável de ambiente | `$env:OLLAMA_MODEL = "qwen2.5:3b"` | `export OLLAMA_MODEL=qwen2.5:3b` |
> | Cliente HTTP | `curl.exe` — no PowerShell 5.1, `curl` é apelido de `Invoke-WebRequest` e tem outra sintaxe | `curl` |
>
> **A pegadinha mais comum.** No Git Bash, a contrabarra é caractere de escape, não
> separador de caminho: `--corpus dataset\corpus.json` chega ao Python como
> `datasetcorpus.json` e o programa aborta com `FileNotFoundError`. Caminhos copiados do
> Explorador de Arquivos do Windows vêm com contrabarra e precisam ser convertidos.

### 3.1 Subir a aplicação

Na raiz do repositório:

```bash
docker compose up --build
```

Aguarde até o *backend* responder. Confirme com:

```bash
curl http://localhost:8000/docs
```

No PowerShell, use `curl.exe http://localhost:8000/docs` — ou abra o endereço no
navegador, que serve igualmente como verificação.

**No Linux**, o Ollama não é alcançável por `host.docker.internal`. Crie um arquivo
`.env` na raiz antes de subir:

```
OLLAMA_BASE_URL=http://172.17.0.1:11434
```

| Serviço | Endereço |
|---|---|
| API do *backend* | http://localhost:8000 |
| Documentação da API | http://localhost:8000/docs |
| Interface web | http://localhost:5173 |
| LocalStack | http://localhost:4566 |

### 3.2 Confirmar que o modelo está em GPU

**Este passo não é opcional.** Com o *backend* no ar e após a primeira interação:

```bash
ollama ps
```

A coluna `PROCESSOR` deve indicar `GPU` ou um percentual de GPU. Se indicar `100% CPU`,
o modelo está rodando em processador, e os tempos medidos **não representam o sistema
como projetado**. As métricas de recuperação continuam válidas — elas não dependem do
tempo —, mas nenhum número de latência deve ser usado antes de resolver isso.

O orquestrador faz essa verificação automaticamente e emite um alerta, mas confira
manualmente também.

### 3.3 Instalar a ferramenta de *benchmark*

Em um ambiente Python separado do *backend*:

```bash
cd benchmark
pip install -e .
```

> **Como o pacote é resolvido.** O `pip install -e .` instala apenas as dependências
> (`httpx`, `pydantic`, `scipy`, `matplotlib`, `psutil`, `pyyaml`) — nenhum pacote
> importável é registrado, o que é esperado. O módulo `benchmark.cli` é resolvido como
> *namespace package*, e por isso **só funciona com a raiz do repositório como diretório
> de trabalho**. O orquestrador já cuida disso; se chamar a CLI diretamente, veja a
> observação em 3.5.

### 3.4 Aplicar o patch da condição segmentada

A condição consolidada funciona sem alteração nenhuma. Para rodar também a segmentada,
aplique as três alterações descritas em `benchmark/PATCH-runner-modo-indice.md`: dois
campos em `dataset/schema.py`, o método `run` em `ablation/runner.py` e um argumento em
`cli.py`.

Sem `--index-mode`, o comportamento permanece idêntico ao original.

### 3.5 Executar

A ferramenta é chamada **a partir da raiz do repositório**, nunca de dentro de
`benchmark/` — ver a observação sobre *namespace package* em 3.3.

#### Teste de fumaça — faça antes da execução completa

Cinco consultas, uma configuração, poucos minutos. Confirma que o *backend* responde, que
a ingestão do corpus conclui, que o roteamento das consultas funciona e que o mecanismo de
contingência é acionado — sem esperar as horas da execução completa.

O arquivo `dataset/queries-smoke.json` traz uma consulta de cada documento mais uma fora
da base. Na raiz do repositório:

```bash
python -m benchmark.cli run --corpus dataset/corpus.json --queries dataset/queries-smoke.json --corpus-root dataset --api http://localhost:8000 --chunking medio --configs A --out-dir benchmark/runs/smoke-consolidado --tag smoke --index-mode consolidado
```

E, se a condição segmentada for rodar — é o caminho de código acrescentado pelo patch de
3.4, vale exercitá-lo:

```bash
python -m benchmark.cli run --corpus dataset/corpus.json --queries dataset/queries-smoke.json --corpus-root dataset --api http://localhost:8000 --chunking medio --configs A --out-dir benchmark/runs/smoke-segmentado --tag smoke --index-mode segmentado
```

O que verificar na saída:

| Sinal | Consolidado | Segmentado |
|---|---|---|
| Agentes criados | uma linha `agente _todos: … — corpus ingerido` | **quatro** linhas: `cdc`, `lgpd`, `mei`, `pix` |
| Destino das consultas | todas com `-> _todos ok` | cada uma no agente do seu documento |
| Linhas `sem agente de destino, pulada` | nenhuma | nenhuma |
| `foratudo-001` | deve cair na resposta de contingência | idem |

Uma linha `sem agente de destino, pulada` indica que o campo `target_document` não chegou
ao modelo de dados: o patch em `dataset/schema.py` (3.4) não foi aplicado, e o Pydantic
descartou o campo silenciosamente.

A ingestão é a parte demorada — 211 páginas de *embeddings*. No modo segmentado ela ocorre
quatro vezes, uma por agente, de modo que o segundo comando leva mais tempo que o primeiro
ainda que as consultas sejam as mesmas.

#### Execução completa

```bash
cd benchmark
python run_experimento.py --api http://localhost:8000
```

O orquestrador captura a especificação do ambiente, verifica a GPU, copia o *dataset* para
dentro da pasta da execução e roda as duas condições em pastas separadas. É o único
comando que se chama de dentro de `benchmark/`: ele próprio executa a CLI com a raiz do
repositório como diretório de trabalho.

Opções úteis:

```bash
python run_experimento.py --condicoes consolidado    # só uma das condições
python run_experimento.py --chunking pequeno         # outro perfil de segmentação
```

#### Chamando a ferramenta diretamente

Sem o orquestrador, para controlar cada parâmetro. Na raiz do repositório, em uma linha —
forma que funciona em qualquer terminal:

```bash
python -m benchmark.cli run --corpus dataset/corpus.json --queries dataset/queries-consolidado.json --corpus-root dataset --api http://localhost:8000 --chunking medio --configs A B C F --index-mode consolidado --out-dir benchmark/runs/teste_consolidado
```

A mesma chamada quebrada em várias linhas, para leitura — **Git Bash, WSL, Linux, macOS**
(contrabarra ao fim da linha):

```bash
python -m benchmark.cli run \
    --corpus dataset/corpus.json \
    --queries dataset/queries-consolidado.json \
    --corpus-root dataset \
    --api http://localhost:8000 \
    --chunking medio \
    --configs A B C F \
    --index-mode consolidado \
    --out-dir benchmark/runs/teste_consolidado
```

E em **PowerShell** (acento grave ao fim da linha):

```powershell
python -m benchmark.cli run `
    --corpus dataset/corpus.json `
    --queries dataset/queries-consolidado.json `
    --corpus-root dataset `
    --api http://localhost:8000 `
    --chunking medio `
    --configs A B C F `
    --index-mode consolidado `
    --out-dir benchmark/runs/teste_consolidado
```

Rodar de dentro de `benchmark/` produz `No module named benchmark`: o diretório
`benchmark/` precisa estar visível a partir do diretório de trabalho para o *namespace
package* resolver.

> **Atenção.** O `raw.jsonl` é aberto em modo de acréscimo. Rodar duas vezes apontando
> para a mesma pasta de saída duplica os registros e corrompe as métricas. O orquestrador
> cria uma pasta nova a cada execução; se chamar a CLI diretamente, use sempre um
> `--out-dir` inédito — inclusive ao repetir o teste de fumaça.

---

## 4. O que sai

```
benchmark/runs/monografia_<carimbo>/
├─ ambiente.json               hardware, versões, verificação de GPU
├─ resumo.json                 duração, configurações, status de cada condição
├─ dataset/                    cópia do corpus e das consultas usados
├─ consolidado/
│  ├─ raw.jsonl                um registro por interação
│  ├─ aggregate.csv            métricas agregadas por configuração
│  ├─ timing_stats.csv         n, média, desvio, p50, p90, p95, p99 por etapa
│  └─ report.md                relatório legível
└─ segmentado/
   └─ (mesma estrutura)
```

### Onde encontrar cada métrica

| Métrica | Arquivo | Campo |
|---|---|---|
| *Recall*@1 e *recall*@5 | `aggregate.csv` | `recall@1`, `recall@5` |
| Acionamento correto e indevido | `aggregate.csv` | `fallback_correto`, `fallback_indevido` |
| Tempo de busca, p95 | `timing_stats.csv` | etapa `busca_total`, estatística `p95` |
| Tempo total, p95 | `timing_stats.csv` | etapa `t_total`, estatística `p95` |
| *Tokens* por interação | `aggregate.csv` | `avg_input_tokens`, `avg_output_tokens` |

A etapa `busca_total` é a soma de `t_search_vector`, `t_search_lexical` e `t_fusion`
calculada **por interação antes da agregação** — não é a soma das três médias, porque
percentil não é operação linear.

### Bases de cálculo

Os indicadores não compartilham o mesmo denominador:

| Indicador | Consultas | Peso de uma consulta |
|---|---:|---:|
| *Recall*@1 e *recall*@5 | 40 | 2,5 p.p. |
| Acionamento indevido | 40 | 2,5 p.p. |
| Acionamento correto | 8 | 12,5 p.p. |
| Latência e *tokens* | 48 | — |

Diferenças correspondentes a uma ou duas consultas não devem ser interpretadas como
resultado.

### Recalcular sem rodar de novo

O `raw.jsonl` guarda um registro por interação, com todos os tempos brutos. Qualquer
estatística nova pode ser derivada dele sem repetir a execução:

```bash
python -m benchmark.cli aggregate \
    --raw runs/monografia_<carimbo>/consolidado/raw.jsonl \
    --out-dir runs/monografia_<carimbo>/consolidado
```

---

## 5. Condições de reprodutibilidade

### O que está fixado

- **Temperatura do modelo em zero**, definida em `ablation/configs.py`
- **Perfil de segmentação `medio`**: 1024 caracteres com sobreposição de 128
- **`max_context_chunks` em 10** nos agentes de ablação, para cobrir *recall*@10 com uma
  única chamada ao `/chat`
- **Corpus e consultas versionados** no repositório e copiados para dentro de cada
  execução

### O que varia entre máquinas

Os **tempos** são específicos do hardware. Processador, GPU, memória e versão do Ollama
mudam a latência observada. Por isso o `ambiente.json` registra essas informações a cada
execução, e qualquer comparação entre resultados exige confrontar os dois arquivos.

As **métricas de recuperação** são reproduzíveis nas configurações A, B e C, cujo
resultado é determinístico: a pontuação BM25, a similaridade de cosseno e a fusão
ponderada são funções determinísticas da consulta e do índice. A configuração F depende
do modelo de linguagem na expansão de consultas e na reordenação; mesmo com temperatura
zero, pequenas variações entre execuções são possíveis.

### Como a verdade de referência é verificada

O casamento entre um trecho anotado e um resultado retornado exige duas condições: mesmo
arquivo de origem e sobreposição textual de ao menos 50% do trecho anotado dentro do
*chunk* recuperado. A comparação usa o campo `reference_quote`, não os deslocamentos
numéricos — o que torna o casamento tolerante a diferenças de formatação entre
extratores de PDF.

---

## 6. Limitações conhecidas

1. **Os tempos não se generalizam.** A execução ocorre em máquina única com modelo de
   linguagem local. A arquitetura de produção projetada emprega serviço gerenciado, com
   características de latência distintas.

2. **A busca percorre o índice integralmente.** A implementação atual não utiliza
   estrutura de indexação que reduza o espaço de busca, de modo que o tempo cresce
   proporcionalmente ao volume de *chunks* armazenados. Os tempos medidos caracterizam a
   escala de corpus testada, não uma propriedade estrutural.

3. **Dois dos quatro analisadores sintáticos são exercitados.** O corpus emprega PDF e
   texto simples; os analisadores de DOCX e *Markdown* não são acionados.

4. **A qualidade das respostas não é avaliada.** O experimento mede a etapa de
   recuperação. A avaliação das respostas geradas exigiria anotação humana de conjunto
   representativo de interações.

5. **O subconjunto de contingência é pequeno.** Oito consultas fora da base conferem
   granularidade de 12,5 pontos percentuais à taxa de acionamento correto.

---

## 7. Solução de problemas

**O *backend* não sobe.** Verifique se as portas 8000, 5173 e 4566 estão livres. O
serviço `infra-init` precisa concluir antes do `backend`; se falhar, confira os registros
do `localstack`.

**Erro de conexão com o Ollama.** No Linux, defina `OLLAMA_BASE_URL=http://172.17.0.1:11434`
no `.env`. Em Windows e macOS, `host.docker.internal` costuma funcionar sem ajuste.
Confirme que o serviço está no ar com `ollama list`.

**Respostas muito lentas.** Rode `ollama ps` e verifique o processador em uso. Em CPU, o
`qwen2.5:14b` pode levar minutos por resposta. Para validar o fluxo sem esperar, use um
modelo menor definindo `OLLAMA_MODEL=qwen2.5:3b` — mas não use esses resultados na
análise.

**Nenhum trecho é dado como recuperado.** Confirme que os arquivos em `dataset/corpus/`
são exatamente os mesmos que geraram as anotações. Substituir um documento por outra
versão invalida a verdade de referência.

**`httpx.RemoteProtocolError: Server disconnected without sending a response`.** O
*backend* encerrou a conexão antes de responder. Duas causas prováveis: a geração
ultrapassou o tempo limite de 180 segundos do cliente — comum com o modelo em CPU — ou o
contêiner do *backend* ficou sem memória e foi reiniciado. Verifique com
`docker compose logs backend --tail 50` e confirme a GPU com `ollama ps`. Se o problema
persistir com GPU ativa, aumente o `timeout` em `AblationRunner.__init__`.

**`No module named benchmark`.** Você está chamando a CLI de dentro de `benchmark/`.
Volte para a raiz do repositório — ver 3.5. A exceção é o `run_experimento.py`, que é
chamado de dentro de `benchmark/` justamente por cuidar disso sozinho.

**`FileNotFoundError: 'datasetcorpus.json'`** (ou qualquer caminho com as barras
desaparecidas). Você está no Git Bash e passou o caminho com contrabarra, que ali é
caractere de escape. Troque `dataset\corpus.json` por `dataset/corpus.json` — ver as
convenções de terminal no início do capítulo 3.

**`unrecognized arguments: --index-mode`.** O patch de 3.4 não foi aplicado neste clone.
Sem ele, só a condição consolidada roda, e sem o argumento.

**Linhas `sem agente de destino, pulada` no modo segmentado.** O patch foi aplicado em
`cli.py` e `ablation/runner.py`, mas não em `dataset/schema.py`: sem o campo
`target_document` no modelo, o Pydantic descarta o destino de cada consulta.

**Para testar o fluxo rapidamente**, use o teste de fumaça de 3.5: cinco consultas, uma
configuração, poucos minutos.

---

## 8. Citação

Ao reutilizar o conjunto de consultas ou a verdade de referência, registre a versão do
repositório empregada. Os resultados reportados na monografia correspondem ao estado do
repositório na data de execução indicada em `ambiente.json`.
