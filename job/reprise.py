"""A REPRISE — uma COPIA, e nunca o mesmo desafio de novo (RF-DES-029/152, T041).

═══════════════════════════════════════════════════════════════════════════
O QUE ELA E, E O QUE ELA NAO E
═══════════════════════════════════════════════════════════════════════════

E **fallback de operacao**: quando a fila de aprovados acaba, o servidor publica
um desafio antigo bem avaliado como o desafio de **hoje**, para toda a base —
mesma data, mesmo quadro, mesma pontuacao, com um rotulo dizendo que e reprise.

⛔ **Nao e segunda chance de ninguem.** Nao tem relacao com o desafio que uma
pessoa especifica perdeu: passado perdido e perdido (RF-DES-006). O dono
confirmou o requisito em 03/09/2026 **depois** de ter entendido justamente o
contrario — *"eu tinha imaginado que era o usuario refazendo um desafio que tinha
perdido"* —, e por isso a primeira linha do requisito diz o que ele nao e.

⛔ **E nunca um candidato nao revisado** (RF-DES-012d). Um dia repetido e um
aborrecimento; um desafio impossivel no ar e uma sessao perdida e um usuario a
menos.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE COPIA, E NAO UM ESTADO `reprise` NO DESAFIO ORIGINAL
═══════════════════════════════════════════════════════════════════════════

Foi precisado pelo dono em 04/09/2026, e e a regra que mantem **todo o resto**
simples. Se o mesmo desafio fosse publicado duas vezes:

  · `un002_desafio UNIQUE (id_desafio)` teria de cair, e o vinculo dia↔desafio
    deixaria de ser 1:1;
  · `un001_resolucao UNIQUE (id_desafio_dia, id_usuario)` continuaria valendo,
    mas o **quadro** da reprise nasceria misturado com o do dia original —
    pessoas de meses atras aparecendo no quadro de hoje;
  · o teto de duas dicas, que e **por desafio** (RF-DES-057), passaria a somar as
    dicas de duas datas.

Com a copia, nada disso acontece: identificador novo, quadro limpo, contadores
zerados. O preco e uma linha duplicada em `tb001_desafio` — barato.

═══════════════════════════════════════════════════════════════════════════
⚠️ A ESCOLHA PREFERE QUEM TEVE MENOS PARTICIPACAO
═══════════════════════════════════════════════════════════════════════════

RF-DES-029, textual: *"para que caia sobre o menor numero possivel de gente que
ja a jogou"*. E o unico criterio de desempate que reduz o incomodo real da
reprise — repetir o desafio mais popular do mes seria repetir para todo mundo.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE NAO SE COPIA
═══════════════════════════════════════════════════════════════════════════

`co_curadoria` volta a `'aprovado'` (a copia ja nasce revisada, porque a origem
foi), e `de_motivo_descarte` fica `NULL`. O que **nunca** se copia e o
`id_desafio` — e a razao de a reprise existir como copia — nem o `dh_geracao`,
que e o instante em que **esta** linha nasceu.

⚠️ **Reprise de reprise nao acontece.** A origem apontada e sempre a **linha
original**: se a escolhida ja for uma reprise, o ponteiro segue para a origem
dela. Sem isso, uma cadeia de copias apontando umas para as outras tornaria
impossivel responder *"quantas vezes este desafio ja foi ao ar"* com uma consulta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Optional
from uuid import UUID

from api.desafios.modelos_evento import VW_DESAFIO_DIA, VW_TENTATIVA
from api.desafios.modelos_producao import VW_DESAFIO

#: Quantos dias precisam ter passado desde a publicacao original.
#:
#: ⚠️ Nao e conforto: e o intervalo abaixo do qual a reprise seria percebida como
#: defeito. Repetir o desafio da semana passada parece o job travado; repetir o
#: de tres meses atras parece o que e — um fallback raro.
DIAS_MINIMOS_DESDE_A_ORIGEM = 60


class RepriseImpossivel(RuntimeError):
    """Nao ha desafio elegivel para reprise.

    ⚠️ **E o pior caso operacional da spec** (secao de casos-limite): a fila
    acabou **e** nao ha reprise. Ele tem excecao propria — e nao um `None`
    devolvido calado — porque quem o recebe precisa fazer barulho: e o dia em que
    o aplicativo abre sem desafio.
    """


@dataclass(frozen=True, slots=True)
class CandidataAReprise:
    """Um desafio antigo que pode voltar ao ar.

    Atributos:
        id_desafio: o desafio a copiar.
        id_origem: a **linha original**, que a copia vai apontar. Igual a
            `id_desafio` quando ela propria e o original.
        dt_dia_original: quando foi ao ar da primeira vez.
        qt_tentativas: quanta gente ja passou por ele — o criterio de escolha.
        qt_resolucoes: quantas resolveram. E o "bem avaliado" de RF-DES-012d.
    """

    id_desafio: UUID
    id_origem: UUID
    dt_dia_original: date
    qt_tentativas: int
    qt_resolucoes: int

    @property
    def taxa_de_resolucao(self) -> float:
        """A fracao de quem tentou e resolveu.

        ⚠️ Sem tentativa nenhuma a taxa e `0.0`, e isso e **correto para a
        decisao**: um desafio que ninguem tentou nao tem prova de ser bom, e
        reprisa-lo seria estrear um desconhecido com rotulo de reprise.
        """
        return self.qt_resolucoes / self.qt_tentativas if self.qt_tentativas else 0.0


#: Piso de resolucao para um desafio ser considerado "bem avaliado".
#:
#: ⚠️ **E o alvo de RF-DES-014 (≥70% entre humanos que tentam)**, e nao um numero
#: novo. Um desafio que ficou muito abaixo dele quando estreou nao melhorou
#: sozinho — reprisa-lo seria repetir de proposito o dia que deu errado.
TAXA_MINIMA_PARA_REPRISAR = 0.70

#: Quantas tentativas sao precisas para a taxa significar alguma coisa.
#:
#: ⚠️ Mesmo numero de RF-DES-063 (a fracao escondida abaixo de 20 tentativas), e
#: pelo mesmo motivo: "2 de 3 resolveram" nao e uma medida, e um desafio julgado
#: por tres pessoas seria escolhido pelo acaso.
TENTATIVAS_MINIMAS_PARA_JULGAR = 20


#: As candidatas a reprise, ja ordenadas pela preferencia de RF-DES-029.
#:
#: ⚠️ **`COALESCE(d.id_desafio_origem, d.id_desafio)`** e o que impede a cadeia de
#: copias: se a escolhida ja for uma reprise, a nova aponta para a origem dela, e
#: nao para ela. Assim *"quantas vezes este desafio foi ao ar"* continua sendo uma
#: consulta, e nao uma travessia recursiva.
#:
#: ⛔ `co_curadoria = 'aprovado'` nao e redundante com "ja foi publicado": um
#: desafio pode ter sido descartado **depois** de ir ao ar, e e exatamente esse
#: que nao pode voltar.
SQL_CANDIDATAS = f"""
SELECT d.id_desafio,
       COALESCE(d.id_desafio_origem, d.id_desafio) AS id_origem,
       dia.dt_dia                                  AS dt_dia_original,
       COALESCE(t.qt_tentativas, 0)                AS qt_tentativas,
       COALESCE(t.qt_resolucoes, 0)                AS qt_resolucoes
  FROM {VW_DESAFIO} d
  JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio = d.id_desafio
  LEFT JOIN (
        SELECT id_desafio_dia,
               COUNT(*)                                AS qt_tentativas,
               COUNT(*) FILTER (WHERE ic_resolveu)     AS qt_resolucoes
          FROM {VW_TENTATIVA}
         GROUP BY id_desafio_dia
       ) t
    ON t.id_desafio_dia = dia.id_desafio_dia
 WHERE d.co_curadoria = 'aprovado'
   AND dia.dt_dia <= :dt_limite
 ORDER BY COALESCE(t.qt_tentativas, 0) ASC,
          dia.dt_dia ASC
 LIMIT :limite
