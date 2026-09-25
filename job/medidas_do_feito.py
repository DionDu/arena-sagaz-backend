"""O job ⛔ grava desafio de tipo cuja frase de feito ninguem declarou (T085za).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE MODULO EXISTE
═══════════════════════════════════════════════════════════════════════════

O cartao de quem resolveu diz o FEITO da pessoa (*"4 caixas em 2 turnos"*), e
cada tipo de desafio tem a sua frase no aplicativo. A frase le numeros do
retrato da resolucao (`desafio_dia.tb003_resolucao.js_feito`, a `0027`). O dono,
em 24/09/2026:

    "Precisamos de alguma forma de amarrar tambem que novos formatos e tipos de
     desafios, que serao gerados pelo gerador de desafios, sejam obrigados a
     ajustar este `js_feito` se necessario incluir nova medida para montar a
     frase de cumprimento dos desafios."

A declaracao do que cada frase le vive no aplicativo e chega aqui pelo
manifesto `contratos/medidas_do_feito.json` (gerado la, por
`tool/gerar_manifesto_medidas_do_feito.dart`). Este modulo e a **trava de
execucao**: [exigir_frase_do_feito] roda em `gravacao.montar_linha`, o ponto
unico em que um candidato vira linha de `desafio.tb001_desafio`.

⚠️ **Por que no job, e ⛔ so no teste**: o tipo em avaliacao (o da medicao do
editorial, que o gerador aceita por parametro proprio) nunca passa pelo cadeado
de `RECEITAS` - e e justamente o tipo novo. Com a trava na gravacao, nenhum
caminho publica um desafio que o aplicativo mostraria como *"Objetivo cumprido"*
para sempre. (⛔ O nome do parametro nao aparece aqui de proposito: um cadeado
de `tests/unitarios/test_gerador_de_candidatos.py` le o texto de todo arquivo
do job atras dele, e a primeira versao deste comentario o reprovou.)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

#: O manifesto, versionado neste repositorio. `parents[1]` sobe de `job/` ate a
#: raiz do backend.
MANIFESTO = Path(__file__).resolve().parents[1] / "contratos" / "medidas_do_feito.json"


class FraseDoFeitoNaoDeclarada(ValueError):
    """O tipo ⛔ declarou o que a frase de feito dele le - ⛔ e publicavel.

    ⚠️ Falha alto de proposito, como `TipoSemReceita`: o desafio sairia, a
    pessoa resolveria, e o cartao diria *"Objetivo cumprido"* para sempre - sem
    erro em lugar nenhum.
    """


@lru_cache(maxsize=1)
def frases_declaradas() -> dict[str, dict[str, Any]]:
    """As entradas do manifesto, pela chave de i18n do objetivo.

    `lru_cache` = o arquivo e lido uma vez por processo (o job grava dezenas de
    candidatos por execucao, e o manifesto ⛔ muda no meio dela).

    Raises:
        FileNotFoundError: manifesto ausente. ⛔ Devolver `{}` aqui faria
            a trava recusar TUDO - ou, se alguem a "consertasse" tolerando o
            vazio, aceitar tudo.
    """
    conteudo = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    return {entrada["co_chave_objetivo"]: entrada for entrada in conteudo["frases"]}


def exigir_frase_do_feito(
    *, co_chave_objetivo: str, co_jogo: str, js_chegada: Mapping[str, Any]
) -> None:
    """Recusa o desafio cuja frase de feito ⛔ esta declarada, ou ⛔ bate.

    Tres conferencias:

      1. a chave do objetivo tem entrada no manifesto;
      2. a entrada e do mesmo jogo - a frase le medidas do medidor DAQUELE jogo;
      3. se a frase precisa de quanto da janela foi gasto, a chegada TEM janela
         contada (turnos ou lances) - com a janela `partida` o aplicativo ⛔ tem
         o que contar, e a frase ficaria muda.

    Raises:
        FraseDoFeitoNaoDeclarada: em qualquer das tres.
    """
    entrada = frases_declaradas().get(co_chave_objetivo)
    if entrada is None:
        raise FraseDoFeitoNaoDeclarada(
            f"o objetivo {co_chave_objetivo!r} ⛔ tem frase de feito declarada. "
            "Declare as medidas dela em medidasDoFeitoPorObjetivo (app, "
            "lib/modulos/desafio_do_dia/logica/medidas_do_feito.dart), rode "
            "tool/gerar_manifesto_medidas_do_feito.dart e commite as duas copias "
            "- ANTES de publicar o tipo."
        )
    if entrada["co_jogo"] != co_jogo:
        raise FraseDoFeitoNaoDeclarada(
            f"o objetivo {co_chave_objetivo!r} esta declarado para o jogo "
            f"{entrada['co_jogo']!r}, e o desafio e de {co_jogo!r}. A frase leria "
            "medidas que o medidor deste jogo ⛔ produz."
        )
    tipo_da_janela = (js_chegada.get("janela") or {}).get("tipo")
    if entrada["janela_gasta"] and tipo_da_janela in (None, "partida"):
        raise FraseDoFeitoNaoDeclarada(
            f"a frase de {co_chave_objetivo!r} precisa de quanto da janela foi "
            f"gasto, e a chegada tem janela {tipo_da_janela!r} - o aplicativo ⛔ "
            "tem o que contar."
        )
