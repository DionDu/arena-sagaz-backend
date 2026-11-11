"""O AVALIADOR DE RESOLUCOES (RF-DES-035/036, SC-013 — T043a).

═══════════════════════════════════════════════════════════════════════════
⚠️ ELE NAO E O MESMO QUE T029, E CONFUNDI-LOS SERIA CARO
═══════════════════════════════════════════════════════════════════════════

    T029 (`motores/nucleo/medidor_por_fita.py`)  → confere o **CANDIDATO**,
                                                   dentro do gerador
    T043a (este arquivo)                         → audita a **RESOLUCAO** que
                                                   chegou do aplicativo

Os dois reproduzem uma fita, e e so isso que tem em comum. Um pergunta *"este
desafio e resolvivel?"*; o outro, *"o que esta pessoa mandou bate com o que os
lances dela dizem?"*.

═══════════════════════════════════════════════════════════════════════════
⚠️ "VALIDAR NAO E JOGAR" — E ISSO E ESTRUTURAL, NAO PROMESSA
═══════════════════════════════════════════════════════════════════════════

RF-DES-035: o servidor **re-executa os lances recebidos** conferindo legalidade e
objetivo. ⛔ Nao roda busca, nao chama a CNN e nao decide lance nenhum — os
lances da CPU vem no log e sao apenas **conferidos**.

E a separacao de papeis de T004 que torna isso impossivel de burlar: quem este
modulo chama e `motores.juiz.julgar_desafio`, que so tem acesso ao **arbitro**.
⛔ Nao ha caminho daqui ate `escolher_lance` — nao por disciplina, por
importacao.

═══════════════════════════════════════════════════════════════════════════
⚠️ RODA EM LOTE, FORA DO CAMINHO DA REQUISICAO (RF-DES-036)
═══════════════════════════════════════════════════════════════════════════

O aplicativo **ja mostrou o resultado e nao espera resposta**. Esta auditoria e
tardia de proposito: rodar dentro do `POST` obrigaria a pessoa a esperar a
reproducao da partida inteira para ver a tela que ela ja viu.

═══════════════════════════════════════════════════════════════════════════
⛔ DIVERGENCIA E ALERTA, NUNCA CORRECAO
═══════════════════════════════════════════════════════════════════════════

**Vale o aplicativo** (RF-DES-032, D-05). Este modulo escreve `co_auditoria` e
`de_auditoria`, e ⛔ **nao toca em `nu_xp`, nao apaga resolucao e nao tira
ninguem do quadro**.

⚠️ O motivo e concreto: um recalculo pode ter bug proprio, e punir com base nele
tiraria XP de gente honesta na primeira versao errada do arbitro. Quem viu
*"resolvido!"* e depois nao se encontra no quadro nao conclui "fui pego"; conclui
"esse aplicativo e bugado".

═══════════════════════════════════════════════════════════════════════════
⚠️ SEM ESTE ARQUIVO, `co_auditoria` FICA EM `'pendente'` PARA SEMPRE
═══════════════════════════════════════════════════════════════════════════

A coluna tem `DEFAULT 'pendente'`, entao **nada da erro** — e a secao de
divergencias do painel (T040) abre vazia para sempre. E por isso que aquela tela
mostra os **tres** contadores: `divergente = 0` com `pendente` alto significa
*"ninguem conferiu"*, e nao *"esta tudo certo"*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from api.desafios.modelos_evento import TB_RESOLUCAO, VW_DESAFIO_DIA, VW_RESOLUCAO
from api.desafios.modelos_producao import VW_DESAFIO
# O `CASE` que devolve a letra ao lance do Quatro. ⚠️ `quadro` so depende de
# SQLAlchemy e dos modelos de desafio (nada de `fastapi`), e por isso cabe na
# imagem enxuta do job (`requirements_job.txt`).
from api.desafios.quadro import LETRA_DO_LANCE_QUATRO_SQL
from motores.juiz import JogoDesconhecido, julgar_desafio
from motores.nucleo.chegada import ChegadaInvalida
from motores.nucleo.medidor_por_fita import CUMPRIU, DADO_INVALIDO

#: Os tres estados de `desafio_dia.tb003_resolucao.co_auditoria`.
PENDENTE = "pendente"
CONFERE = "confere"
DIVERGENTE = "divergente"

#: Quantas resolucoes uma execucao audita.
#:
#: ⚠️ **Ha limite porque reproduzir uma fita custa CPU**, e o job divide a maquina
#: com a geracao dos candidatos. Uma fila que cresceu durante uma queda e drenada
#: em varias execucoes, e nao numa que trava o container.
LOTE_PADRAO = 200

#: O quanto o `Q` do servidor pode diferir do que o aplicativo mandou sem virar
#: divergencia.
#:
#: ⚠️ **Nao e frouxidao: e aritmetica.** O aplicativo calcula em `double` de Dart
#: e o servidor em `Decimal`; as duas contas passam por divisoes e chegam a
#: numeros que diferem na quinta casa. Sem tolerancia, **toda** resolucao seria
#: divergente — e o alerta que dispara sempre e um alerta que ninguem le.
TOLERANCIA_Q = 0.01


class AuditoriaImpossivel(RuntimeError):
    """A resolucao nao pode ser auditada por defeito do **desafio**.

    ⚠️ E diferente de divergencia: aqui nao ha o que comparar. Chegada malformada
    ou jogo sem medidor sao defeitos do que foi publicado, e nao da partida de
    quem jogou — marcar a pessoa como divergente seria acusa-la do erro de outro.
    """


@dataclass(frozen=True, slots=True)
class Veredito:
    """O que a auditoria concluiu sobre uma resolucao.

    Atributos:
        co_auditoria: `confere` · `divergente`. ⚠️ **Nunca `pendente`** — este
            objeto so existe porque a auditoria rodou.
        de_auditoria: o diagnostico, quando divergiu. ⛔ Texto interno: ele vai
            para o painel do dono, e **nunca** para a tela de ninguem — o banco
            nao fala tres idiomas.
    """

    co_auditoria: str
    de_auditoria: Optional[str] = None

    @property
    def divergiu(self) -> bool:
        """Atalho legivel para o caso que gera alerta."""
        return self.co_auditoria == DIVERGENTE


#: As resolucoes ainda nao auditadas, com tudo o que a reproducao precisa.
#:
#: ⚠️ **Uma consulta so traz o desafio junto**, e nao uma por resolucao: auditar
#: duzentas linhas com um `SELECT` de desafio para cada uma seria o padrao N+1
#: numa rotina que ja e a mais cara do job.
#:
#: ⚠️ `ORDER BY dh_resolucao` faz a fila ser drenada na ordem em que chegou — o
#: que importa quando um lote nao da conta de tudo: as mais antigas sao as que ja
#: esperaram mais.
SQL_PENDENTES = f"""
SELECT r.id_resolucao,
       r.id_desafio_dia,
       r.id_usuario,
       r.id_tentativa,
       r.id_partida,
       r.nu_lance_cumpre_desafio,
       r.nu_xp,
       d.id_desafio,
       d.co_jogo,
       d.co_modalidade,
       d.js_posicao_inicial,
       d.js_chegada
  FROM {VW_RESOLUCAO} r
  JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio_dia = r.id_desafio_dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE r.co_auditoria = '{PENDENTE}'
 ORDER BY r.dh_resolucao ASC
 LIMIT :limite