"""


def elegivel(candidata: CandidataAReprise) -> bool:
    """Esta candidata pode voltar ao ar?

    Args:
        candidata: a linha lida do banco.

    Returns:
        `True` quando ela e **comprovadamente** boa.

    ⚠️ **Sem prova nao passa.** Tentativas de menos e taxa de menos reprovam pelo
    mesmo motivo de fundo: reprise so se justifica quando o desafio ja mostrou
    que funciona, e um desconhecido com rotulo de reprise e o pior dos dois
    mundos — nem novidade, nem garantia.
    """
    if candidata.qt_tentativas < TENTATIVAS_MINIMAS_PARA_JULGAR:
        return False
    return candidata.taxa_de_resolucao >= TAXA_MINIMA_PARA_REPRISAR


def escolher(
    candidatas: list[CandidataAReprise], *, dt_hoje: date
) -> CandidataAReprise:
    """A reprise a publicar hoje.

    Args:
        candidatas: as linhas lidas por `SQL_CANDIDATAS`, na ordem em que vieram.
        dt_hoje: o dia corrente em UTC.

    Returns:
        A escolhida — **a de menor participacao anterior** entre as elegiveis.

    Raises:
        RepriseImpossivel: quando nenhuma passa nos filtros.

    ⚠️ A ordem ja vem do banco; esta funcao **filtra** e pega a primeira. Reordenar
    aqui criaria uma segunda regra de preferencia, e as duas divergiriam no dia em
    que uma delas mudasse.
    """
    limite = _limite_de_antiguidade(dt_hoje)
    aptas = [
        c for c in candidatas if elegivel(c) and c.dt_dia_original <= limite
    ]
    if not aptas:
        raise RepriseImpossivel(
            f"nenhum desafio elegivel para reprise em {dt_hoje}. "
            f"⛔ Este e o pior caso operacional: a fila de aprovados acabou E "
            f"nao ha reprise. Foram avaliadas {len(candidatas)} candidata(s); "
            f"os filtros sao ≥{TENTATIVAS_MINIMAS_PARA_JULGAR} tentativas, "
            f"taxa ≥{TAXA_MINIMA_PARA_REPRISAR:.0%} e publicacao ate {limite}."
        )
    return aptas[0]


def _limite_de_antiguidade(dt_hoje: date) -> date:
    """A data mais recente que uma origem pode ter."""
    return dt_hoje - timedelta(days=DIAS_MINIMOS_DESDE_A_ORIGEM)


#: A copia. ⚠️ **`INSERT ... SELECT`**, e nao ler em Python e reescrever campo a
#: campo: uma coluna nova em `tb001_desafio` entraria na tabela e **ficaria de
#: fora da copia** sem que nada acusasse — a reprise sairia com um campo `NULL`
#: que ninguem procuraria.
#:
#: As unicas colunas que a copia **nao** herda estao escritas aqui, e cada uma
#: com o seu motivo:
#:
#:   · `id_desafio`  → identificador proprio; e a razao de a reprise ser copia;
#:   · `dh_geracao`  → o instante em que **esta** linha nasceu (o `DEFAULT now()`);
#:   · `co_curadoria`→ `'aprovado'`: a copia nasce revisada porque a origem foi;
#:   · `de_motivo_descarte` → `NULL`, e o `ck004_motivo` exige que seja;
#:   · `id_desafio_origem` e `ic_reprise` → o que faz dela uma reprise.
SQL_COPIAR = """
INSERT INTO desafio.tb001_desafio (
        co_jogo, co_modalidade, co_variante,
        co_formato_posicao, js_posicao_inicial,
        nu_tipo_desafio, js_chegada, ic_chegada_encerra_partida,
        co_chave_objetivo, js_objetivo,
        co_personagem, nu_semente,
        js_solucao, nu_lances_solucao,
        nu_tempo_piso_ms, nu_tempo_teto_ms,
        nu_versao_catalogo,
        co_versao_minima, co_versao_perfil, co_versao_motor, nu_teto_log,
        co_curadoria, de_motivo_descarte,
        id_desafio_origem, ic_reprise)
