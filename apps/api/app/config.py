import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sem SEGREDO_JWT, cada processo sorteia o seu: nunca existe um segredo conhecido (o código é
# público). O efeito colateral, só em desenvolvimento, é que reiniciar a API desloga todo mundo.
SEGREDO_SORTEADO = secrets.token_hex(32)


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ambiente: str = "desenvolvimento"  # desenvolvimento | producao | teste
    database_url: str = "postgresql+psycopg://rcmotos:rcmotos@localhost:5432/rcmotos"

    # Sessão
    segredo_jwt: str = SEGREDO_SORTEADO
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
    # Prazo do comprador para transferir o veículo, contado da venda
    prazo_transferencia_dias: int = 30

    # Consulta de procedência pela placa: "" (desligada) | "demonstracao".
    # O provedor real (ex.: Infosimples) entra aqui quando a conta da loja existir.
    procedencia_provedor: str = ""

    # Quando true, a interface avisa que os números são ilustrativos (dados do seed --demo).
    dados_demo: bool = False

    @field_validator("database_url")
    @classmethod
    def _usar_driver_psycopg(cls, url: str) -> str:
        # Hospedagens entregam "postgres://" ou "postgresql://"; o driver instalado é o psycopg 3.
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url[len(prefixo) :]
        return url

    @field_validator("segredo_jwt", mode="before")
    @classmethod
    def _segredo_vazio_usa_sorteado(cls, valor: str | None) -> str:
        # SEGREDO_JWT= (vazio) no .env equivale a não definir.
        return valor or SEGREDO_SORTEADO

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @model_validator(mode="after")
    def _exigir_segredo_em_producao(self) -> "Config":
        if self.producao and (self.segredo_jwt == SEGREDO_SORTEADO or len(self.segredo_jwt) < 32):
            raise ValueError(
                "Defina SEGREDO_JWT com pelo menos 32 caracteres aleatórios em produção "
                "(ex.: openssl rand -hex 32)."
            )
        return self


@lru_cache
def obter_config() -> Config:
    return Config()