"""

#: A fita: os lances da partida, no vocabulario do log.
#:
#: ⚠️ **`co_aresta` no Pontinhos e `co_lance` nas damas**, e o `COALESCE` os une
#: numa coluna so — o medidor de cada jogo sabe ler o proprio. Os `LEFT JOIN` sao
#: obrigatorios: uma jogada sem extensao e uma jogada de um jogo que este `SELECT`
#: nao conhece, e ela precisa chegar como `NULL` para o julgamento acusar dado
#: invalido, em vez de sumir da fita.
#:
#: ⚠️ **O Quatro em Linha nao guarda o lance escrito** (`s4`): guarda o tipo por
#: extenso e a coluna, em duas colunas, e e o `CASE` do quadro
#: (`LETRA_DO_LANCE_QUATRO_SQL`) que as junta de volta (`'s' || 4` = `s4`). O
#: `||` do Postgres converte o inteiro em texto, e com a letra `NULL` (tipo
#: `desconhecido`) o resultado inteiro e `NULL` — nunca um `4` sem tipo.
#:
#: ⛔ **Ate 11/11/2026 o Quatro faltava aqui**, e cada lance dele chegava `NULL`.
#: A primeira resolucao de Desafio do Dia do Quatro que entrou na fila derrubou
#: o job inteiro, todo dia, em `des` e `prd` (`TypeError` no `_ler_lance`),
#: e nenhuma resolucao — de jogo nenhum — foi auditada depois dela. A consulta
#: irma, `SQL_LANCES` do replay, ja o conhecia desde a T153; por isso o `CASE`
#: agora e importado de la, e nao copiado.
#:
#: ⛔ **`ORDER BY nu_ordem` e a fita.** `nu_ordem` e sequencia continua de
#: eventos: nunca recua e nunca se repete. Ordenar por `dh_jogada` daria a mesma
#: coisa quase sempre — e o "quase" seriam duas jogadas no mesmo milissegundo.
SQL_FITA = f"""
SELECT j.nu_ordem,
       j.nu_jogador,
       COALESCE(
           p.co_aresta,
           dm.co_lance,
           ({LETRA_DO_LANCE_QUATRO_SQL}) || q.nu_coluna
       ) AS co_lance
  FROM partida.tb002_jogada j
  LEFT JOIN jogo_pontinhos.tb002_jogada p ON p.id_jogada = j.id_jogada
  LEFT JOIN jogo_damas.tb002_jogada dm    ON dm.id_jogada = j.id_jogada
  -- A VIEW, e nao a tabela: e ela que traz o tipo por extenso (`soltar`), que
  -- o `CASE` traduz na letra. A tabela so tem o numero da dimensao.
  LEFT JOIN jogo_quatro.vw002_jogada q    ON q.id_jogada = j.id_jogada
 WHERE j.id_partida = :id_partida
 ORDER BY j.nu_ordem ASC