SELECT co_jogo, co_modalidade, co_variante,
       co_formato_posicao, js_posicao_inicial,
       nu_tipo_desafio, js_chegada, ic_chegada_encerra_partida,
       co_chave_objetivo, js_objetivo,
       co_personagem, nu_semente,
       js_solucao, nu_lances_solucao,
       nu_tempo_piso_ms, nu_tempo_teto_ms,
       nu_versao_catalogo,
       co_versao_minima, co_versao_perfil, co_versao_motor, nu_teto_log,
       'aprovado', NULL,
       :id_origem, TRUE
  FROM desafio.tb001_desafio
 WHERE id_desafio = :id_desafio
RETURNING id_desafio
"""

#: Os feitos de saida tambem sao copiados — sem eles a reprise nao teria como
#: pagar XP, e `tb003_feito_desafio` e `NOT NULL` do lado do desafio.
#:
#: ⚠️ **Sem isto a reprise iria ao ar e pagaria so o piso de 18 XP.** Nada daria
#: erro: o `INSERT` do desafio passaria, o aplicativo baixaria a linha, e a
#: diferenca so apareceria no extrato de quem jogou — que ninguem confere.
SQL_COPIAR_FEITOS = """
INSERT INTO desafio.tb003_feito_desafio
       (id_desafio, nu_feito, nu_ordem, vr_peso,
        co_normalizacao, vr_min, vr_max, co_sobre)
