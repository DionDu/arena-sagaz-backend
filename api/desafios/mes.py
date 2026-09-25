"""O RESUMO DO MES — a fita, o calendario e os dias que ja passaram (T072a).

`GET /v1/desafios/meu-mes` — `contracts/resumo-do-mes.md`.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ISTO E DO SERVIDOR, E NAO UM REGISTRO NO APARELHO
═══════════════════════════════════════════════════════════════════════════

RF-DES-114: o historico fica **indefinidamente**, e nada e apagado
(RF-DES-038). O que mora em `shared_preferences` some numa reinstalacao — e o
sintoma seria o pior possivel: a pessoa que joga ha tres meses trocaria de
aparelho e veria um mes vazio, com a fita e o calendario dizendo que ela nunca
jogou.

⚠️ **O contador de tentativas do aplicativo NAO serve**, e ele diz isso no
proprio arquivo: ele guarda **um** dia, o corrente, de proposito. E o cache de
desafios so tem hoje e os proximos.

═══════════════════════════════════════════════════════════════════════════
⚠️ O MES ZERA, E ISSO E REGRA DE PRODUTO (RF-DES-067)
═══════════════════════════════════════════════════════════════════════════

O resumo e do **mes corrente**, e todo mundo recomeca junto no dia 1. ⛔ Nao ha
acumulado de todos os tempos aqui: esse ja tem dono (RF-DES-068), o ranking
geral por XP, que existe e nao muda.

⚠️ **E nao ha parametro de mes.** A tela nao navega meses (o desenho do Claude
Design nao tem seta de mes), e um parametro seria superficie publica sem
consumidor — mais um caminho para manter, testar e defender.

═══════════════════════════════════════════════════════════════════════════
⛔ NADA DE AMANHA, NEM AQUI (RF-DES-009)
═══════════════════════════════════════════════════════════════════════════

A fila de aprovados tem dias **futuros** publicados, e eles estao nesta mesma
tabela. A consulta corta em **hoje**: servir um dia que ainda nao chegou daria
ao aplicativo o que ele nao pode mostrar — e a garantia de RF-DES-009 mora na
tela justamente porque o servidor nao consegue impedir uma tela de exibir o que
ja esta no aparelho. Aqui da para nao mandar.

═══════════════════════════════════════════════════════════════════════════
⚠️ ZERO APARECE AQUI, AO CONTRARIO DO QUADRO
═══════════════════════════════════════════════════════════════════════════

RF-DES-064 proibe o zero **no quadro**, e o motivo e especifico: la o numero
conta sobre o **tamanho da base**, e nao sobre a partida. Aqui o zero e sobre a
propria pessoa, e e informacao legitima — *"ainda sem desafios resolvidos neste
mes. Todo mundo recomeca junto no dia 1"*. Quem escolhe a frase e a tela; o
servidor manda o numero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import VW_DESAFIO_DIA, VW_RESOLUCAO

#: A VIEW do desafio publicado — a linha de producao (schema `desafio`).
VW_DESAFIO = "desafio.vw001_desafio"


#: Os dias do mes corrente, com o que houve em cada um **para esta pessoa**.
#:
#: ⚠️ **`LEFT JOIN` na resolucao, e nao `JOIN`**: o dia em que a pessoa nao
#: resolveu precisa vir na lista — e com a forma de "nao resolvido", que e o que
#: o calendario desenha. Um `JOIN` devolveria so os dias bons, e o calendario
#: nasceria sem os outros.
#:
#: ⚠️ **A resolucao e filtrada por `id_usuario` DENTRO do `ON`**, e nao no
#: `WHERE`: no `WHERE` ela viraria um `JOIN` disfarcado, descartando justamente
#: os dias sem resolucao dela — o defeito classico do `LEFT JOIN`, e ele nao da
#: erro nenhum.
#:
#: ⛔ **`co_curadoria = 'aprovado'`** pelo mesmo motivo das outras rotas: so
#: aprovado entra no calendario.
SQL_DIAS_DO_MES = f"""
SELECT dia.dt_dia,
       dia.id_desafio_dia,
       d.id_desafio,
       d.co_jogo,
       d.co_modalidade,
       d.ic_reprise,
       d.co_personagem,
       d.co_chave_objetivo,
       d.js_objetivo,
       (r.id_resolucao IS NOT NULL) AS ic_resolvido
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
  LEFT JOIN {VW_RESOLUCAO} r
    ON r.id_desafio_dia = dia.id_desafio_dia
   AND r.id_usuario = :id_usuario
 WHERE d.co_curadoria = 'aprovado'
   AND dia.dt_dia >= :primeiro_dia
   AND dia.dt_dia <= :dt_hoje
 ORDER BY dia.dt_dia DESC
