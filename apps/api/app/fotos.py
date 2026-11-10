"""Fotos dos veículos: valida, corrige orientação, remove EXIF (GPS) e gera miniatura."""

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import obter_config

Image.MAX_IMAGE_PIXELS = 60_000_000
LADO_MAX = 1920
LADO_MINIATURA = 480
FORMATOS = {"JPEG", "PNG", "WEBP", "MPO"}


def ler_com_limite(arquivo: UploadFile) -> bytes:
    limite = obter_config().foto_tamanho_max_mb * 1024 * 1024
    dados = arquivo.file.read(limite + 1)
    if len(dados) > limite:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Foto muito grande (máx. {obter_config().foto_tamanho_max_mb} MB).",
        )
    return dados


def _salvar_jpeg(img: Image.Image, lado: int, destino: Path, qualidade: int) -> None:
    copia = img.copy()
    copia.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    copia.save(destino, "JPEG", quality=qualidade, optimize=True)


def salvar_foto(veiculo_id: int, dados: bytes) -> tuple[str, str]:
    """Grava a foto e a miniatura. Devolve os caminhos relativos a UPLOADS_DIR."""
    invalida = HTTPException(422, "Arquivo inválido: envie uma foto JPG, PNG ou WebP.")
    try:
        img = Image.open(io.BytesIO(dados))
        if img.format not in FORMATOS:
            raise invalida
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        raise invalida from exc

    pasta = obter_config().uploads_dir / "veiculos" / str(veiculo_id)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = uuid.uuid4().hex
    _salvar_jpeg(img, LADO_MAX, pasta / f"{nome}.jpg", 85)
    _salvar_jpeg(img, LADO_MINIATURA, pasta / f"{nome}_mini.jpg", 80)
    base = f"veiculos/{veiculo_id}/{nome}"
    return f"{base}.jpg", f"{base}_mini.jpg"


def apagar_arquivos(*caminhos: str) -> None:
    raiz = obter_config().uploads_dir
    for caminho in caminhos:
        (raiz / caminho).unlink(missing_ok=True)


def url(caminho: str) -> str:
    return f"/arquivos/{caminho}"
