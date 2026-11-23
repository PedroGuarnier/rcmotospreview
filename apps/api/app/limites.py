"""Limites de tentativas por janela de tempo, em memória.

Servem para o login (força bruta) e para a consulta pública de placa. Em memória basta:
a API roda em um processo só, e zerar ao reiniciar não é problema.
"""

import time
from collections import defaultdict, deque

from fastapi import Request


def ip_do_cliente(request: Request) -> str:
    """IP de quem chamou: o último salto do X-Forwarded-For (escrito pelo proxy da frente).

    O primeiro valor do cabeçalho é o que o próprio cliente manda e não é confiável.
    """
    encaminhado = request.headers.get("x-forwarded-for", "")
    ultimo = encaminhado.split(",")[-1].strip()
    return ultimo or (request.client.host if request.client else "?")


class Janela:
    """Conta eventos por chave dentro de uma janela deslizante."""

    def __init__(self, limite: int, segundos: float) -> None:
        self.limite = limite
        self.segundos = segundos
        self._eventos: dict[object, deque[float]] = defaultdict(deque)

    def _fila(self, chave: object) -> deque[float]:
        fila = self._eventos[chave]
        corte = time.monotonic() - self.segundos
        while fila and fila[0] < corte:
            fila.popleft()
        return fila

    def estourou(self, chave: object) -> bool:
        return len(self._fila(chave)) >= self.limite

    def espera(self, chave: object) -> float:
        """Segundos até a chave voltar a ficar abaixo do limite."""
        fila = self._fila(chave)
        if len(fila) < self.limite:
            return 0.0
        return max(0.0, fila[0] + self.segundos - time.monotonic())

    def registrar(self, chave: object) -> None:
        self._fila(chave).append(time.monotonic())
        if len(self._eventos) > 20_000:  # não deixa o dicionário crescer sem fim
            self._eventos.clear()

    def limpar(self, chave: object) -> None:
        self._eventos.pop(chave, None)

    def zerar(self) -> None:
        self._eventos.clear()
