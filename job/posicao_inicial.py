"""A POSICAO INICIAL de um desafio, nos dois formatos (RF-DES-218/221, T031).

═══════════════════════════════════════════════════════════════════════════
DOIS FORMATOS, E A DIFERENCA E DO JOGO — NAO E GOSTO
═══════════════════════════════════════════════════════════════════════════

    co_formato_posicao = 'fen'                → damas
    co_formato_posicao = 'sequencia_lances'   → Pontinhos

Nas damas **cada peca carrega a sua cor na propria casa**, e a FEN ja traz de
quem e a vez no prefixo `W:`/`B:`. A posicao se descreve sozinha.

No Pontinhos a posse de uma caixa e **historico**: o tabuleiro fisico nao guarda
quem a fechou. Uma posicao so existe como a sequencia que a produziu.

⚠️ E por isso que uma matriz **nao** foi escolhida para o Pontinhos, e os tres
motivos estao no `data-model.md`:

  1. a migracao `0006` ja reconstroi o tabuleiro a partir das arestas, do vazio.
     Uma matriz criaria um SEGUNDO caminho de reconstrucao, so para o desafio —
     e dois caminhos para a mesma coisa e como as tres telas de fim de partida
     divergiram;
  2. a matriz **nao diz de quem e a vez**: quem fecha caixa joga de novo, e uma
     posicao com tres caixas fechadas e compativel com a vez de qualquer um dos
     dois — a diferenca muda o desafio inteiro;
  3. a matriz **nao e auditavel**: nada nela impede uma caixa fechada sem os
     quatro lados, ou um placar que nenhuma partida legal produziria.

═══════════════════════════════════════════════════════════════════════════
⚠️ `vez_de` E `placar` SAO DERIVADOS, E ESTAO NA LINHA COMO CONFERENCIA
═══════════════════════════════════════════════════════════════════════════

O job reconstroi a sequencia, recalcula os dois e **compara com o que gravou**.
Divergiu, ⛔ **nao publica**.

E o mesmo principio de `ic_chegada_encerra_partida`: ninguem digita, e o que esta
escrito tem de bater com o que se calcula. Um `vez_de` errado no banco produziria
um desafio que o aplicativo comeca com o jogador errado — sem erro nenhum.
"""

from __future__ import annotations

from typing import Any, Mapping

from motores.damas.motor_damas import EstadoDamas
from motores.pontinhos.motor_pontinhos import EstadoPontinhos

#: A versao do formato de `js_posicao_inicial`.
VERSAO = 1

#: Os dois valores de `co_formato_posicao`, e o `CHECK` da migracao `0018`.
FORMATO_SEQUENCIA = "sequencia_lances"
FORMATO_FEN = "fen"


class PosicaoInvalida(ValueError):
    """A posicao inicial nao descreve um estado alcancavel.

    ⚠️ **Isto e defeito do DESAFIO, e nao da tentativa de ninguem.** Quem o
    recebe na geracao descarta o candidato; quem o recebe na leitura descobriu
    dado corrompido no banco.
    """


# ═══════════════════════════════════════════════════════════════════════════
# Escrever
# ═══════════════════════════════════════════════════════════════════════════


def do_pontinhos(lances: list[str], *, jogador_inicial: int = 1) -> dict[str, Any]:
    """Monta `js_posicao_inicial` a partir da sequencia de tracos marcados.

    Args:
        lances: os rotulos (`H_0_1`, `V_1_0`, …) na ordem em que foram marcados.
        jogador_inicial: quem abriu a preparacao. `+1` por padrao, como no
            aplicativo.

    Returns:
        O JSON com `versao`, `lances` (cada um com o jogador que o fez), `vez_de`
        e `placar`.

    Raises:
        PosicaoInvalida: se a sequencia repetir um traco ou usar rotulo que nao
            existe no tabuleiro.

    ⚠️ **O jogador de cada lance nao e "par/impar"**: quem fecha caixa joga de
    novo. A alternancia sai da reproducao pelo motor, lance a lance — escreve-la
    a mao daria uma sequencia que o proprio motor recusaria.
    """
    estado = EstadoPontinhos()
    anotados: list[dict[str, Any]] = []

    try:
        for ordem, lance in enumerate(lances, start=1):
            anotados.append(
                {"n": ordem, "jogador": estado.vez_de, "lance": lance}
            )
            estado = estado.com_lance(lance)
        # Força a reproducao completa: o motor so valida quando lhe perguntam.
        placar = estado.placar
        vez = estado.vez_de
    except ValueError as erro:
        raise PosicaoInvalida(f"sequencia de Pontinhos invalida: {erro}") from erro

    if jogador_inicial != 1:
        # O motor sempre comeca pelo jogador 1 — e a regra do aplicativo. Uma
        # posicao que comecasse pelo outro exigiria virar a sequencia inteira, e
        # ninguem precisa disso hoje: falha alto em vez de fingir que atende.
        raise PosicaoInvalida(
            "o Pontinhos sempre abre com o jogador 1; nao ha como montar uma "
            f"preparacao comecando por {jogador_inicial}"
        )

    return {
        "versao": VERSAO,
        "lances": anotados,
        "vez_de": vez,
        "placar": {"j1": placar[1], "j2": placar[-1]},
    }


