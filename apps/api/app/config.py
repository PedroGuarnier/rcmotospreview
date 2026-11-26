from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SEGREDO_PADRAO_DEV = "troque-este-segredo-antes-de-ir-para-producao"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: str = "desenvolvimento"  # desenvolvimento | producao | teste
    database_url: str = "postgresql+psycopg://rcmotos:rcmotos@localhost:5432/rcmotos"

    # Sessão
    segredo_jwt: str = SEGREDO_PADRAO_DEV
    sessao_horas: int = 24 * 7
    cookie_sessao: str = "rc_sessao"

    # Login
    max_tentativas_login: int = 5
    bloqueio_login_minutos: int = 15

    # Arquivos (fotos dos veículos)
    uploads_dir: Path = Path("uploads")
    foto_tamanho_max_mb: int = 15

    # Regras de negócio
    fuso_horario: str = "America/Fortaleza"
    dias_parado_alerta: int = 45

    # Consulta de procedência pela placa: "" (desligada) | "demonstracao" | "consultarplaca".
    procedencia_provedor: str = ""
    # Conta na Consultar Placa (e-mail da conta + chave gerada em Minha Conta > API).
    consultarplaca_email: str = ""
    consultarplaca_api_key: str = ""
    # Provedor pago: laudo completo da mesma placa feito há menos de N horas é reaproveitado
    # em vez de pagar outra consulta (0 = sempre consulta de novo).
    procedencia_reuso_horas: int = 24

    # Quando true, a interface avisa que os números são ilustrativos (dados do seed --demo).
    dados_demo: bool = False

    # IA do assistente (perguntas sobre vendas, estoque e financeiro). Sem a chave do provedor
    # escolhido, fica desligada: o assistente continua cadastrando e avisa que as perguntas
    # não estão ligadas.
    ia_provedor: Literal["groq", "anthropic"] = "groq"
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    ia_modelo: str = ""  # vazio = o padrão do provedor (app/ia/provedores.py)

    @field_validator("ia_provedor", mode="before")
    @classmethod
    def _provedor_vazio_usa_padrao(cls, valor: str | None) -> str:
        return (valor or "groq").strip().lower()

    @field_validator("segredo_jwt", mode="before")
    @classmethod
    def _segredo_vazio_usa_padrao(cls, valor: str | None) -> str:
        # SEGREDO_JWT= (vazio) no .env equivale a não definir.
        return valor or SEGREDO_PADRAO_DEV

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @model_validator(mode="after")
    def _exigir_segredo_em_producao(self) -> "Config":
        if self.producao and (self.segredo_jwt == SEGREDO_PADRAO_DEV or len(self.segredo_jwt) < 32):
            raise ValueError(
                "Defina SEGREDO_JWT com pelo menos 32 caracteres aleatórios em produção "
                "(ex.: openssl rand -hex 32)."
            )
        return self


@lru_cache
def obter_config() -> Config:
    return Config()
