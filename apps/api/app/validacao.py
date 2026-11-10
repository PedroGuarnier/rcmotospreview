"""Normalização e validação de documentos e identificadores brasileiros."""

import re

_PLACA = re.compile(r"^[A-Z]{3}\d[A-Z0-9]\d{2}$")  # antiga (ABC1234) e Mercosul (ABC1D23)


def so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def normalizar_placa(valor: str) -> str:
    placa = re.sub(r"[^A-Za-z0-9]", "", valor).upper()
    if not _PLACA.match(placa):
        raise ValueError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
    return placa


def normalizar_chassi(valor: str) -> str:
    chassi = re.sub(r"[\s\-.]", "", valor).upper()
    if not chassi.isalnum() or len(chassi) > 17 or len(chassi) < 6:
        raise ValueError("Chassi inválido: use até 17 letras e números.")
    return chassi


def normalizar_renavam(valor: str) -> str:
    renavam = so_digitos(valor)
    if not 9 <= len(renavam) <= 11:
        raise ValueError("RENAVAM inválido: deve ter de 9 a 11 dígitos.")
    return renavam.zfill(11)


def normalizar_telefone(valor: str) -> str:
    fone = so_digitos(valor)
    if fone.startswith("55") and len(fone) in (12, 13):
        fone = fone[2:]
    if len(fone) not in (10, 11):
        raise ValueError("Telefone inválido: informe DDD + número.")
    return fone


def _dv_mod11(valores: list[int], pesos: list[int]) -> int:
    resto = sum(v * p for v, p in zip(valores, pesos, strict=True)) % 11
    return 0 if resto < 2 else 11 - resto


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    nums = [int(c) for c in cpf]
    d1 = _dv_mod11(nums[:9], list(range(10, 1, -1)))
    d2 = _dv_mod11(nums[:10], list(range(11, 1, -1)))
    return nums[9] == d1 and nums[10] == d2


def _cnpj_valido(cnpj: str) -> bool:
    # Aceita o CNPJ alfanumérico (em vigor desde julho/2026): valor = código ASCII − 48.
    if len(cnpj) != 14 or not cnpj[:12].isalnum() or not cnpj[12:].isdigit():
        return False
    if cnpj == cnpj[0] * 14:
        return False
    vals = [ord(c) - 48 for c in cnpj]
    d1 = _dv_mod11(vals[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _dv_mod11(vals[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return vals[12] == d1 and vals[13] == d2


def normalizar_cpf_cnpj(valor: str) -> str:
    doc = re.sub(r"[^A-Za-z0-9]", "", valor).upper()
    if len(doc) == 11 and _cpf_valido(doc):
        return doc
    if len(doc) == 14 and _cnpj_valido(doc):
        return doc
    raise ValueError("CPF/CNPJ inválido. Confira os números.")
