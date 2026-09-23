"""AS MEDIDAS DE SAIDA DO XP: o que este desafio produz (RF-DES-219/223, T037).

═══════════════════════════════════════════════════════════════════════════
DUAS COISAS SAO GRAVADAS AQUI
═══════════════════════════════════════════════════════════════════════════

  1. as linhas de `desafio.tb003_feito_desafio` — que medidas este desafio
     produz, com que peso e como cada uma vira um numero entre 0 e 1;
  2. a **regua de tempo** de `tb001_desafio` (`nu_tempo_piso_ms`/`nu_tempo_teto_ms`),
     sem a qual *"rapido"* nao teria contra o que medir.

═══════════════════════════════════════════════════════════════════════════
⚠️ A DIRECAO NAO E ESCRITA AQUI — E ELA E O DEFEITO MAIS SILENCIOSO DO XP
═══════════════════════════════════════════════════════════════════════════

A direcao de cada feito vem de `desafio.tb902_catalogo_feito.co_direcao`, e ⛔
**nao se escreve duas vezes**: mais tentativas, mais tempo e mais dica
**reduzem** o XP; mais merito aumenta.

⚠️ **Uma parcela na direcao errada NAO daria erro nenhum** — so pagaria mais a
quem jogou pior. Por isso ela mora no catalogo, uma vez, e por isso este modulo
**le** o catalogo em vez de repetir a informacao.

═══════════════════════════════════════════════════════════════════════════
⚠️ OS PESOS SOMAM 1,000, E ISSO E TESTE, NAO `CHECK`
═══════════════════════════════════════════════════════════════════════════

Soma entre linhas nao cabe num `CHECK` de linha. Quem confere e um teste — e a
funcao [conferir] aqui, que o job chama antes de gravar.

⚠️ **Peso zero e legitimo**: o feito continua sendo medido e exibido no Raio-X, so
nao conta para a nota. O `ck003_faixa` da migracao amarra os dois: `nenhuma` so
existe com peso zero.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "contratos" / "catalogo_feitos.json"

#: As tres normalizacoes, e o `CHECK` da migracao `0018`.
FAIXA = "faixa"
FRACAO = "fracao"
NENHUMA = "nenhuma"

#: A regua de tempo padrao, em milissegundos.
#:
#: ⚠️ **O piso e o tempo do gabarito jogado direto**; o teto e onde a parcela de
#: tempo zera. Os dois saem da medicao, e estes numeros sao so o ponto de partida
#: de quem ainda nao mediu nada.
#:
#: ⚠️ Teto igual ao piso faria a parcela de tempo dividir por zero — o
#: `ck007_regua_tempo` da migracao recusa, e a funcao abaixo recusa antes.
#: Onde a parcela da economia de lances ZERA, em multiplos dos lances da solucao
#: (T049t, decisao do dono de 23/09/2026, `DECISOES-do-dono.md` §8v).
#:
#: ⚠️ **3, e nao 2**: quem joga 1,5x os lances do gabarito ainda leva 75% da
#: parcela - o desafio e casual, e jogar um pouco mais que o gabarito nao e
#: errar. A parcela pesa 0,3 a 0,4 do merito, que pesa 0,25 de `Q`.
MULTIPLO_DA_ECONOMIA_DE_LANCES = 3

#: A chave, NOS PARAMETROS que as medidas recebem, com os lances do SOLUCIONADOR
#: na solucao oficial. ⚠️ **E parametro, e ⛔ medida**: ate a T049t ela era o
#: `co_sobre` de uma `fracao`, e o contrato manda que `sobre` seja **outra medida
#: da mesma partida** - o tamanho do gabarito e um numero fixo do desafio, e o
#: lugar dele e a `faixa`. Com a fracao, NINGUEM conseguia resolver: o aplicativo
#: recusava calcular `Q` (`MedidaDeSaidaInvalida`) e o servidor, a resolucao.
PARAMETRO_LANCES_DA_SOLUCAO = "lances_da_solucao"

PISO_DE_TEMPO_MINIMO_MS = 5_000
FOLGA_DO_TETO = 6.0


class MedidasInvalidas(ValueError):
    """As medidas de saida nao formam um conjunto gravavel.

    ⚠️ Defeito do DESAFIO: ele nao deveria ser publicado. Quem recebe isto na
    geracao descarta o candidato.
    """


def _catalogo() -> dict[str, dict[str, Any]]:
    """O catalogo de feitos, indexado por chave.

    ⚠️ Le o manifesto versionado, e nao o banco: o job precisa saber a direcao de
    um feito **antes** de gravar, e o manifesto e a mesma coisa que a dimensao
    (o cadeado 4 garante).
    """
    if not CATALOGO.is_file():
        raise MedidasInvalidas(
            f"o manifesto do catalogo de feitos nao esta em {CATALOGO}. Sem ele "
            "nao ha como saber a direcao de cada medida, e uma parcela na direcao "
            "errada nao daria erro — so pagaria mais a quem jogou pior."
        )
    dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return {linha["co_feito"]: linha for linha in dados["feitos"]}


def linha_de_faixa(
    co_feito: str, *, nu_ordem: int, vr_peso: str, vr_min: float, vr_max: float
) -> dict[str, Any]:
    """Uma medida normalizada por FAIXA: `(medido - min) / (max - min)`.

    ⚠️ `vr_peso` entra como **texto** (`"0.600"`) e vira `Decimal`: somar `0.6` e
    `0.4` em ponto flutuante nao da `1.0`, e a soma dos pesos precisa fechar em
    1,000 exatos.
    """
    return {
        "co_feito": co_feito,
        "nu_ordem": nu_ordem,
        "vr_peso": Decimal(vr_peso),
        "co_normalizacao": FAIXA,
        "vr_min": Decimal(str(vr_min)),
        "vr_max": Decimal(str(vr_max)),
        "co_sobre": None,
    }


def linha_de_fracao(
    co_feito: str, *, nu_ordem: int, vr_peso: str, co_sobre: str
) -> dict[str, Any]:
    """Uma medida normalizada por FRACAO: `medido / <co_sobre>`."""
    return {
        "co_feito": co_feito,
        "nu_ordem": nu_ordem,
        "vr_peso": Decimal(vr_peso),
        "co_normalizacao": FRACAO,
        "vr_min": None,
        "vr_max": None,
        "co_sobre": co_sobre,
    }


def lances_do_solucionador(js_solucao: Mapping[str, Any], *, vez_de: int) -> int:
    """Quantos lances da solucao oficial sao **de quem resolve** o desafio.

    ⚠️ **So os dele, e nao o tamanho da solucao**: nas damas a solucao traz os
    lances dos dois lados (`nu_lances_solucao` = 9 no `damas_coroar` de
    23/09/2026, dos quais 5 da pessoa), e `lances_do_jogador` conta so os dela.
    Comparar a medida da pessoa com o total dos dois lados faria todo mundo
    parecer economico.

    Args:
        js_solucao: o gabarito (`{"lances": [{"jogador": 1, ...}, ...]}`).
        vez_de: o sinal de quem resolve - `js_posicao_inicial["vez_de"]`, o mesmo
            que o juiz usa.
    """
    return sum(1 for lance in js_solucao["lances"] if lance["jogador"] == vez_de)


def linha_da_economia_de_lances(
    p: Mapping[str, Any], *, nu_ordem: int, vr_peso: str
) -> dict[str, Any]:
    """A parcela da economia de lances: FAIXA de `L` a `3L` (T049t, §8v).

    `L` sao os lances do solucionador na solucao oficial
    ([PARAMETRO_LANCES_DA_SOLUCAO], que o job poe nos parametros ao publicar).
    Com `lances_do_jogador` em `menor_melhor`:

        jogou L lances (o gabarito)   ->  nota 1,0
        jogou 1,5 L                   ->  nota 0,75
        jogou 3 L ou mais             ->  nota 0,0

    E a mesma forma da regua de tempo: piso = o gabarito, teto = onde zera.
    """
    lances = int(p[PARAMETRO_LANCES_DA_SOLUCAO])
    if lances <= 0:
        raise MedidasInvalidas(
            f"a solucao oficial tem {lances} lance(s) de quem resolve - sem "
            "eles a economia de lances nao tem de onde partir"
        )
    return linha_de_faixa(
        "lances_do_jogador",
        nu_ordem=nu_ordem,
        vr_peso=vr_peso,
        vr_min=lances,
        vr_max=lances * MULTIPLO_DA_ECONOMIA_DE_LANCES,
    )


def linha_so_medida(co_feito: str, *, nu_ordem: int) -> dict[str, Any]:
    """Uma medida **exibida e nao pontuada**.

    ⚠️ Peso zero nao e desperdicio: *"quantas caixas voce deixou o adversario
    fechar"* interessa em qualquer desafio de Pontinhos, mas so e **merito** num
    desafio cujo objetivo seja nao entrega-las.
    """
    return {
        "co_feito": co_feito,
        "nu_ordem": nu_ordem,
        "vr_peso": Decimal("0.000"),
        "co_normalizacao": NENHUMA,
        "vr_min": None,
        "vr_max": None,
        "co_sobre": None,
    }


def conferir(linhas: Sequence[Mapping[str, Any]]) -> None:
    """As linhas formam um conjunto gravavel?

    Confere, na ordem em que os defeitos custam caro:

      1. **toda chave existe no catalogo** — uma chave inventada seria uma medida
         que nenhum jogo produz, e o desafio pagaria zero naquela parcela sempre;
      1b. ⛔ **nenhuma chave e de SESSAO** — tempo, tentativas e dicas ja tem peso
         fixo em `Q` (0,20, 0,30 e 0,25); pesa-las tambem no merito faria a mesma
         medida contar **duas vezes**, e a soma dos pesos continuaria 1,000 sem
         que nada acusasse;
      2. **os pesos somam 1,000** — a soma e o que faz `Q` ficar em [0, 1];
      3. **cada normalizacao tem os seus campos** — o `ck003_faixa` diz o mesmo,
         e falhar aqui aponta para quem montou as linhas;
      4. **a ordem de exibicao nao repete** — o Raio-X mostraria duas medidas na
         mesma posicao;
      5. ⛔ **o `co_sobre` de uma `fracao` e MEDIDA DO TABULEIRO do catalogo**
         (T049t) — o denominador e outra medida da mesma partida. Ate 23/09/2026
         o editorial publicava `lances_da_solucao` ali, que nao e medida nenhuma,
         e nenhuma resolucao daqueles desafios era possivel.

    Raises:
        MedidasInvalidas: em qualquer um dos quatro casos.
    """
    if not linhas:
        raise MedidasInvalidas(
            "desafio sem medida de saida nenhuma: o Raio-X ficaria vazio e `Q` "
            "nao teria de que ser calculado"
        )

    catalogo = _catalogo()

    desconhecidas = [l["co_feito"] for l in linhas if l["co_feito"] not in catalogo]
    if desconhecidas:
        raise MedidasInvalidas(
            f"chaves fora do catalogo de feitos: {desconhecidas}. ⚠️ Uma chave "
            "inventada e uma medida que nenhum jogo produz — a parcela pagaria "
            "zero para sempre, sem erro nenhum."
        )

    # ⛔ Medida de SESSAO nao entra no merito (16/09/2026). O merito e o que a
    # pessoa fez **no jogo**; tempo, tentativas e dicas sao a sessao, e ja pesam
    # em `Q` por fora. Pesa-las aqui pagaria a mesma coisa duas vezes — e, como a
    # soma dos relativos continuaria 1,000, nenhuma outra conferencia veria.
    de_sessao = [
        l["co_feito"]
        for l in linhas
        if catalogo[l["co_feito"]]["co_procedencia"] == "sessao"
    ]
    if de_sessao:
        raise MedidasInvalidas(
            f"medidas de sessao entre os pesos do merito: {de_sessao}. ⚠️ Tempo, "
            "tentativas e dicas ja tem peso proprio em Q (RF-DES-042); no merito "
            "elas contariam uma segunda vez."
        )

    soma = sum((l["vr_peso"] for l in linhas), start=Decimal("0"))
    if soma != Decimal("1.000"):
        raise MedidasInvalidas(
            f"os pesos somam {soma}, e precisam somar 1.000 — e a soma que "
            "mantem `Q` dentro de [0, 1]"
        )

    ordens = [l["nu_ordem"] for l in linhas]
    if len(set(ordens)) != len(ordens):
        raise MedidasInvalidas(f"ha nu_ordem repetido: {ordens}")
    if any(o < 1 for o in ordens):
        raise MedidasInvalidas(f"nu_ordem comeca em 1; veio {ordens}")

    for linha in linhas:
        _conferir_normalizacao(linha, catalogo)


def _conferir_normalizacao(
    linha: Mapping[str, Any], catalogo: Mapping[str, Mapping[str, Any]]
) -> None:
    """Cada normalizacao exige os SEUS campos, e proibe os outros.

    ⚠️ Sem isto, uma linha `faixa` sem `vr_max` divide por nulo na hora de
    pontuar — e o erro apareceria no calculo do XP de alguem.
    """
    norma = linha["co_normalizacao"]
    chave = linha["co_feito"]

    if norma == FAIXA:
        if linha["vr_min"] is None or linha["vr_max"] is None:
            raise MedidasInvalidas(f"{chave}: `faixa` exige vr_min e vr_max")
        if linha["vr_max"] <= linha["vr_min"]:
            raise MedidasInvalidas(
                f"{chave}: vr_max ({linha['vr_max']}) precisa ser maior que "
                f"vr_min ({linha['vr_min']}) — iguais dividiriam por zero"
            )
        if linha["co_sobre"] is not None:
            raise MedidasInvalidas(f"{chave}: `faixa` nao usa co_sobre")

    elif norma == FRACAO:
        sobre = linha["co_sobre"]
        if not sobre:
            raise MedidasInvalidas(f"{chave}: `fracao` exige co_sobre")
        # ⛔ **O denominador e OUTRA MEDIDA DA MESMA PARTIDA** (contrato
        # `desafio-publicado.md`). Fora do catalogo, nenhum jogo a produz: o
        # aplicativo recusa calcular `Q` e o servidor recusa a resolucao - o
        # desafio nasce sem resolucao possivel (T049t). De sessao, ela ja pesa
        # em `Q` por fora.
        if sobre not in catalogo:
            raise MedidasInvalidas(
                f"{chave}: a fracao e sobre `{sobre}`, que nao esta no catalogo "
                "de feitos - nenhum jogo a mede, e ninguem resolveria o desafio. "
                "Um numero fixo do desafio (o tamanho do gabarito) e `faixa`."
            )
        if catalogo[sobre]["co_procedencia"] != "tabuleiro":
            raise MedidasInvalidas(
                f"{chave}: a fracao e sobre `{sobre}`, que nao e medida do "
                "tabuleiro - o denominador precisa sair da mesma partida"
            )
        if linha["vr_min"] is not None or linha["vr_max"] is not None:
            raise MedidasInvalidas(f"{chave}: `fracao` nao usa vr_min/vr_max")

    elif norma == NENHUMA:
        if linha["vr_peso"] != Decimal("0.000"):
            raise MedidasInvalidas(
                f"{chave}: `nenhuma` so existe com peso zero — medido e exibido, "
                "nao pontuado"
            )
        if any(linha[campo] is not None for campo in ("vr_min", "vr_max", "co_sobre")):
            raise MedidasInvalidas(f"{chave}: `nenhuma` nao usa campo nenhum")

    else:
        raise MedidasInvalidas(f"{chave}: normalizacao {norma!r} nao existe")


def direcao_de(co_feito: str) -> str:
    """A direcao daquele feito, lida do catalogo.

    ⚠️ **Lida, e nunca escrita aqui.** A direcao mora no catalogo uma vez, e e
    ela que faz mais tempo e mais dicas **reduzirem** o XP.
    """
    catalogo = _catalogo()
    if co_feito not in catalogo:
        raise MedidasInvalidas(f"o feito {co_feito!r} nao esta no catalogo")
    return catalogo[co_feito]["co_direcao"]


def regua_de_tempo(*, nu_tempo_do_gabarito_ms: int) -> tuple[int, int]:
    """O piso e o teto da parcela de tempo, em milissegundos.

    Args:
        nu_tempo_do_gabarito_ms: quanto leva jogar a solucao direto.

    Returns:
        `(nu_tempo_piso_ms, nu_tempo_teto_ms)`.

    ⚠️ **O piso e o tempo do gabarito jogado direto** — ninguem resolve mais
    rapido que a propria solucao —, e o teto e onde a parcela zera. Sem os dois,
    *"rapido"* nao teria contra o que medir.

    ⚠️ **Teto igual ao piso dividiria por zero** na hora de normalizar, e o
    `ck007_regua_tempo` da migracao recusa. Aqui a folga e multiplicativa, para
    que um desafio curto nao ganhe uma janela absurda nem um longo, uma apertada.
    """
    piso = max(PISO_DE_TEMPO_MINIMO_MS, int(nu_tempo_do_gabarito_ms))
    teto = int(piso * FOLGA_DO_TETO)
    if teto <= piso:
        raise MedidasInvalidas(
            f"regua de tempo degenerada: piso={piso} teto={teto}"
        )
    return piso, teto
