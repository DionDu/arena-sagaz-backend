"""`GET /v1/card-do-dia` - a única leitura da página do card do dia.

A página (Flutter web, só do dono) desenha os stories no celular e os entrega à
janela de compartilhar. Ela precisa de três coisas, e esta rota entrega as três
numa resposta só:

1. **o desafio que está valendo**, no MESMO formato de `/v1/desafios/hoje`
   (`DesafioPublicado`), para a página reaproveitar o código do app que o lê;
2. **a agenda**: se hoje é dia de publicar, quais stories, em que layout e papel,
   e com que legenda (`agenda.py`);
3. **os números do Magno**, quando é a quarta dele (`magno.py`).

═══════════════════════════════════════════════════════════════════════════
⚠️ PÚBLICA E SÓ DE LEITURA, COMO O `/hoje`
═══════════════════════════════════════════════════════════════════════════

Sem login: nada aqui é de uma pessoa. O desafio é o mesmo para todo mundo, e os
números do Magno são contagens. ⛔ Nunca o gabarito (a consulta é a do `/hoje`,
que não seleciona `js_solucao`) e ⛔ nunca um desafio de dia que ainda não começou.

⚠️ **Não é o `/hoje` reaproveitado, de propósito:** o `/hoje` anota a visita do
aparelho (a amostra da adoção de versões, T118), e a página do dono no navegador
entraria nessa amostra como um "aparelho" que não existe.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.card_do_dia import agenda as regras
from api.card_do_dia import magno
from api.desafios.modelos_resposta import DesafioPublicado
from api.desafios.publicacao import para_resposta
from api.desafios.repositorio import RepositorioDesafio
from api.nucleo.banco import obter_sessao

router = APIRouter()

#: Quanto tempo os números do Magno ficam guardados na memória do processo.
#: A consulta lê todas as partidas contra o Magno; a página é aberta poucas vezes
#: por semana, mas pode ser recarregada várias vezes seguidas no momento do post.
CACHE_MAGNO_SEGUNDOS = 600

# O cache: (instante em que foi lido, partidas). `time.monotonic()` é um relógio
# que só anda para a frente (não volta quando o relógio do sistema é acertado),
# o certo para medir "há quanto tempo".
_cache_magno: Optional[tuple[float, list[magno.PartidaDoMagno]]] = None


# ── O formato da resposta ────────────────────────────────────────────────────


class StoryDoDia(BaseModel):
    """Um story, na ordem de publicação."""

    card: Literal["convite", "magno", "ajuda"]
    #: Um dos quatro papéis da moldura do vídeo: caderno, damas, quatro, pontinhos.
    papel: str
    #: Só no convite: 1 (lado a lado), 2 (o balão), 3 (o cartaz).
    layout: Optional[int] = None
    #: A legenda pronta. No convite traz as lacunas `{objetivo}` e `{jogo}`, que
    #: a página preenche com o texto do app (ver `agenda.LEGENDAS_CONVITE`).
    legenda: str


class MagnoDoDia(BaseModel):
    """O que o card D mostra. Só vem na quarta do Magno, e se os números valem."""

    variante: Literal["placa", "placar"]
    #: `None` = os quatro jogos juntos; senão, o `co_jogo` do escopo.
    jogo: Optional[str] = None
    dias_sem_perder: int
    recorde_dias: int
    #: O rótulo do placar ("Em novembro") e os seus números.
    periodo: str
    partidas_no_periodo: int
    derrotas_no_periodo: int


class CardDoDia(BaseModel):
    """A resposta inteira da página."""

    agora_no_servidor: datetime
    #: O dia de Brasília em que o desafio vigente começou (às 21h).
    dia_publicacao: date
    #: Se `dia_publicacao` é um dos quatro dias da semana. Falso = a página diz
    #: "hoje não tem publicação", e os stories vêm mesmo assim (o botão "ver
    #: mesmo assim").
    publica_hoje: bool
    proxima_publicacao: date
    #: O link que vai na figurinha e na legenda (com a origem `story`).
    link: str
    #: `None` = o desafio de hoje não foi aprovado na curadoria; a página diz
    #: isso e não há post.
    desafio: Optional[DesafioPublicado] = None
    stories: list[StoryDoDia]
    magno: Optional[MagnoDoDia] = None


# ── As dependências (trocáveis nos testes) ───────────────────────────────────


def agora_utc() -> datetime:
    """O instante do servidor. Função com nome para o teste poder fixá-lo."""
    return datetime.now(timezone.utc)


async def ler_desafio_vigente(
    sessao: AsyncSession = Depends(obter_sessao),
) -> Optional[dict]:
    """A linha do desafio que está valendo agora (a mesma consulta do `/hoje`)."""
    return await RepositorioDesafio(sessao).de_hoje(agora=agora_utc())


async def ler_partidas_do_magno(
    sessao: AsyncSession = Depends(obter_sessao),
) -> list[magno.PartidaDoMagno]:
    """As partidas contra o Magno, com o cache de `CACHE_MAGNO_SEGUNDOS`."""
    global _cache_magno  # `global`: a função reescreve a variável do módulo
    if _cache_magno is not None and time.monotonic() - _cache_magno[0] < CACHE_MAGNO_SEGUNDOS:
        return _cache_magno[1]
    partidas = await magno.ler_partidas_do_magno(sessao)
    _cache_magno = (time.monotonic(), partidas)
    return partidas


# ── A rota ───────────────────────────────────────────────────────────────────


@router.get("/card-do-dia", response_model=CardDoDia)
async def card_do_dia(
    resposta: Response,
    linha_desafio: Optional[dict] = Depends(ler_desafio_vigente),
    partidas: list[magno.PartidaDoMagno] = Depends(ler_partidas_do_magno),
) -> CardDoDia:
    """O desafio vigente, a agenda do dia e (na quarta do Magno) os números dele.

    Sem desafio aprovado, o dia de publicação sai do relógio (o dia UTC de agora
    menos um), para a página ainda saber dizer "hoje não é dia" ou "não aprovado".
    """
    agora = agora_utc()
    dia_utc = linha_desafio["dt_dia"] if linha_desafio else agora.date()
    dia = regras.dia_de_publicacao(dia_utc)

    rotulo_periodo = ""
    escopos = None
    if regras.e_quarta_do_magno(dia):
        # Só na quarta do Magno a conta roda (as partidas já vieram do cache).
        escopos, rotulo_periodo = magno.calcular_escopos(partidas, dia)
    plano = regras.montar_agenda(dia, escopos_do_magno=escopos)

    magno_do_dia = None
    if plano.magno is not None:
        n = plano.magno.numeros
        magno_do_dia = MagnoDoDia(
            variante=plano.magno.variante,
            jogo=n.jogo,
            dias_sem_perder=n.dias_sem_perder,
            recorde_dias=n.recorde_dias,
            periodo=rotulo_periodo,
            partidas_no_periodo=n.partidas_no_periodo,
            derrotas_no_periodo=n.derrotas_no_periodo,
        )

    # ⚠️ A página é do dono, aberta às 21h em ponto: nada de cache no caminho,
    # senão ela mostraria o desafio de ontem por alguns minutos.
    resposta.headers["Cache-Control"] = "no-store"
    resposta.headers["X-Robots-Tag"] = "noindex"
    return CardDoDia(
        agora_no_servidor=agora,
        dia_publicacao=plano.dia_publicacao,
        publica_hoje=plano.publica_hoje,
        proxima_publicacao=plano.proxima_publicacao,
        link=regras.LINK_DOS_STORIES,
        desafio=para_resposta(linha_desafio, agora=agora) if linha_desafio else None,
        stories=[
            StoryDoDia(card=s.card, papel=s.papel, layout=s.layout, legenda=s.legenda)
            for s in plano.stories
        ],
        magno=magno_do_dia,
    )