def das_damas(fen: str, *, co_modalidade: str = "brasileira") -> dict[str, Any]:
    """Monta `js_posicao_inicial` a partir de uma FEN.

    Raises:
        PosicaoInvalida: se a FEN nao for legivel pelo motor.

    ⚠️ `vez_de` sai da PROPRIA FEN (o prefixo `W:`/`B:`), e nao de um campo ao
    lado: duas fontes para o mesmo fato acabam discordando, e a que estivesse
    errada mandaria.
    """
    try:
        estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        vez = estado.vez_de
        # Reler a FEN pelo motor normaliza a escrita (ordem das casas, espacos):
        # duas FEN diferentes que descrevem a mesma posicao viram uma so, e o
        # `UNIQUE` do banco passa a significar o que promete.
        normalizada = estado.fen
    except (ValueError, KeyError, IndexError) as erro:
        raise PosicaoInvalida(f"FEN invalida: {fen!r} ({erro})") from erro

    return {"versao": VERSAO, "fen": normalizada, "vez_de": vez}


# ═══════════════════════════════════════════════════════════════════════════
# Ler e CONFERIR
# ═══════════════════════════════════════════════════════════════════════════


def conferir(
    co_formato: str,
    posicao: Mapping[str, Any],
    *,
    co_modalidade: str = "brasileira",
) -> None:
    """Reconstroi a posicao e exige que os derivados batam com o que esta escrito.

    ⚠️ **E este passo que faz `vez_de` e `placar` valerem alguma coisa.** Sem ele
    os dois campos seriam anotacao decorativa, e um desafio com a vez errada
    passaria pelo banco e quebraria no aparelho de quem o jogasse.

    Raises:
        PosicaoInvalida: quando o formato nao existe, a posicao nao e
            reproduzivel, ou os derivados divergem.
    """
    if posicao.get("versao") != VERSAO:
        raise PosicaoInvalida(
            f"js_posicao_inicial versao {posicao.get('versao')!r}; esperada {VERSAO}"
        )

    if co_formato == FORMATO_SEQUENCIA:
        _conferir_sequencia(posicao)
    elif co_formato == FORMATO_FEN:
        _conferir_fen(posicao, co_modalidade)
    else:
        raise PosicaoInvalida(
            f"co_formato_posicao {co_formato!r} nao existe. Os dois sao "
            f"{FORMATO_SEQUENCIA!r} e {FORMATO_FEN!r}."
        )


def _conferir_sequencia(posicao: Mapping[str, Any]) -> None:
    """A conferencia do Pontinhos: reproduz a sequencia e compara vez e placar."""
    lances = posicao.get("lances")
    if not isinstance(lances, list):
        raise PosicaoInvalida("js_posicao_inicial.lances precisa ser uma lista")

    try:
        estado = EstadoPontinhos(lances=tuple(l["lance"] for l in lances))
        placar = estado.placar
        vez = estado.vez_de
    except (ValueError, KeyError, TypeError) as erro:
        raise PosicaoInvalida(f"sequencia irreproduzivel: {erro}") from erro

    if posicao.get("vez_de") != vez:
        raise PosicaoInvalida(
            f"vez_de gravado ({posicao.get('vez_de')!r}) nao bate com o "
            f"reconstruido ({vez!r}). ⛔ Nao publique este desafio."
        )

    escrito = posicao.get("placar") or {}
    calculado = {"j1": placar[1], "j2": placar[-1]}
    if escrito != calculado:
        raise PosicaoInvalida(
            f"placar gravado ({escrito}) nao bate com o reconstruido "
            f"({calculado}). ⛔ Nao publique este desafio."
        )

    # ⚠️ O jogador anotado em cada lance tambem e derivado, e tambem se confere:
    # e ele que o medidor por fita usa para saber onde um turno comeca.
    reproduzido = EstadoPontinhos()
    for lance in lances:
        if lance.get("jogador") != reproduzido.vez_de:
            raise PosicaoInvalida(
                f"o lance {lance.get('n')} esta anotado como do jogador "
                f"{lance.get('jogador')!r}, mas na reproducao a vez e de "
                f"{reproduzido.vez_de!r} — quem fecha caixa joga de novo, e a "
                "anotacao tem de refletir isso."
            )
        reproduzido = reproduzido.com_lance(lance["lance"])


def _conferir_fen(posicao: Mapping[str, Any], co_modalidade: str) -> None:
    """A conferencia das damas: a FEN e legivel, e a vez bate com o prefixo."""
    fen = posicao.get("fen")
    if not isinstance(fen, str) or not fen:
        raise PosicaoInvalida("js_posicao_inicial.fen ausente")

    try:
        estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        vez = estado.vez_de
    except (ValueError, KeyError, IndexError) as erro:
        raise PosicaoInvalida(f"FEN irreproduzivel: {fen!r} ({erro})") from erro

    if posicao.get("vez_de") != vez:
        raise PosicaoInvalida(
            f"vez_de gravado ({posicao.get('vez_de')!r}) nao bate com o prefixo "
            f"da FEN ({vez!r}). ⛔ Nao publique este desafio."
        )


def formato_do_jogo(co_jogo: str) -> str:
    """Qual formato aquele jogo usa.

    ⚠️ **Jogo novo entra aqui, e falha alto se nao entrar.** Um jogo sem formato
    declarado gravaria a posicao no formato errado — e o aplicativo tentaria ler
    uma FEN como sequencia, sem que nada dissesse por que.
    """
    formatos = {"pontinhos": FORMATO_SEQUENCIA, "damas": FORMATO_FEN}
    if co_jogo not in formatos:
        raise PosicaoInvalida(
            f"o jogo {co_jogo!r} nao declarou formato de posicao. Jogo novo entra "
            "em `formato_do_jogo`, ou nao e publicavel."
        )
    return formatos[co_jogo]