"""

#: Marca a resolucao. ⛔ **So `co_auditoria` e `de_auditoria`** — nenhuma outra
#: coluna aparece neste `UPDATE`, e essa ausencia e o requisito.
#:
#: ⚠️ `WHERE co_auditoria = 'pendente'` deixa a rotina segura contra duas
#: execucoes simultaneas: a segunda nao reescreve o que a primeira ja concluiu.
SQL_MARCAR = f"""
UPDATE {TB_RESOLUCAO}
   SET co_auditoria = :co_auditoria,
       de_auditoria = :de_auditoria
 WHERE id_resolucao = :id_resolucao
   AND co_auditoria = '{PENDENTE}'
RETURNING id_resolucao
"""


def fita_do_log(linhas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Converte as jogadas do log no vocabulario que o juiz espera.

    Args:
        linhas: o que `SQL_FITA` devolveu.

    Returns:
        `[{"n", "jogador", "lance"}, ...]`.

    ⚠️ **`nu_jogador` e 1/2 e `jogador` e +1/-1.** Sao convencoes diferentes **de
    proposito** (o generico usa o numero, a extensao usa o sinal), e o `CHECK` da
    migracao `0012` impede que uma vire a outra por descuido. A traducao acontece
    aqui, uma vez.
    """
    return [
        {
            "n": linha["nu_ordem"],
            "jogador": 1 if linha["nu_jogador"] == 1 else -1,
            "lance": linha["co_lance"],
        }
        for linha in linhas
    ]


