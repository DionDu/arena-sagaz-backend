"""A PESCARIA LE O ARQUIVO SEJA QUAL FOR A CODIFICACAO (14/09/2026).

⛔ **Este script ja tropecou na codificacao DUAS vezes**, e a segunda custou uma
pescaria inteira: o dono rodou o comando que eu dei, o PowerShell escreveu o JSON
em **UTF-16LE com BOM** (e o `>` dele que decide isso, nao o Python que o gerou),
e a pescaria morreu no primeiro byte:

    UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0

⚠️ **O erro chega longe da causa.** Quem o le pensa em dado corrompido; o arquivo
esta perfeito, e o que esta errado e a suposicao de quem o abriu.

⚠️ A primeira vez foi no CSV, com o BOM de UTF-8: a primeira coluna passava a se
chamar `﻿fen`, o cabecalho parecia certo na tela e o `linha["fen"]` falhava.

⛔ **A cura nao pode ser "lembrar do encoding certo no comando"** - foi
exatamente isso que falhou das duas vezes. Ela e ler os primeiros bytes e
perguntar ao arquivo.
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from scripts.pescar_moldes_de_partidas import carregar

#: Duas posicoes de verdade, com as brancas a jogar em uma e as pretas na outra.
#:
#: ⚠️ **A segunda existe para provar o espelho junto**: `carregar` normaliza tudo
#: para as brancas, e um teste so com `W:` passaria sem tocar nesse caminho.
FENS = ["W:W21,26,30:B5,7,10", "B:W24,29:B9,11,14"]

#: As codificacoes que um arquivo pode chegar tendo, e quem as produz.
#:
#: ⛔ `utf-16` (sem sufixo) e o que o `>` do PowerShell escreve em varias versoes,
#: e ele **sempre** poe BOM. `utf-8-sig` e o que o Excel e o export do Postgres no
#: Windows escrevem. `utf-8` puro e o que o `consultar_des.py` escreve.
#:
#: ⚠️ **`utf-16-le` e `utf-16-be` SEM BOM ficam de fora, e isso e uma escolha.**
#: Sem o rotulo no comeco, distinguir UTF-16 de UTF-8 exige adivinhar pelo padrao
#: dos bytes nulos — heuristica que erra em arquivo pequeno. ⛔ Nenhuma ferramenta
#: deste fluxo escreve UTF-16 sem BOM, entao suportar isso custaria adivinhacao
#: paga com o risco de ler o arquivo errado **em silencio**.
CODIFICACOES = ["utf-8", "utf-8-sig", "utf-16"]


@pytest.mark.parametrize("codificacao", CODIFICACOES)
def test_o_json_e_lido_em_qualquer_codificacao(tmp_path, codificacao: str):
    """⛔ O caso que custou a pescaria de 14/09."""
    arquivo = tmp_path / "fens.json"
    texto = json.dumps([{"fen": f} for f in FENS])
    arquivo.write_bytes(texto.encode(codificacao))

    lidas = carregar(arquivo)
    assert len(lidas) == 2, f"{codificacao}: esperava 2 posicoes, veio {lidas}"
    # ⚠️ Toda posicao sai com as brancas a jogar — inclusive a que entrou com `B:`.
    assert all(f.startswith("W:") for f in lidas), lidas


@pytest.mark.parametrize("codificacao", CODIFICACOES)
def test_o_csv_e_lido_em_qualquer_codificacao(tmp_path, codificacao: str):
    """⚠️ O mesmo cadeado no outro formato.

    ⛔ **E aqui o BOM nao explode: ele CONTAMINA.** Sem descarta-lo, a primeira
    coluna se chama `﻿fen` — com um caractere invisivel na frente —, o cabecalho
    parece certo na tela, e o `linha["fen"]` levanta `KeyError` apontando para uma
    coluna que esta la.
    """
    # ⚠️ **Pelo `csv.writer`, e nao por concatenacao**: a FEN tem virgulas
    # (`W:W21,26,30:...`), e um CSV escrito a mao as entregaria como separador de
    # coluna. O export do Postgres poe as aspas; o teste tem de por tambem, senao
    # ele reprova o script por um defeito que e do proprio teste.
    arquivo = tmp_path / "fens.csv"
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(["fen"])
    escritor.writerows([[f] for f in FENS])
    arquivo.write_bytes(buffer.getvalue().encode(codificacao))

    lidas = carregar(arquivo)
    assert len(lidas) == 2, f"{codificacao}: esperava 2 posicoes, veio {lidas}"
    assert all(f.startswith("W:") for f in lidas), lidas


def test_o_BOM_nao_vira_caractere_da_primeira_FEN(tmp_path):
    """⛔ O BOM e um rotulo de codificacao, e nao um caractere.

    ⚠️ Deixa-lo passar seria o pior dos mundos: o arquivo carregaria **sem erro**,
    e a primeira FEN da lista sairia com um caractere invisivel na frente. Ela
    falharia na montagem do estado, uma posicao entre milhares, e o motivo do
    descarte seria contado como `montagem:ValueError`.
    """
    arquivo = tmp_path / "fens.json"
    arquivo.write_bytes(json.dumps([{"fen": FENS[0]}]).encode("utf-8-sig"))

    assert carregar(arquivo) == [FENS[0]]


def test_arquivo_sem_BOM_continua_sendo_utf8(tmp_path):
    """⚠️ O caminho normal — o que o `consultar_des.py` escreve — nao muda."""
    arquivo = tmp_path / "fens.json"
    arquivo.write_text(json.dumps([{"fen": FENS[0]}]), encoding="utf-8")

    assert carregar(arquivo) == [FENS[0]]
