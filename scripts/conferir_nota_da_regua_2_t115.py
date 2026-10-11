"""A NOTA DA REGUA 2 COM OS DADOS REAIS (T115) - Maria 23 e Fernando 22.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT PROVA
═══════════════════════════════════════════════════════════════════════════

A troca da regua da nota (`DECISOES-do-dono.md` §8zzo) nasceu de um empate no
`prd`: no desafio de 10/10/2026, o Fernando (9 tentativas, 0 dica, 38 s) e a
Maria (2 tentativas, 2 dicas, 54 s) tiraram 25 os dois, porque a regua 1 zerava
a parcela de tentativas na 4a. A promessa da regua 2 era **Maria 23, Fernando
22**. Este script refaz a conta com:

  - os dados REAIS deles, lidos do `prd` (o extrato gravado: as medidas de
    sessao e as do merito, e os pesos daquele desafio);
  - as reguas gravadas no `des` (`vw905`), onde as migracoes `0030`, `0031` e
    `0032` ja estao;
  - **a conta do proprio servidor** (`montar_extrato` e `pontuacao_do_extrato`,
    as mesmas funcoes que `servico_envio.py` chama).

⚠️ **A regua 2 e passada EXPLICITAMENTE, e nao escolhida pela data.** O desafio
deles e de 10/10, e pela vigencia (`regua_vigente`) ele e da regua 1 em qualquer
ambiente. A conferencia escolhe a versao pelo numero, e confere a vigencia a
parte, na condicao (e).

═══════════════════════════════════════════════════════════════════════════
⚠️ COM CONTROLE: A REGUA 1 TEM DE REPRODUZIR O QUE FOI GRAVADO
═══════════════════════════════════════════════════════════════════════════

Um 23 e um 22 sozinhos nao provam nada: com uma medida lida errada (o tempo em
segundos, a dica do dia trocada pela da tentativa), a conta poderia acertar os
dois numeros por acidente. Por isso a condicao (a) roda a MESMA montagem com a
regua 1 e exige o extrato gravado no `prd` em 10/10, **parcela a parcela** (o
servidor daquele dia ainda pontuava pela regua 1). So depois disso o resultado
da regua 2 significa alguma coisa.

═══════════════════════════════════════════════════════════════════════════
⛔ SO LEITURA, NOS DOIS BANCOS
═══════════════════════════════════════════════════════════════════════════

Cada conexao abre uma transacao `READ ONLY` e a desfaz (`ROLLBACK`) no fim: uma
escrita falharia NO BANCO. ⛔ Nunca imprime URL nem senha. ⛔ Nenhum id de
usuario no codigo: cada pessoa e reconhecida pelas tentativas (9 e 2), que e
como a decisao do dono as descreve.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\conferir_nota_da_regua_2_t115.py

Leva poucos segundos. Sai com codigo 0 so quando todas as condicoes fecham.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

# `parents[1]` e a raiz do backend: e dela que `api` e `scripts` sao importaveis.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, o primeiro emoji derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

# Reuso, e nao copia: as consultas e a conta sao as do servidor.
from api.desafios.extrato_xp import (  # noqa: E402
    FEITO_DICAS,
    FEITO_TEMPO,
    FEITO_TENTATIVAS,
    ParcelaDeXp,
    montar_extrato,
    pontuacao_do_extrato,
)
from api.desafios.regua_da_nota import (  # noqa: E402
    SQL_REGUAS_DA_NOTA,
    ReguaDaNota,
    regua_vigente,
    reguas_das_linhas,
)
from api.desafios.repositorio_envio import (  # noqa: E402
    SQL_DIRECOES_DE_SESSAO,
    SQL_PESOS_DO_DESAFIO,
    SQL_REGUA_DE_TEMPO,
)
from scripts.conferir_portao_t050 import Relatorio, url_do_des  # noqa: E402
from scripts.consultar_prd import url_do_prd  # noqa: E402

#: O dia do desafio do empate.
DIA_DO_EMPATE = date(2026, 10, 10)

#: Quem e quem, pelas tentativas, e o que a regua 2 prometeu (§8zzo).
ESPERADO_NA_REGUA_2 = {9: ("Fernando", 22), 2: ("Maria", 23)}

#: As resolucoes do dia, com o desafio de cada uma.
SQL_RESOLUCOES_DO_DIA = """
SELECT d.id_desafio, r.id_resolucao, r.nu_xp
  FROM desafio_dia.vw003_resolucao r
  JOIN desafio_dia.vw001_desafio_dia d USING (id_desafio_dia)
 WHERE d.dt_dia = :dt_dia
"""

#: O extrato gravado de uma resolucao: as medidas e o XP de cada parcela.
SQL_EXTRATO_GRAVADO = """
SELECT nu_tipo_xp, nu_feito, co_feito, vr_medida, vr_xp
  FROM desafio_dia.vw004_xp_desafio
 WHERE id_resolucao = :id_resolucao
