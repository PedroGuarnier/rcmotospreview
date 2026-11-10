"""Cria o primeiro usuário (dono) e, opcionalmente, dados ilustrativos.

    python -m app.seed            # cria o dono a partir de DONO_NOME / DONO_EMAIL / DONO_SENHA
    python -m app.seed --demo     # + veículos, vendas e usuários de exemplo (só para testar)

Os dados do --demo são ILUSTRATIVOS: não use em produção. Rode a API com DADOS_DEMO=true
para a interface avisar isso em todas as telas.
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app import audit, procedencia, schemas, servicos
from app.config import obter_config
from app.db import SessionLocal
from app.models import (
    Aporte,
    CustoVeiculo,
    FormaPagamento,
    Perfil,
    RegraComissao,
    Situacao,
    TipoCusto,
    TipoVeiculo,
    Usuario,
    Veiculo,
)
from app.security import gerar_hash
from app.tempo import hoje

SENHA_DEMO = "rcmotos123"


def criar_dono(db) -> Usuario:
    dono = db.scalar(select(Usuario).where(Usuario.perfil == Perfil.dono))
    if dono is not None:
        print(f"Já existe um dono: {dono.email}")
        return dono
    email = os.environ.get("DONO_EMAIL", "").strip().lower()
    senha = os.environ.get("DONO_SENHA", "")
    nome = os.environ.get("DONO_NOME", "Dono")
    if not email or len(senha) < 8:
        sys.exit("Defina DONO_EMAIL e DONO_SENHA (mín. 8 caracteres) para criar o dono.")
    dono = Usuario(
        nome=nome,
        email=email,
        senha_hash=gerar_hash(senha),
        perfil=Perfil.dono,
        acesso_aportes=True,
    )
    db.add(dono)
    db.commit()
    print(f"Dono criado: {email}")
    return dono


def criar_demo(db, dono: Usuario) -> None:
    if obter_config().producao:
        sys.exit("--demo não roda em produção.")
    if db.scalar(select(Veiculo.id).limit(1)) is not None:
        print("Já existem veículos: dados de exemplo não foram criados.")
        return
    db.info["usuario"] = dono
    dia = hoje()

    def usuario(nome, email, perfil, regra=None, valor=None):
        u = Usuario(
            nome=nome,
            email=email,
            senha_hash=gerar_hash(SENHA_DEMO),
            perfil=perfil,
            comissao_regra=regra,
            comissao_valor=valor,
        )
        db.add(u)
        return u

    usuario("Gerente (exemplo)", "gerente@exemplo.com", Perfil.gerente)
    usuario("Financeiro (exemplo)", "financeiro@exemplo.com", Perfil.financeiro)
    v1 = usuario(
        "Vendedor 1 (exemplo)",
        "vendedor1@exemplo.com",
        Perfil.vendedor,
        RegraComissao.percentual_lucro,
        Decimal("10"),
    )
    v2 = usuario(
        "Vendedor 2 (exemplo)",
        "vendedor2@exemplo.com",
        Perfil.vendedor,
        RegraComissao.valor_fixo,
        Decimal("150"),
    )

    # (tipo, marca, modelo, ano, cor, km, placa, compra, preço, situação, dias, [custos])
    estoque = [
        (
            "moto",
            "Honda",
            "CG 160 Fan",
            2022,
            "Vermelha",
            18500,
            "QRS1A23",
            11500,
            14900,
            "a_venda",
            12,
            [("manutencao", "Revisão e troca de óleo", 280)],
        ),
        (
            "moto",
            "Honda",
            "Biz 125",
            2021,
            "Branca",
            22000,
            "PIA2B34",
            9800,
            12900,
            "a_venda",
            60,
            [("documentacao", "Transferência", 320)],
        ),
        (
            "moto",
            "Yamaha",
            "Factor 150",
            2023,
            "Azul",
            9000,
            "PIB3C45",
            12800,
            16500,
            "a_venda",
            5,
            [],
        ),
        (
            "moto",
            "Honda",
            "Pop 110i",
            2022,
            "Preta",
            15000,
            "PIC4D56",
            6500,
            8900,
            "preparacao",
            8,
            [("manutencao", "Pneu traseiro", 190)],
        ),
        (
            "moto",
            "Honda",
            "NXR 160 Bros",
            2021,
            "Vermelha",
            31000,
            "PID5E67",
            14200,
            18500,
            "documentacao",
            20,
            [("debito", "IPVA 2026", 410)],
        ),
        (
            "carro",
            "Fiat",
            "Uno Way 1.0",
            2015,
            "Prata",
            98000,
            "PIE6F78",
            24000,
            31900,
            "a_venda",
            30,
            [("manutencao", "Suspensão dianteira", 850)],
        ),
        (
            "carro",
            "Chevrolet",
            "Onix 1.0 LT",
            2019,
            "Branco",
            64000,
            "PIF7G89",
            46000,
            56900,
            "compra",
            2,
            [],
        ),
        (
            "moto",
            "Honda",
            "CG 160 Titan",
            2023,
            "Cinza",
            7000,
            "PIG8H90",
            14000,
            17900,
            "a_venda",
            25,
            [],
        ),
        (
            "moto",
            "Yamaha",
            "Fazer 250",
            2020,
            "Azul",
            28000,
            "PIH9I01",
            15500,
            19900,
            "a_venda",
            40,
            [("manutencao", "Kit relação", 360)],
        ),
        (
            "carro",
            "Volkswagen",
            "Gol 1.6",
            2014,
            "Vermelho",
            120000,
            "PII0J12",
            22000,
            28900,
            "a_venda",
            55,
            [],
        ),
        (
            "moto",
            "Honda",
            "XRE 300",
            2022,
            "Cinza",
            14000,
            "PIJ1K24",
            21500,
            26900,
            "a_venda",
            3,
            [("manutencao", "Revisão completa", 420)],
        ),
        (
            "carro",
            "Hyundai",
            "HB20 1.0",
            2018,
            "Branco",
            71000,
            "PIK2L36",
            41000,
            49900,
            "a_venda",
            18,
            [("documentacao", "Transferência", 380)],
        ),
    ]
    veiculos = []
    for tipo, marca, modelo, ano, cor, km, placa, compra, preco, situacao, dias, custos in estoque:
        entrada = datetime.now(UTC) - timedelta(days=dias)
        v = Veiculo(
            tipo=TipoVeiculo(tipo),
            marca=marca,
            modelo=modelo,
            ano_fabricacao=ano,
            ano_modelo=ano,
            cor=cor,
            km=km,
            placa=placa,
            valor_compra=Decimal(compra),
            preco_venda=Decimal(preco),
            data_compra=dia - timedelta(days=dias + 3),
            situacao=Situacao(situacao),
            situacao_desde=entrada,
            observacoes="Dado ilustrativo (seed --demo).",
        )
        for tipo_custo, descricao, valor in custos:
            v.custos.append(
                CustoVeiculo(
                    tipo=TipoCusto(tipo_custo),
                    descricao=descricao,
                    valor=Decimal(valor),
                    data=dia - timedelta(days=dias),
                )
            )
        db.add(v)
        veiculos.append(v)
    db.flush()

    # Vendas de exemplo: (índice do veículo, vendedor, valor, forma, dias atrás)
    vendas = [
        (7, v1, 17500, FormaPagamento.a_vista, 3),
        (8, v2, 19500, FormaPagamento.financiado_banco, 9),
        (9, v1, 28000, FormaPagamento.parcelado_loja, 38),
    ]
    for i, (indice, vendedor, valor, forma, dias) in enumerate(vendas, start=1):
        extras = {}
        if forma == FormaPagamento.parcelado_loja:
            extras = dict(
                entrada=Decimal("8000"),
                numero_parcelas=10,
                valor_parcela=Decimal("2000"),
                primeiro_vencimento=dia - timedelta(days=dias - 30),
            )
        elif forma == FormaPagamento.financiado_banco:
            extras = dict(banco="Banco (exemplo)", entrada=Decimal("5000"))
        servicos.registrar_venda(
            db,
            schemas.VendaCriar(
                veiculo_id=veiculos[indice].id,
                cliente_novo=schemas.ClienteCriar(
                    nome=f"Cliente {i} (exemplo)", telefone=f"8699900000{i}"
                ),
                vendedor_id=vendedor.id,
                valor=Decimal(valor),
                forma=forma,
                data_venda=dia - timedelta(days=dias),
                **extras,
            ),
            dono,
        )
    # Laudos de procedência ilustrativos para o que está à venda (provedor de demonstração)
    if procedencia.provedor_ativo() == "demonstracao":
        for v in veiculos:
            if v.situacao == Situacao.a_venda:
                procedencia.consultar(db, v.placa, dono)
    db.add(
        Aporte(
            data=dia - timedelta(days=15),
            valor=Decimal("5000"),
            descricao="Aporte ilustrativo",
            registrado_por_id=dono.id,
        )
    )
    db.commit()
    print(f"Dados ilustrativos criados. Senha dos usuários de exemplo: {SENHA_DEMO}")


def main() -> None:
    audit.instalar(SessionLocal)
    with SessionLocal() as db:
        dono = criar_dono(db)
        if "--demo" in sys.argv:
            criar_demo(db, dono)


if __name__ == "__main__":
    main()