def jogador_do_desafio(js_posicao_inicial: Mapping[str, Any]) -> int:
    """De quem e o desafio: o `vez_de` da posicao publicada, `+1` ou `-1`.

    ⚠️ **E o mesmo numero com que o gerador julga** (`job/gerador.py`:
    `jogador=js_posicao["vez_de"]`) e com que o app julga
    (`jogadorDaPosicaoPublicada`, em `lib/core/desafios/desafio.dart`). A
    auditoria passava `+1` fixo ate 11/11/2026: dava certo nas damas e no
    Pontinhos, em que todo desafio publicado abre com o `+1`, e errado no Quatro,
    em que a vez e do `-1` sempre que a posicao publicada tem um numero IMPAR de
    lances.

    ⚠️ **Sem o campo, `+1`**: a posicao das damas e so a FEN (a vez vem no prefixo
    dela, e o medidor a le de la). Valor fora de `+1`/`-1` tambem cai no `+1`,
    como no app: quem recusa desafio malformado e a geracao, e nao esta leitura.
    """
    vez = js_posicao_inicial.get("vez_de")
    # `isinstance(..., (int, float))`: o JSON pode trazer `-1` ou `-1.0`.
    return -1 if isinstance(vez, (int, float)) and int(vez) == -1 else 1


def fita_nos_sinais_do_motor_quatro(
    fita: Sequence[Mapping[str, Any]], *, jogador: int
) -> list[dict[str, Any]]:
    """Traduz a fita do Quatro das CORES DO APP para os SINAIS DO MOTOR.

    Args:
        fita: a fita de `fita_do_log`, com `jogador` nas cores do app (`+1` = o
            Jogador 1, que no desafio e sempre a pessoa).
        jogador: o `vez_de` da posicao publicada — o sinal da pessoa no motor.

    Returns:
        A mesma fita, com cada `jogador` no sinal do motor.

    ⚠️ **Duas convencoes, e as duas estao certas no lugar delas.** O motor chama
    de `+1` quem fez o 1o lance da sequencia INTEIRA (a posicao publicada
    incluida); o log grava `nu_jogador` nas cores do app, e no app a pessoa e
    sempre o Jogador 1 (`estado_partida_quatro.dart`, "quem abriu sai da
    sequencia"). Entao, quando a posicao publicada tem um numero impar de lances,
    a pessoa e o `-1` do motor e o personagem e o `+1`: o sinal do motor e o do
    app multiplicado pelo `vez_de`. Com `vez_de = +1` nada muda.

    ⛔ **So no Quatro.** No Pontinhos, quando a vez e do `-1`, o app poe a pessoa
    como Jogador 2 (`partida_screen.dart` do Pontinhos), e o log ja sai no sinal
    do jogo; multiplicar la inverteria uma fita que esta certa.
    """
    return [{**lance, "jogador": lance["jogador"] * jogador} for lance in fita]