"""

#: Tres casas, como `tb004_xp_desafio.vr_xp`.
MILESIMO = Decimal("0.001")


async def _ler(url: str, consultas) -> Any:
    """Abre uma transacao SOMENTE LEITURA, roda `consultas(conexao)` e desfaz.

    `consultas` e uma funcao assincrona que recebe a conexao e devolve o que leu.
    ⚠️ `SET TRANSACTION READ ONLY` tem de ser o PRIMEIRO comando da transacao, e e
    o banco que recusa uma escrita depois dele - nao uma conferencia de texto.
    """
    motor = create_async_engine(url)
    try:
        async with motor.connect() as conexao:
            await conexao.execute(text("SET TRANSACTION READ ONLY"))
            try:
                return await consultas(conexao)
            finally:
                await conexao.rollback()
    finally:
        await motor.dispose()


async def _dados_do_prd(conexao) -> dict[str, Any]:
    """Tudo o que a conta precisa, lido do `prd`."""
    linhas = (
        await conexao.execute(text(SQL_RESOLUCOES_DO_DIA), {"dt_dia": DIA_DO_EMPATE})
    ).mappings().all()
    resolucoes = []
    for linha in linhas:
        extrato = (
            await conexao.execute(
                text(SQL_EXTRATO_GRAVADO), {"id_resolucao": linha["id_resolucao"]}
            )
        ).mappings().all()
        resolucoes.append(
            {"id_desafio": linha["id_desafio"], "nu_xp": linha["nu_xp"],
             "extrato": [dict(e) for e in extrato]}
        )

    ids = {r["id_desafio"] for r in resolucoes}
    assert len(ids) == 1, f"o dia {DIA_DO_EMPATE} tem {len(ids)} desafios"
    id_desafio = ids.pop()
    pesos = (
        await conexao.execute(text(SQL_PESOS_DO_DESAFIO), {"id_desafio": id_desafio})
    ).mappings().all()
    regua_de_tempo = (
        await conexao.execute(text(SQL_REGUA_DE_TEMPO), {"id_desafio": id_desafio})
    ).mappings().one()
    direcoes = (
        await conexao.execute(
            text(SQL_DIRECOES_DE_SESSAO),
            {"chaves": [FEITO_TENTATIVAS, FEITO_TEMPO, FEITO_DICAS]},
        )
    ).mappings().all()
    reguas = (await conexao.execute(text(SQL_REGUAS_DA_NOTA))).mappings().all()
    return {
        "resolucoes": resolucoes,
        "pesos": [dict(p) for p in pesos],
        "regua_de_tempo": dict(regua_de_tempo),
        "direcoes": {d["co_feito"]: d["co_direcao"] for d in direcoes},
        "reguas": reguas_das_linhas([dict(r) for r in reguas]),
    }


async def _reguas_do_des(conexao) -> list[ReguaDaNota]:
    """As versoes da regua gravadas no `des`."""
    linhas = (await conexao.execute(text(SQL_REGUAS_DA_NOTA))).mappings().all()
    return reguas_das_linhas([dict(r) for r in linhas])


def _sessao(extrato: list[dict]) -> tuple[int, int, int, dict[str, Decimal]]:
    """(tentativas, tempo_ms, dicas, medidas do tabuleiro) de um extrato gravado.

    As tres de sessao sao as `vr_medida` das parcelas 2, 3 e 4; as medidas do
    tabuleiro sao as linhas de feito (`nu_feito` preenchido), inclusive a que so
    e medida e nao pontua (tipo 6), que tambem chega no envio.
    """
    por_tipo = {e["nu_tipo_xp"]: e for e in extrato if e["nu_feito"] is None}
    medidas = {
        e["co_feito"]: Decimal(e["vr_medida"]) for e in extrato if e["nu_feito"]
    }
    return (
        int(por_tipo[2]["vr_medida"]),
        int(por_tipo[3]["vr_medida"]),
        int(por_tipo[4]["vr_medida"]),
        medidas,
    )


def _calcular(dados: dict, resolucao: dict, regua: ReguaDaNota) -> list[ParcelaDeXp]:
    """A montagem do servidor, com a regua passada explicitamente."""
    tentativas, tempo_ms, dicas, medidas = _sessao(resolucao["extrato"])
    return montar_extrato(
        regua=regua,
        medidas=medidas,
        pesos=dados["pesos"],
        nu_tentativas=tentativas,
        nu_tempo_ms=tempo_ms,
        nu_dicas=dicas,
        nu_tempo_piso_ms=dados["regua_de_tempo"]["nu_tempo_piso_ms"],
        nu_tempo_teto_ms=dados["regua_de_tempo"]["nu_tempo_teto_ms"],
        direcoes=dados["direcoes"],
    )


def _xp_por_parcela(parcelas) -> dict[tuple, Decimal]:
    """`{(nu_tipo_xp, nu_feito): vr_xp}`, em tres casas."""
    return {
        (p.nu_tipo_xp, p.nu_feito): Decimal(p.vr_xp).quantize(MILESIMO)
        for p in parcelas
    }


def _gravado_por_parcela(extrato: list[dict]) -> dict[tuple, Decimal]:
    return {
        (e["nu_tipo_xp"], e["nu_feito"]): Decimal(e["vr_xp"]).quantize(MILESIMO)
        for e in extrato
    }


def _mesmas_parcelas(a: ReguaDaNota, b: ReguaDaNota) -> bool:
    """Duas versoes com os MESMOS numeros (peso, forma, x0, escala)."""
    def chave(r: ReguaDaNota):
        return {
            t: (p.vr_peso, p.co_forma, p.vr_x0, p.vr_escala)
            for t, p in r.parcelas.items()
        }
    return chave(a) == chave(b)


async def conferir() -> int:
    relatorio = Relatorio()
    dados = await _ler(url_do_prd(), _dados_do_prd)
    reguas_des = {r.nu_versao: r for r in await _ler(url_do_des(), _reguas_do_des)}
    reguas_prd = {r.nu_versao: r for r in dados["reguas"]}

    # Quem e quem: pelas tentativas gravadas.
    pessoas = {}
    for resolucao in dados["resolucoes"]:
        tentativas = _sessao(resolucao["extrato"])[0]
        pessoas[tentativas] = resolucao
    condicao = "(0) as duas resolucoes do empate, lidas do prd"
    relatorio.anotar(
        condicao,
        set(pessoas) == set(ESPERADO_NA_REGUA_2),
        f"tentativas encontradas: {sorted(pessoas)} (esperadas 2 e 9); "
        f"XP gravado: {sorted(r['nu_xp'] for r in dados['resolucoes'])}",
    )
    if set(pessoas) != set(ESPERADO_NA_REGUA_2):
        relatorio.imprimir()
        return 1

    # (a) CONTROLE: a regua 1 reproduz o que o servidor gravou em 10/10.
    condicao = "(a) controle: a regua 1 do des reproduz o extrato gravado no prd"
    for tentativas, (nome, _) in ESPERADO_NA_REGUA_2.items():
        resolucao = pessoas[tentativas]
        parcelas = _calcular(dados, resolucao, reguas_des[1])
        calculado = _xp_por_parcela(parcelas)
        gravado = _gravado_por_parcela(resolucao["extrato"])
        diferentes = {
            k: (gravado.get(k), calculado.get(k))
            for k in set(gravado) | set(calculado)
            if gravado.get(k) != calculado.get(k)
        }
        pontuacao = pontuacao_do_extrato(parcelas)
        relatorio.anotar(
            condicao,
            not diferentes and pontuacao == resolucao["nu_xp"],
            f"{nome}: {pontuacao} calculado × {resolucao['nu_xp']} gravado; "
            f"{len(gravado)} parcelas, "
            + ("todas iguais" if not diferentes else f"DIFERENTES: {diferentes}"),
        )

    # (b) as versoes de copia sao copias.
    condicao = "(b) no des, a versao 3 = a 1 e a versao 4 = a 2"
    for copia, original in ((3, 1), (4, 2)):
        relatorio.anotar(
            condicao,
            copia in reguas_des and _mesmas_parcelas(reguas_des[copia], reguas_des[original]),
            f"versao {copia} × versao {original}: "
            + ("mesmos pesos, formas e constantes" if copia in reguas_des
               and _mesmas_parcelas(reguas_des[copia], reguas_des[original])
               else "DIFERENTES ou ausente"),
        )

    # (c) a regua 2 do des e a mesma do prd (a 0030 e a mesma migracao).
    condicao = "(c) a regua 2 do des e a mesma do prd"
    iguais = 2 in reguas_prd and _mesmas_parcelas(reguas_des[2], reguas_prd[2])
    relatorio.anotar(
        condicao, iguais,
        "versao 2: " + ("identica nos dois bancos" if iguais else "DIFERENTE"),
    )

    # (d) A PROMESSA: a regua 2, passada explicitamente.
    condicao = "(d) a regua 2 (passada pelo numero) da Maria 23 e Fernando 22"
    for tentativas, (nome, esperado) in ESPERADO_NA_REGUA_2.items():
        parcelas = _calcular(dados, pessoas[tentativas], reguas_des[2])
        pontuacao = pontuacao_do_extrato(parcelas)
        detalhe = " + ".join(
            f"{p.vr_xp.quantize(MILESIMO)}" for p in parcelas if p.vr_xp
        )
        relatorio.anotar(
            condicao,
            pontuacao == esperado,
            f"{nome}: {pontuacao} (esperado {esperado}) = {detalhe}",
        )

    # (e) a vigencia no des: qual versao cada dia escolhe.
    condicao = "(e) a vigencia no des: 10/10 → 1, 12/10 → 2, 13/10 → 3, 14/10 → 4"
    for dia, versao in (
        (date(2026, 10, 10), 1),
        (date(2026, 10, 12), 2),
        (date(2026, 10, 13), 3),
        (date(2026, 10, 14), 4),
    ):
        escolhida = regua_vigente(reguas_des.values(), dia).nu_versao
        relatorio.anotar(
            condicao, escolhida == versao,
            f"{dia:%d/%m}: versao {escolhida} (esperada {versao})",
        )

    return 0 if relatorio.imprimir() else 1


def main() -> int:
    return asyncio.run(conferir())


if __name__ == "__main__":
    raise SystemExit(main())
