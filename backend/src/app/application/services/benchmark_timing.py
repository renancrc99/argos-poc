"""Cronometragem por etapa, usada só em modo benchmark (ver X-Benchmark em chat_router.py).

Usa contextvars pra acumular tempos por etapa sem alterar assinatura de nenhuma
função ao longo da cadeia de chamadas: quem quiser medir uma etapa só precisa
envolver o trecho com `with stage("nome_da_etapa"): ...`, desde que isso rode
dentro de uma sessão aberta por `session()`. Fora de uma sessão, `stage()` é
um no-op de custo desprezível (só verifica a contextvar).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_timings: ContextVar["dict[str, float] | None"] = ContextVar("_benchmark_timings", default=None)


def is_active() -> bool:
    """True se há uma sessão de cronometragem aberta no contexto atual."""
    return _timings.get() is not None


@contextmanager
def session() -> Iterator[dict[str, float]]:
    """Abre uma sessão de cronometragem. Toda chamada a `stage()` feita dentro
    deste bloco (mesmo em outras funções/módulos chamados a partir daqui)
    acumula no mesmo dict, disponível para leitura ao final do bloco."""
    timings: dict[str, float] = {}
    token = _timings.set(timings)
    try:
        yield timings
    finally:
        _timings.reset(token)


def record(name: str, value: float) -> None:
    """Registra diretamente um valor já calculado para a etapa `name` (soma se repetida).
    Complementa `stage()` para casos em que o tempo não é "da entrada até a saída de um
    bloco" — ex: tempo até o primeiro token de uma resposta em streaming, medido manualmente
    a partir de um instante de referência anterior."""
    timings = _timings.get()
    if timings is None:
        return
    timings[name] = timings.get(name, 0.0) + value


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Cronometra um trecho e soma o tempo à etapa `name`. Chamadas repetidas
    à mesma etapa (ex: t_search_lexical em cada query do multiquery) somam
    entre si, refletindo o tempo total gasto naquela etapa na interação."""
    timings = _timings.get()
    if timings is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        timings[name] = timings.get(name, 0.0) + elapsed
