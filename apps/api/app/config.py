from functools import lru_cache
from pathlib import Path

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

    # Consulta de procedência pela placa: "" (desligada) | "demonstracao".
    # O provedor real (ex.: Infosimples) entra aqui quando a conta da loja existir.
    procedencia_provedor: str = ""

    # Quando true, a interface avisa que os números são ilustrativos (dados do seed --demo).
    dados_demo: bool = False

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
