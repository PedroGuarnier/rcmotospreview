from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import obter_config


def agora() -> datetime:
    return datetime.now(ZoneInfo(obter_config().fuso_horario))


def hoje() -> date:
    """Data de hoje no fuso da loja (Piauí)."""
    return agora().date()
