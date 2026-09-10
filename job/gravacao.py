"""A GRAVACAO: idempotente e com folga (RF-DES-012/013, T038).

═══════════════════════════════════════════════════════════════════════════
⚠️ A FREQUENCIA DO JOB NAO E A FREQUENCIA DO DESAFIO
═══════════════════════════════════════════════════════════════════════════

E a frase de RF-DES-011, e ela e a razao de este modulo existir separado.

Cada execucao cobre **todos os dias entre agora e a proxima execucao prevista**,
com folga: no minimo **7** dias, no maximo **30**. O cron pode rodar uma vez por
dia, uma vez por semana ou uma vez por mes — o que muda e quantos dias cada
execucao precisa cobrir, e nao quantos desafios existem.

⚠️ **O minimo de 7 nao e conforto: e a margem de sobrevivencia.** Se o job falhar
e ninguem perceber, ha uma semana de fila antes de o aplicativo abrir sem desafio
do dia. Um job que cobrisse so o dia seguinte transformaria qualquer falha de uma
noite num dia sem produto.

⚠️ **O maximo de 30 tambem tem motivo**, e ele e de curadoria: desafio gerado com
muita antecedencia e revisado com muita antecedencia, e o dono passaria a aprovar
conteudo que so vai ao ar dali a meses — sem saber o que mais estara publicado
junto.

═══════════════════════════════════════════════════════════════════════════
⚠️ A IDEMPOTENCIA MORA NO BANCO, E NAO NUMA CHECAGEM DAQUI
═══════════════════════════════════════════════════════════════════════════

`desafio_dia.tb001_desafio_dia` tem `un001_dia UNIQUE (dt_dia)`. Rodar duas vezes
para a mesma data **nao troca** o desafio publicado, porque a segunda insercao
falha.

⛔ **Uma checagem "ja existe?" antes do `INSERT` NAO basta**, e essa e a parte que
costuma ser feita errada: duas execucoes simultaneas passariam as duas pela
checagem, e so o banco as separa. A checagem daqui existe para **evitar trabalho**
(nao gerar o que ja existe), nunca para garantir a unicidade.

═══════════════════════════════════════════════════════════════════════════
⚠️ E E AQUI QUE `nu_versao_catalogo` E CARIMBADO
═══════════════════════════════════════════════════════════════════════════

A coluna e `NOT NULL` e diz com que versao do catalogo de feitos aquele desafio
foi escrito. Sem o carimbo, o `INSERT` falha — de proposito.

⚠️ Ela e o que mantem uma resolucao antiga **explicavel** depois de o catalogo
crescer: da para saber com que regua aquele 27 foi calculado. Sem ela, um
recalculo futuro daria outro numero e ninguem saberia qual dos dois vale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "contratos" / "catalogo_feitos.json"

#: A folga da fila, em dias (RF-DES-012).
DIAS_MINIMOS = 7
DIAS_MAXIMOS = 30


class GravacaoInvalida(ValueError):
    """O plano de gravacao nao respeita as regras da fila."""


@dataclass(frozen=True, slots=True)
class PlanoDoDia:
    """O que a execucao pretende fazer com um dia.

    Atributos:
        dt_dia: o dia.
        ja_publicado: se ja existe desafio para ele.
    """

    dt_dia: date
    ja_publicado: bool

    @property
    def precisa_gerar(self) -> bool:
        """Dia ja publicado nao se toca — e a idempotencia vista daqui."""
        return not self.ja_publicado


def dias_a_cobrir(
    *,
    dt_hoje: date,
    dt_proxima_execucao: date | None = None,
    dias_minimos: int = DIAS_MINIMOS,
    dias_maximos: int = DIAS_MAXIMOS,
) -> list[date]:
    """Que dias esta execucao precisa cobrir.

    Args:
        dt_hoje: o dia em que o job esta rodando.
        dt_proxima_execucao: quando o cron vai acordar de novo. `None` quando
            nao se sabe — e ai vale o minimo.
        dias_minimos, dias_maximos: a folga.

    Returns:
        Os dias, de hoje em diante, em ordem.

    ⚠️ **A conta inclui HOJE.** Um job que comecasse em D+1 deixaria o proprio dia
    da execucao descoberto sempre que a fila tivesse acabado — que e exatamente a
    situacao em que ele mais precisa cobrir.

    ⚠️ **E ela cobre ate a proxima execucao MAIS a folga**, e nao ate a proxima
    execucao. Cobrir so ate la nao deixaria margem nenhuma: bastaria a proxima
    execucao falhar para o dia seguinte ficar vazio.
    """
    if dias_minimos < 1:
        raise GravacaoInvalida(f"dias_minimos precisa ser >= 1; veio {dias_minimos}")
    if dias_maximos < dias_minimos:
        raise GravacaoInvalida(
            f"dias_maximos ({dias_maximos}) menor que dias_minimos ({dias_minimos})"
        )

    quantos = dias_minimos
    if dt_proxima_execucao is not None:
        if dt_proxima_execucao < dt_hoje:
            raise GravacaoInvalida(
                f"a proxima execucao ({dt_proxima_execucao}) e anterior a hoje "
                f"({dt_hoje})"
            )
        # Ate a proxima execucao, mais a folga minima.
        ate_la = (dt_proxima_execucao - dt_hoje).days
        quantos = max(dias_minimos, ate_la + dias_minimos)

    quantos = min(quantos, dias_maximos)
    return [dt_hoje + timedelta(days=n) for n in range(quantos)]


def montar_plano(
    *,
    dt_hoje: date,
    dias_ja_publicados: Iterable[date],
    dt_proxima_execucao: date | None = None,
) -> list[PlanoDoDia]:
    """O plano da execucao: que dias cobrir e quais ja estao prontos.

    ⚠️ **Os dias ja publicados NAO sao pulados em silencio** — eles entram no
    plano marcados. E o que permite ao log dizer *"cobri 7 dias, 5 ja estavam
    publicados, gerei 2"*, em vez de um numero sozinho que nao distingue "fila
    cheia" de "job nao fez nada".
    """
    publicados = set(dias_ja_publicados)
    return [
        PlanoDoDia(dt_dia=dia, ja_publicado=dia in publicados)
        for dia in dias_a_cobrir(
            dt_hoje=dt_hoje, dt_proxima_execucao=dt_proxima_execucao
        )
    ]


def versao_do_catalogo() -> int:
    """O `nu_versao_catalogo` a carimbar em cada desafio gerado agora.

    ⚠️ **Sai do manifesto**, e nao de uma constante: o manifesto e a mesma coisa
    que a dimensao do banco (o cadeado 4 garante), e uma constante aqui poderia
    discordar dela sem que nada acusasse.
    """
    if not CATALOGO.is_file():
        raise GravacaoInvalida(
            f"o manifesto do catalogo nao esta em {CATALOGO}, e sem ele nao ha "
            "como carimbar `nu_versao_catalogo` — a coluna e NOT NULL, e o "
            "INSERT falharia depois de toda a medicao ter sido feita."
        )
    dados = json.loads(CATALOGO.read_text(encoding="utf-8"))
    versao = dados.get("nu_versao_catalogo")
    if not isinstance(versao, int) or versao < 1:
        raise GravacaoInvalida(
            f"nu_versao_catalogo invalido no manifesto: {versao!r}"
        )
    return versao


@dataclass(frozen=True, slots=True)
class LinhaDeDesafio:
    """Os campos de `desafio.tb001_desafio` prontos para o `INSERT`.

    ⚠️ Este dataclass **nao** fala com o banco: ele so junta o que o job produziu
    e confere o que precisa estar junto. Quem executa o `INSERT` e o repositorio,
    e ele recebe isto pronto.
    """

    co_jogo: str
    co_modalidade: str | None
    co_variante: str
    co_formato_posicao: str
    js_posicao_inicial: dict[str, Any]
    nu_tipo_desafio: int
    js_chegada: dict[str, Any]
    ic_chegada_encerra_partida: bool
    co_chave_objetivo: str
    js_objetivo: dict[str, Any]
    co_personagem: str
    nu_semente: int
    js_solucao: dict[str, Any]
    nu_lances_solucao: int
    nu_tempo_piso_ms: int
    nu_tempo_teto_ms: int
    nu_versao_catalogo: int
    co_versao_minima: str
    co_versao_perfil: str
    co_versao_motor: str
    nu_teto_log: int
    co_curadoria: str = "candidato"


def montar_linha(
    candidato,
    *,
    ic_chegada_encerra_partida: bool,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    co_versao_perfil: str,
    co_versao_motor: str,
    co_versao_minima: str,
    nu_teto_log: int,
) -> LinhaDeDesafio:
    """Junta o candidato e as medidas numa linha pronta para gravar.

    ⚠️ **Tudo nasce `candidato`** (RF-DES-012a): nada vai ao ar sem o dono ver. Um
    padrao `aprovado` aqui faria a curadoria virar opcional por acidente — e a
    primeira vez que alguem esquecesse de aprovar, o desafio iria ao ar sozinho.
    """
    return LinhaDeDesafio(
        co_jogo=candidato.co_jogo,
        co_modalidade=candidato.co_modalidade,
        co_variante=candidato.co_variante,
        co_formato_posicao=candidato.co_formato_posicao,
        js_posicao_inicial=candidato.js_posicao_inicial,
        nu_tipo_desafio=candidato.receita.nu_tipo_desafio,
        js_chegada=candidato.js_chegada,
        ic_chegada_encerra_partida=ic_chegada_encerra_partida,
        co_chave_objetivo=candidato.receita.co_chave_objetivo,
        js_objetivo=candidato.js_objetivo,
        co_personagem=candidato.co_personagem,
        nu_semente=candidato.nu_semente,
        js_solucao=candidato.js_solucao,
        nu_lances_solucao=candidato.nu_lances_solucao,
        nu_tempo_piso_ms=nu_tempo_piso_ms,
        nu_tempo_teto_ms=nu_tempo_teto_ms,
        nu_versao_catalogo=versao_do_catalogo(),
        co_versao_minima=co_versao_minima,
        co_versao_perfil=co_versao_perfil,
        co_versao_motor=co_versao_motor,
        nu_teto_log=nu_teto_log,
    )


#: O `INSERT` do dia, com a idempotencia **no banco**.
#:
#: ⚠️ `ON CONFLICT (dt_dia) DO NOTHING` e o que torna a segunda execucao inofensiva
#: — e aqui `DO NOTHING` e a escolha CERTA, ao contrario do ingestor de partidas,
#: onde ele descartava em silencio o envio que completava a partida. A diferenca:
#: um dia ja publicado **nao tem segunda versao**; uma partida em andamento tem.
SQL_PUBLICAR_O_DIA = """
INSERT INTO desafio_dia.tb001_desafio_dia
       (dt_dia, id_desafio, dh_encerramento)
