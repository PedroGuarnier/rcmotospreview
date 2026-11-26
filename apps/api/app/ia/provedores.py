"""Provedores de modelo de linguagem, atrás de um contrato interno único.

O laço de perguntas (`agente.py`), as ferramentas, as permissões e o prompt são os mesmos
para todos. Cada adaptador só converte o formato das ferramentas e das mensagens:

- `groq` (padrão): API compatível com a da OpenAI (`/openai/v1/chat/completions`, `tools`
  em function calling, respostas com `tool_calls` e mensagens `role: "tool"`), chamada com o
  `httpx`, sem SDK.
- `anthropic`: Messages API do Claude pelo SDK oficial (`tool_use` / `tool_result`).

Contrato: `provedor.conversa(...)` abre uma conversa no formato do provedor; `chamar()`
devolve um `Turno` neutro (texto, pedidos de ferramenta, por que parou, tokens);
`devolver(turno, resultados)` acrescenta a resposta do modelo e os resultados das consultas.
Falhas viram `ErroIA` com um `tipo` que o agente transforma em frase.

Os dois são testados com transporte falso (`httpx.MockTransport` e o equivalente do SDK),
sem rede.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

import anthropic
import httpx

from app.config import obter_config
from app.ia.ferramentas import Ferramenta
from app.schemas import AssistenteTroca

MODELO_PADRAO = {
    # Configurável em IA_MODELO. O llama-3.3-70b-versatile foi desligado pelo Groq em
    # 16/08/2026; o substituto recomendado, com tool use, é o gpt-oss-120b.
    "groq": "openai/gpt-oss-120b",
    "anthropic": "claude-haiku-5-5",
}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

TipoErro = Literal["limite", "credito", "chave", "fora_do_ar", "tempo", "conexao", "outro"]
Parada = Literal["fim", "ferramenta", "limite_tokens", "recusa", "pausa"]


class ErroIA(Exception):
    def __init__(self, tipo: TipoErro, detalhe: str = ""):
        super().__init__(f"{tipo}: {detalhe}" if detalhe else tipo)
        self.tipo = tipo


@dataclass
class Pedido:
    """O modelo pediu uma ferramenta. `entrada` pode não ser dict (JSON inválido)."""

    id: str
    nome: str
    entrada: Any


@dataclass
class Uso:
    entrada: int = 0
    saida: int = 0
    cache_lida: int = 0
    cache_gravada: int = 0


@dataclass
class Turno:
    texto: str
    pedidos: list[Pedido]
    parada: Parada
    uso: Uso
    bruto: Any = field(default=None, repr=False)  # a resposta do modelo, no formato do provedor


@dataclass
class Resultado:
    pedido_id: str
    conteudo: str  # JSON
    erro: bool


class Conversa(Protocol):
    def chamar(self, timeout: float) -> Turno: ...
    def devolver(self, turno: Turno, resultados: list[Resultado]) -> None: ...


class Provedor(Protocol):
    nome: str
    modelo: str

    def conversa(
        self,
        sistema: str,
        contexto: str,
        ferramentas: list[Ferramenta],
        historico: list[AssistenteTroca],
        pergunta: str,
    ) -> Conversa: ...


# ---------------------------------------------------------------------------------------
# Groq (formato OpenAI), com httpx
# ---------------------------------------------------------------------------------------


@dataclass
class Groq:
    chave: str
    modelo: str
    http: httpx.Client
    max_tokens: int = 2048
    esforco: str = "low"  # reasoning_effort do gpt-oss: low | medium | high
    nome: str = "groq"

    def conversa(self, sistema, contexto, ferramentas, historico, pergunta) -> "ConversaGroq":
        mensagens: list[dict[str, Any]] = [
            {"role": "system", "content": f"{sistema}\n\n{contexto}"}
        ]
        for troca in historico:
            mensagens.append({"role": "user", "content": troca.pergunta})
            mensagens.append({"role": "assistant", "content": troca.resposta})
        mensagens.append({"role": "user", "content": pergunta})
        definicoes = [
            {
                "type": "function",
                "function": {
                    "name": f.nome,
                    "description": f.descricao,
                    "parameters": f.esquema(),
                },
            }
            for f in ferramentas
        ]
        return ConversaGroq(self, mensagens, definicoes)


@dataclass
class ConversaGroq:
    provedor: Groq
    mensagens: list[dict[str, Any]]
    ferramentas: list[dict[str, Any]]

    def chamar(self, timeout: float) -> Turno:
        p = self.provedor
        corpo: dict[str, Any] = {
            "model": p.modelo,
            "messages": self.mensagens,
            "max_completion_tokens": p.max_tokens,
        }
        if self.ferramentas:
            corpo.update(tools=self.ferramentas, tool_choice="auto")
        if p.modelo.startswith("openai/gpt-oss"):
            corpo["reasoning_effort"] = p.esforco
        try:
            r = p.http.post(
                GROQ_URL,
                json=corpo,
                headers={"Authorization": f"Bearer {p.chave}"},
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise ErroIA("tempo") from exc
        except httpx.HTTPError as exc:
            raise ErroIA("conexao", type(exc).__name__) from exc
        if r.status_code != 200:
            raise _erro_http(r)
        try:
            dados = r.json()
            escolha = dados["choices"][0]
            mensagem = escolha["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ErroIA("outro", "resposta em formato inesperado") from exc

        pedidos = []
        for chamada in mensagem.get("tool_calls") or []:
            funcao = chamada.get("function") or {}
            try:
                entrada = json.loads(funcao.get("arguments") or "{}")
            except ValueError:
                entrada = funcao.get("arguments")  # a ferramenta responde "parâmetros inválidos"
            pedidos.append(Pedido(chamada.get("id", ""), funcao.get("name", ""), entrada))
        motivo = escolha.get("finish_reason")
        parada: Parada = (
            "ferramenta"
            if pedidos
            else "limite_tokens"
            if motivo == "length"
            else "recusa"
            if motivo == "content_filter"
            else "fim"
        )
        uso = dados.get("usage") or {}
        return Turno(
            texto=mensagem.get("content") or "",  # o campo `reasoning` nunca vai para a tela
            pedidos=pedidos,
            parada=parada,
            uso=Uso(entrada=uso.get("prompt_tokens", 0), saida=uso.get("completion_tokens", 0)),
            bruto=mensagem,
        )

    def devolver(self, turno: Turno, resultados: list[Resultado]) -> None:
        # O raciocínio (`reasoning`) volta junto do pedido, dentro da mesma pergunta: sem ele o
        # gpt-oss às vezes respondia com texto embaralhado depois do resultado da ferramenta.
        # Ele nunca vai para a tela nem para o histórico entre perguntas.
        mensagem: dict[str, Any] = {
            "role": "assistant",
            "content": turno.texto or None,
            "tool_calls": turno.bruto.get("tool_calls"),
        }
        if turno.bruto.get("reasoning"):
            mensagem["reasoning"] = turno.bruto["reasoning"]
        self.mensagens.append(mensagem)
        for r in resultados:
            self.mensagens.append(
                {"role": "tool", "tool_call_id": r.pedido_id, "content": r.conteudo}
            )


def _erro_http(r: httpx.Response) -> ErroIA:
    try:
        corpo = r.json().get("error") or {}
    except ValueError:
        corpo = {}
    detalhe = f"HTTP {r.status_code} {corpo.get('code') or corpo.get('type') or ''}".strip()
    if r.status_code == 429:  # limite da camada gratuita (por minuto ou por dia)
        return ErroIA("limite", detalhe)
    if r.status_code in (401, 403):
        return ErroIA("chave", detalhe)
    if r.status_code == 402:
        return ErroIA("credito", detalhe)
    if r.status_code >= 500 or r.status_code == 498:  # 498: sem capacidade no momento
        return ErroIA("fora_do_ar", detalhe)
    return ErroIA("outro", detalhe)


# ---------------------------------------------------------------------------------------
# Anthropic (Claude), com o SDK oficial
# ---------------------------------------------------------------------------------------


@dataclass
class Anthropic:
    cliente: anthropic.Anthropic
    modelo: str
    max_tokens: int = 2048  # o raciocínio (thinking) também conta aqui
    esforco: str = "medium"
    nome: str = "anthropic"

    def conversa(self, sistema, contexto, ferramentas, historico, pergunta) -> "ConversaAnthropic":
        mensagens: list[dict[str, Any]] = []
        for troca in historico:
            mensagens.append({"role": "user", "content": troca.pergunta})
            mensagens.append({"role": "assistant", "content": troca.resposta})
        mensagens.append({"role": "user", "content": pergunta})
        blocos_sistema = [
            # tools + esta parte fixa formam o prefixo em cache
            {"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": contexto},
        ]
        definicoes = [
            {"name": f.nome, "description": f.descricao, "input_schema": f.esquema()}
            for f in ferramentas
        ]
        return ConversaAnthropic(self, blocos_sistema, definicoes, mensagens)


@dataclass
class ConversaAnthropic:
    provedor: Anthropic
    sistema: list[dict[str, Any]]
    ferramentas: list[dict[str, Any]]
    mensagens: list[dict[str, Any]]

    def chamar(self, timeout: float) -> Turno:
        p = self.provedor
        # Claude Haiku 5.5: sem budget_tokens, sem temperature/top_p e sem prefill.
        try:
            resposta = p.cliente.messages.create(
                model=p.modelo,
                max_tokens=p.max_tokens,
                system=self.sistema,
                tools=self.ferramentas,
                messages=self.mensagens,
                output_config={"effort": p.esforco},
                timeout=timeout,
            )
        except anthropic.APIError as exc:
            raise _erro_anthropic(exc) from exc
        pedidos = [Pedido(b.id, b.name, b.input) for b in resposta.content if b.type == "tool_use"]
        parada: Parada = {
            "tool_use": "ferramenta",
            "max_tokens": "limite_tokens",
            "refusal": "recusa",
            "pause_turn": "pausa",
        }.get(resposta.stop_reason or "", "fim")
        if parada == "ferramenta" and not pedidos:
            parada = "fim"
        u = resposta.usage
        return Turno(
            texto="\n".join(b.text for b in resposta.content if b.type == "text"),
            pedidos=pedidos,
            parada=parada,
            uso=Uso(
                entrada=u.input_tokens or 0,
                saida=u.output_tokens or 0,
                cache_lida=getattr(u, "cache_read_input_tokens", 0) or 0,
                cache_gravada=getattr(u, "cache_creation_input_tokens", 0) or 0,
            ),
            bruto=resposta.content,
        )

    def devolver(self, turno: Turno, resultados: list[Resultado]) -> None:
        # o conteúdo volta como veio, inclusive os blocos de raciocínio
        self.mensagens.append({"role": "assistant", "content": turno.bruto})
        if resultados:
            blocos = []
            for r in resultados:
                bloco: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": r.pedido_id,
                    "content": r.conteudo,
                }
                if r.erro:
                    bloco["is_error"] = True
                blocos.append(bloco)
            self.mensagens.append({"role": "user", "content": blocos})


def _erro_anthropic(exc: anthropic.APIError) -> ErroIA:
    if isinstance(exc, anthropic.APITimeoutError):
        return ErroIA("tempo")
    if isinstance(exc, anthropic.APIConnectionError):
        return ErroIA("conexao")
    if isinstance(exc, anthropic.RateLimitError):
        return ErroIA("limite")
    if isinstance(exc, anthropic.PaymentRequiredError) or (
        isinstance(exc, anthropic.BadRequestError) and "credit" in str(exc).lower()
    ):
        return ErroIA("credito")
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return ErroIA("chave")
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return ErroIA("fora_do_ar", f"HTTP {exc.status_code}")
    return ErroIA("outro", type(exc).__name__)


# ---------------------------------------------------------------------------------------
# Escolha pela configuração
# ---------------------------------------------------------------------------------------

TIMEOUT_CHAMADA = 25.0  # segundos por chamada ao provedor


def _chave(provedor: str) -> str:
    cfg = obter_config()
    return (cfg.groq_api_key if provedor == "groq" else cfg.anthropic_api_key).strip()


def ia_ligada() -> bool:
    return bool(_chave(obter_config().ia_provedor))


@lru_cache(maxsize=4)
def _criar(provedor: str, chave: str, modelo: str) -> Provedor:
    if provedor == "anthropic":
        # max_retries=1: o SDK repete sozinho 429, 5xx e falha de rede uma vez, com espera.
        cliente = anthropic.Anthropic(api_key=chave, timeout=TIMEOUT_CHAMADA, max_retries=1)
        return Anthropic(cliente, modelo)
    return Groq(chave, modelo, httpx.Client(timeout=TIMEOUT_CHAMADA))


def provedor_ia() -> Provedor | None:
    """Dependência do FastAPI: o provedor configurado, ou None com a IA desligada."""
    cfg = obter_config()
    chave = _chave(cfg.ia_provedor)
    if not chave:
        return None
    modelo = cfg.ia_modelo.strip() or MODELO_PADRAO[cfg.ia_provedor]
    return _criar(cfg.ia_provedor, chave, modelo)