"""


@dataclass(frozen=True)
class DiaDoMes:
    """Um dia do calendario, ja lido."""

    dt_dia: date
    id_desafio_dia: UUID
    id_desafio: UUID
    co_jogo: str
    co_modalidade: Optional[str]
    ic_reprise: bool
    co_personagem: str
    co_chave_objetivo: str
    js_objetivo: Optional[dict[str, Any]]
    ic_resolvido: bool


class RepositorioMes:
    """Leitura do resumo do mes. ⛔ Nao escreve nada."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def dias(
        self, *, id_usuario: str, primeiro_dia: date, dt_hoje: date
    ) -> list[dict[str, Any]]:
        """Os dias publicados do mes, do mais recente para o mais antigo."""
        resultado = await self.sessao.execute(
            text(SQL_DIAS_DO_MES),
            {
                "id_usuario": id_usuario,
                "primeiro_dia": primeiro_dia,
                "dt_hoje": dt_hoje,
            },
        )
        return [dict(m) for m in resultado.mappings().all()]


def primeiro_dia_do_mes(dt_hoje: date) -> date:
    """O dia 1 do mes de [dt_hoje].

    ⚠️ Funcao com nome porque e **a regra do RF-DES-067** — "zera todo mes" — e
    nao uma conta de calendario qualquer. Trocar isto por "os ultimos 30 dias"
    seria outro produto: ninguem mais recomecaria junto.
    """
    return dt_hoje.replace(day=1)


class ServicoMes:
    """Monta o resumo do mes de uma pessoa."""

    def __init__(self, repo: RepositorioMes) -> None:
        self.repo = repo

    async def montar(self, *, id_usuario: str, dt_hoje: date) -> dict[str, Any]:
        """O corpo de `GET /v1/desafios/meu-mes`.

        Args:
            id_usuario: quem esta perguntando. ⚠️ **Exigido** — o historico e
                pessoal, e nao ha versao publica dele.
            dt_hoje: o dia **UTC** de hoje, no servidor. ⚠️ O desafio e do dia
                UTC (RF-DES-007); usar o dia local de quem pergunta faria duas
                pessoas verem calendarios diferentes do mesmo mes.

        Returns:
            O mes corrente, os dias publicados ate hoje e quantos foram
            resolvidos.
        """
        linhas = await self.repo.dias(
            id_usuario=id_usuario,
            primeiro_dia=primeiro_dia_do_mes(dt_hoje),
            dt_hoje=dt_hoje,
        )

        dias = [
            {
                "dia": linha["dt_dia"],
                "id_desafio": linha["id_desafio"],
                "jogo": linha["co_jogo"],
                "modalidade": linha["co_modalidade"],
                "reprise": bool(linha["ic_reprise"]),
                "resolvido": bool(linha["ic_resolvido"]),
                # ⚠️ **O adversario e o enunciado daquele dia** (T085zc,
                # 25/09/2026): o card de um dia passado e as telas que ele abre
                # mostram o rosto e a frase do desafio (o card do dia do Claude
                # Design, peca N2). Sem isto, cada card buscaria o proprio
                # desafio - uma chamada por dia do mes, so para uma frase.
                # ⚠️ **A MESMA forma do desafio publicado** (`chave` + `valores`),
                # e ⛔ a frase pronta: ela viajaria num idioma so (RF-DES-176).
                # ⚠️ Campos ADITIVOS: aplicativo antigo os ignora.
                "personagem": linha["co_personagem"],
                "objetivo": {
                    "chave": linha["co_chave_objetivo"],
                    "valores": linha["js_objetivo"] or {},
                },
            }
            for linha in linhas
        ]

        return {
            # ⚠️ `AAAA-MM`, e ⛔ nunca o nome do mes: o nome e i18n, e escreve-lo
            # aqui traria "September" para quem le em portugues — ou obrigaria o
            # servidor a saber o idioma de cada aparelho em campo.
            "mes": f"{dt_hoje.year:04d}-{dt_hoje.month:02d}",
            "dias": dias,
            "resolvidos": sum(1 for d in dias if d["resolvido"]),
        }