SELECT :id_copia, nu_feito, nu_ordem, vr_peso,
       co_normalizacao, vr_min, vr_max, co_sobre
  FROM desafio.tb003_feito_desafio
 WHERE id_desafio = :id_desafio
"""


def linha_para_copia(linha: Mapping[str, Any]) -> CandidataAReprise:
    """Converte uma linha de `SQL_CANDIDATAS` no dataclass."""
    return CandidataAReprise(
        id_desafio=linha["id_desafio"],
        id_origem=linha["id_origem"],
        dt_dia_original=linha["dt_dia_original"],
        qt_tentativas=int(linha["qt_tentativas"]),
        qt_resolucoes=int(linha["qt_resolucoes"]),
    )


async def publicar_reprise(sessao: Any, *, dt_dia: date) -> Optional[UUID]:
    """Copia o melhor desafio antigo e o publica como o desafio de `dt_dia`.

    Args:
        sessao: uma `AsyncSession` (ou duble com `execute`/`commit`).
        dt_dia: o dia a cobrir.

    Returns:
        O `id_desafio` da **copia**.

    Raises:
        RepriseImpossivel: quando nao ha candidata elegivel.

    ⚠️ **A ordem das tres escritas nao e negociavel**: copia o desafio, copia os
    feitos dele e so entao publica o dia. Publicar antes de copiar os feitos
    deixaria uma janela em que o aplicativo poderia baixar um desafio que paga
    so o piso — e a janela seria curta, intermitente e impossivel de reproduzir.
    """
    from sqlalchemy import text

    from job.gravacao import SQL_PUBLICAR_O_DIA
    from api.desafios.modelos_evento import encerramento_do_dia

    resultado = await sessao.execute(
        text(SQL_CANDIDATAS),
        {"dt_limite": _limite_de_antiguidade(dt_dia), "limite": 200},
    )
    candidatas = [linha_para_copia(m) for m in resultado.mappings().all()]
    escolhida = escolher(candidatas, dt_hoje=dt_dia)

    copia = await sessao.execute(
        text(SQL_COPIAR),
        {"id_desafio": escolhida.id_desafio, "id_origem": escolhida.id_origem},
    )
    nova = copia.first()
    if nova is None:
        raise RepriseImpossivel(
            f"a copia do desafio {escolhida.id_desafio} nao gravou nada"
        )
    id_copia = nova["id_desafio"] if isinstance(nova, Mapping) else nova[0]

    await sessao.execute(
        text(SQL_COPIAR_FEITOS),
        {"id_copia": id_copia, "id_desafio": escolhida.id_desafio},
    )
    await sessao.execute(
        text(SQL_PUBLICAR_O_DIA),
        {
            "dt_dia": dt_dia,
            "id_desafio": id_copia,
            "dh_encerramento": encerramento_do_dia(dt_dia),
        },
    )
    await sessao.commit()
    return id_copia