def auditar(
    *,
    linha: Mapping[str, Any],
    fita: Sequence[Mapping[str, Any]],
) -> Veredito:
    """Re-executa a fita e diz se a resolucao confere.

    Args:
        linha: a resolucao com o desafio junto (uma linha de `SQL_PENDENTES`).
        fita: os lances, como `fita_do_log` os entrega (`jogador` nas cores do
            app). ⚠️ No Quatro, a traducao para os sinais do motor e feita aqui
            (`fita_nos_sinais_do_motor_quatro`).

    Returns:
        O veredito, `confere` ou `divergente`.

    Raises:
        AuditoriaImpossivel: defeito do **desafio** (chegada malformada, jogo sem
            medidor). ⚠️ Nao vira divergencia: seria acusar a pessoa do erro de
            outro.

    ⚠️ **Tres coisas sao comparadas, e nenhuma delas e o gabarito.** O arbitro
    julga o **objetivo**: um caminho diferente da solucao de referencia que cumpra
    o objetivo cumpriu o objetivo. O gabarito serve para ensinar depois.
    """
    if not fita:
        # ⚠️ **Fita vazia nao e "nao cumpriu": e resolucao sem lance nenhum.** Ou
        # a partida chegou sem jogadas, ou o `id_partida` aponta para o lugar
        # errado — e os dois sao divergencia de dado, nao de julgamento.
        return Veredito(
            DIVERGENTE,
            "a partida da resolucao nao tem nenhuma jogada no log",
        )

    # De quem e o desafio, e a fita nos sinais em que o juiz a le.
    jogador = jogador_do_desafio(linha["js_posicao_inicial"])
    if linha["co_jogo"] == "quatro":
        fita = fita_nos_sinais_do_motor_quatro(fita, jogador=jogador)

    try:
        julgamento = julgar_desafio(
            co_jogo=linha["co_jogo"],
            js_posicao_inicial=linha["js_posicao_inicial"],
            js_chegada=linha["js_chegada"],
            fita=fita,
            jogador=jogador,
            co_modalidade=linha["co_modalidade"] or "brasileira",
        )
    except ChegadaInvalida as erro:
        raise AuditoriaImpossivel(
            f"a linha de chegada do desafio {linha['id_desafio']} esta "
            f"malformada: {erro}. ⛔ Isto e defeito do desafio publicado, e nao "
            "da partida de quem jogou."
        ) from erro
    except JogoDesconhecido as erro:
        raise AuditoriaImpossivel(str(erro)) from erro

    if julgamento.veredito == DADO_INVALIDO:
        # ⛔ **Lance ilegal e DADO INVALIDO, nunca "nao cumpriu"** (D-05). Uma
        # sincronizacao com defeito, um aplicativo adulterado ou um bug de
        # gravacao produzem fita irreproduzivel — e tratar isso como tentativa
        # fracassada esconderia o defeito atras de derrotas legitimas.
        return Veredito(
            DIVERGENTE, f"fita irreproduzivel: {julgamento.de_motivo}"
        )

    if julgamento.veredito != CUMPRIU:
        return Veredito(
            DIVERGENTE,
            "o arbitro reproduziu a fita e o objetivo NAO caiu dentro da "
            "janela. ⛔ O XP nao foi mexido: vale o aplicativo (RF-DES-032).",
        )

    # ⚠️ O lance em que o objetivo caiu tambem se confere. Ele e a coluna que o
    # Raio-X usa para abrir o replay no ponto certo; errado, o replay abre num
    # lance qualquer — e ninguem notaria, porque a tela funcionaria.
    esperado = linha["nu_lance_cumpre_desafio"]
    if julgamento.nu_lance_cumpre_desafio != esperado:
        return Veredito(
            DIVERGENTE,
            f"o objetivo caiu no lance {julgamento.nu_lance_cumpre_desafio} "
            f"para o arbitro, e a resolucao diz {esperado}.",
        )

    return Veredito(CONFERE)