VALUES (:dt_dia, :id_desafio, :dh_encerramento)
ON CONFLICT (dt_dia) DO NOTHING
RETURNING id_desafio_dia
"""


def conferir_plano(plano: Sequence[PlanoDoDia]) -> None:
    """O plano respeita a folga e nao tem dia repetido?

    Raises:
        GravacaoInvalida: quando a fila ficaria curta demais, longa demais, ou
            com o mesmo dia duas vezes.
    """
    if not plano:
        raise GravacaoInvalida("plano vazio: nenhum dia seria coberto")

    dias = [p.dt_dia for p in plano]
    if len(set(dias)) != len(dias):
        raise GravacaoInvalida(f"o plano repete dias: {dias}")
    if len(dias) < DIAS_MINIMOS:
        raise GravacaoInvalida(
            f"o plano cobre {len(dias)} dias, e o minimo e {DIAS_MINIMOS}. "
            "⚠️ A folga e a margem de sobrevivencia: sem ela, uma falha de uma "
            "noite vira um dia sem produto."
        )
    if len(dias) > DIAS_MAXIMOS:
        raise GravacaoInvalida(
            f"o plano cobre {len(dias)} dias, e o maximo e {DIAS_MAXIMOS}. "
            "⚠️ Gerar com muita antecedencia faz o dono aprovar conteudo que so "
            "vai ao ar dali a meses."
        )
    if dias != sorted(dias):
        raise GravacaoInvalida("o plano nao esta em ordem de data")
