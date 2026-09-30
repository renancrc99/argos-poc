"""Utilitários de análise de texto (tokenização, similaridade, heurísticas de busca).

Lógica pura, sem I/O — usada tanto pelo adapter de memória quanto pelos use cases
e rotas de debug que precisam analisar queries. Antes vivia dentro do adapter de
memória, o que forçava outras camadas a importar direto de uma infraestrutura
concreta; agora é um utilitário compartilhado de verdade.
"""

import math
import re

# ---------------------------------------------------------------------------
# Stopwords (EN + PT) — reduzem ruído no BM25 e melhoram o IDF de termos úteis
# ---------------------------------------------------------------------------
STOPWORDS: frozenset[str] = frozenset({
    # Inglês
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "it",
    "its", "this", "that", "these", "those", "he", "she", "they", "we",
    "you", "i", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "than", "too",
    "very", "just", "so", "if", "then", "there", "up", "out", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "own", "said", "upon", "one", "two", "also", "now", "even",
    "over", "back", "still", "while", "much", "made", "great", "well",
    "long", "down", "get", "come", "came", "went", "go", "like", "see",
    "know", "take", "make", "look", "turn", "put", "say", "tell", "ask",
    # Português
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "da", "do",
    "das", "dos", "em", "na", "no", "nas", "nos", "por", "para", "com",
    "sem", "sob", "sobre", "que", "se", "não", "mais", "mas", "ou",
    "e", "é", "era", "são", "foi", "ser", "ter", "seu", "sua", "seus",
    "suas", "ele", "ela", "eles", "elas", "eu", "você", "nós", "eles",
    "este", "esta", "esse", "essa", "isso", "aqui", "ali", "já", "ainda",
    "também", "quando", "como", "onde", "porque", "pois", "ao", "aos",
    "à", "às", "pelo", "pela", "pelos", "pelas", "lhe", "lhes", "me",
    "te", "nos", "vos", "muito", "bem", "então", "assim", "até", "entre",
    "depois", "antes", "sempre", "nunca", "só", "todo", "toda", "todos",
})


def tokenize(text: str) -> list[str]:
    """Tokenização com remoção de stopwords e tokens curtos."""
    tokens = re.findall(r"[a-záàâãéèêíìîóòôõúùûçñ\w]+", text.lower())
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calcula similaridade coseno entre dois vetores."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def query_bm25_weight(query: str) -> float:
    """
    Analisa a query e retorna peso BM25 em [0.25, 0.80].

    Termos técnicos/exatos → maior peso BM25 (BM25 dominante).
    Linguagem natural/descritiva → menor peso BM25 (embedding dominante).
    """
    words = re.findall(r'\b\w+\b', query)
    if not words:
        return 0.5

    score = 0
    for w in words:
        if re.search(r'\d', w):
            score += 3   # números, códigos
        if re.search(r'[A-Z]{2,}', w):
            score += 2   # SIGLAS
        if w[0].isupper() and len(w) > 2:
            score += 1   # Nomes Próprios
        if re.search(r'[/_\-:.]', w):
            score += 2   # separadores técnicos/path
        if re.match(r'^v\d', w, re.I):
            score += 3   # strings de versão

    max_score = len(words) * 3
    ratio = min(score / max_score, 1.0) if max_score > 0 else 0.5
    return round(0.25 + ratio * 0.55, 2)  # [0.25, 0.80]