async def auditar_lote(sessao: Any, *, limite: int = LOTE_PADRAO) -> dict[str, int]:
    """Audita as resolucoes pendentes e marca cada uma.

    Args:
        sessao: uma `AsyncSession` (ou duble com `execute`/`commit`).
        limite: quantas resolucoes desta execucao.

    Returns:
        `{"conferem": n, "divergentes": n, "impossiveis": n}` — ⚠️ os tres
        numeros, e nao so o total: "auditei 200" nao diz nada, e e justamente a
        contagem de divergentes que precisa aparecer no log do Railway.

    ⚠️ **Uma resolucao que estoura NAO derruba o lote.** A auditoria e a rotina
    mais exposta a dado torto do projeto — ela le o que chegou de milhoes de
    aparelhos —, e um `raise` no meio deixaria as 199 seguintes pendentes por
    causa de uma.
    """
    from sqlalchemy import text

    resultado = await sessao.execute(text(SQL_PENDENTES), {"limite": limite})
    pendentes = [dict(m) for m in resultado.mappings().all()]

    contagem = {"conferem": 0, "divergentes": 0, "impossiveis": 0}

    for linha in pendentes:
        jogadas = await sessao.execute(
            text(SQL_FITA), {"id_partida": linha["id_partida"]}
        )
        fita = fita_do_log([dict(m) for m in jogadas.mappings().all()])

        try:
            veredito = auditar(linha=linha, fita=fita)
        except AuditoriaImpossivel as erro:
            # ⚠️ **Fica `pendente` de proposito.** O defeito e do desafio, e ele
            # pode ser consertado; marcar como divergente acusaria a pessoa e
            # ainda apagaria o rastro de que ha um desafio publicado quebrado.
            contagem["impossiveis"] += 1
            _avisar(linha, erro)
            continue
        except Exception as erro:  # noqa: BLE001 - e exatamente o que se quer pegar
            # ⛔ **Um estouro que ninguem previu tambem nao derruba o lote.** Ate
            # 11/11/2026 so o `AuditoriaImpossivel` era pego aqui, e um
            # `TypeError` do Quatro (lance `NULL` na fita) derrubou o job inteiro
            # todo dia: a promessa da docstring valia so para o erro esperado.
            #
            # ⚠️ Conta como **impossivel** e fica `pendente`, pelo mesmo motivo
            # do bloco de cima: o defeito e NOSSO (codigo da auditoria), e nao
            # da pessoa. Consertado o codigo, a proxima execucao a audita. O
            # rastro de pilha vai inteiro para o log: sem ele, "impossivel"
            # esconderia o lugar do defeito.
            contagem["impossiveis"] += 1
            _avisar(linha, erro, inesperado=True)
            continue

        await sessao.execute(
            text(SQL_MARCAR),
            {
                "id_resolucao": linha["id_resolucao"],
                "co_auditoria": veredito.co_auditoria,
                "de_auditoria": veredito.de_auditoria,
            },
        )
        contagem["divergentes" if veredito.divergiu else "conferem"] += 1

    await sessao.commit()
    return contagem


def _avisar(
    linha: Mapping[str, Any], erro: Exception, *, inesperado: bool = False
) -> None:
    """Registra um desafio publicado que a auditoria nao consegue reproduzir.

    Args:
        linha: a resolucao que ficou pendente.
        erro: o que estourou.
        inesperado: `True` quando o erro NAO e um `AuditoriaImpossivel` — um
            defeito do codigo da auditoria, e nao do desafio. Ai o aviso diz o
            tipo do erro, a resolucao e a partida, e imprime o rastro de pilha:
            e o que permite achar o defeito sem reproduzir o job.

    ⚠️ Vai para a saida de erro, que e onde o Railway destaca as linhas do log —
    e nao para o painel, porque o painel mostra divergencias **de julgamento**, e
    isto e outra coisa: um desafio quebrado no ar.
    """
    import sys
    import traceback

    if not inesperado:
        print(
            f"[auditoria] ⛔ desafio {linha.get('id_desafio')} nao e auditavel: "
            f"{erro}",
            file=sys.stderr,
        )
        return

    print(
        f"[auditoria] ⛔ erro inesperado ao auditar a resolucao "
        f"{linha.get('id_resolucao')} (jogo {linha.get('co_jogo')}, partida "
        f"{linha.get('id_partida')}): {type(erro).__name__}: {erro}. "
        "Fica PENDENTE; o lote seguiu.",
        file=sys.stderr,
    )
    # `print_exception` recebe o erro ja capturado (fora do `except`, o
    # `print_exc` nao teria o que imprimir).
    traceback.print_exception(erro, file=sys.stderr)
