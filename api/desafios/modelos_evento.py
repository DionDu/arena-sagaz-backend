"""Modelos do schema `desafio_dia` — O EVENTO (T025).

Tudo o que sai do aparelho da pessoa cai neste schema. A justificativa de nao
haver mapeamento declarativo esta em `modelos_producao.py`, e vale igual aqui.

═══════════════════════════════════════════════════════════════════════════
A ORDEM DAS PECAS, QUE E A DECISAO CENTRAL DESTE SCHEMA
═══════════════════════════════════════════════════════════════════════════

    dia         → qual desafio e o de hoje
    tentativa   → uma partida jogada. Aponta para `partida.tb001_partida`
    resolucao   → a tentativa que DEU CERTO. Aponta para a tentativa
    xp          → as linhas do extrato, ancoradas na resolucao, na tentativa
                  ou em nenhuma das duas (o ajuste do teto e **do dia**)

⚠️ **A tentativa precede a resolucao**, e nao o contrario. Uma pessoa tenta
varias vezes, e cada tentativa e uma partida; quem sabe qual delas venceu e a
resolucao, e ela chega la **pela tentativa**.

⚠️ **Tentativa nunca aparece no quadro. Falhar e privado.**
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


def encerramento_do_dia(dt_dia: date) -> datetime:
    """O instante em que o desafio daquele dia encerra: 00:00 UTC do dia seguinte.

    Args:
        dt_dia: o dia do desafio.

    Returns:
        O `dh_encerramento` a gravar em `tb001_desafio_dia`.

    ⚠️ **UTC, e a conta e sempre esta** (RF-DES-008). O dia do Desafio do Dia e um
    dia **UTC**, e nao o dia do fuso de ninguem: e isso que faz o quadro do dia
    ser o mesmo quadro para o mundo inteiro. O aplicativo nunca exibe esta hora —
    ele mostra *"faltam 4h37"*, calculado a partir da diferenca entre este
    instante e o `agora_no_servidor` que viaja junto na resposta.

    ⚠️ **Ela mora aqui, e nao no painel nem no job**, porque os DOIS a
    escrevem: o painel quando o dono troca a data (T039) e o job quando publica
    uma reprise (T041). Duas contas de encerramento discordariam no primeiro
    horario de verao que alguem tentasse acomodar — e a resposta certa e que fuso
    nenhum entra nesta conta.
    """
    # `datetime.combine` cola uma data com uma hora; `time.min` e 00:00:00.
    return datetime.combine(dt_dia + timedelta(days=1), time.min, tzinfo=timezone.utc)

# ═══════════════════════════════════════════════════════════════════════════
# 1. As VIEWs
# ═══════════════════════════════════════════════════════════════════════════

VW_DESAFIO_DIA = "desafio_dia.vw001_desafio_dia"
VW_TENTATIVA = "desafio_dia.vw002_tentativa"
VW_RESOLUCAO = "desafio_dia.vw003_resolucao"
VW_XP_DESAFIO = "desafio_dia.vw004_xp_desafio"
VW_PODER_CONSUMIDO = "desafio_dia.vw005_poder_consumido"
VW_REACAO = "desafio_dia.vw006_reacao"
VW_TIPO_XP = "desafio_dia.vw901_tipo_xp_desafio"
VW_TIPO_PODER = "desafio_dia.vw902_tipo_poder"
VW_TIPO_REACAO = "desafio_dia.vw903_tipo_reacao"

# ⚠️ Aqui as TABELAS ganham constante, ao contrario de `modelos_producao.py`: a
# API **escreve** neste schema, pelo caminho de sincronizacao. Escrita e sempre
# na tabela; leitura e sempre na VIEW.
TB_TENTATIVA = "desafio_dia.tb002_tentativa"
TB_RESOLUCAO = "desafio_dia.tb003_resolucao"
TB_XP_DESAFIO = "desafio_dia.tb004_xp_desafio"
TB_PODER_CONSUMIDO = "desafio_dia.tb005_poder_consumido"
TB_REACAO = "desafio_dia.tb006_reacao"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os vocabularios
# ═══════════════════════════════════════════════════════════════════════════

# O que o servidor achou quando reconferiu a resolucao.
#
# ⚠️ `divergente` **nao apaga a resolucao nem tira XP de ninguem**: marca a linha
# para investigacao. Punir automaticamente com base num recalculo que pode ter
# bug proprio faria o aplicativo tirar XP de gente honesta na primeira versao
# errada do arbitro.
EstadoAuditoria = Literal["pendente", "confere", "divergente"]

# Os codigos da dimensao `tb901_tipo_xp_desafio`, com nome. Escritos aqui para o
# codigo nao carregar numeros soltos: `nu_tipo_xp == 5` nao diz nada; `MERITO`,
# sim. Um teste confere que estes numeros batem com os da migracao `0019`.
XP_BASE = 1
XP_TENTATIVAS = 2
XP_TEMPO = 3
XP_DICA = 4
XP_MERITO = 5
XP_MEDIDA = 6
XP_CONSOLO = 7
XP_AJUSTE = 8
XP_DESCONHECIDO = 9999

# ⚠️ Os DOIS tipos que apontam para um feito — e e exatamente essa dupla que o
# `ck003_feito` da migracao exige. Linha de feito tem de dizer QUAL feito; linha
# que nao e de feito nao pode inventar um.
TIPOS_XP_COM_FEITO = (XP_MERITO, XP_MEDIDA)

# O piso de XP por resolver, e o teto do dia. ⚠️ O teto e **da colecao** (o
# Desafio do Dia), nunca do desafio: ele entra como linha de `ajuste`, negativa,
# e nao como corte no `nu_xp` da resolucao.
XP_PISO_POR_RESOLVER = 18
XP_TETO_DO_DIA = 30


# ═══════════════════════════════════════════════════════════════════════════
# 3. Os modelos
# ═══════════════════════════════════════════════════════════════════════════


class DesafioDoDia(BaseModel):
    """Uma linha de `desafio_dia.tb001_desafio_dia`: um dia, um desafio.

    Duas restricoes do banco sao duas regras de produto, e nenhuma das duas vive
    aqui no codigo de proposito:

    `un001_dia` e a **idempotencia do job** — rodar duas vezes na mesma data nao
    troca o desafio publicado, porque a segunda insercao falha. A garantia mora
    no banco, e nao numa checagem daqui, porque duas execucoes simultaneas
    passariam pela checagem e so o banco as separa.

    `un002_desafio` e *"um desafio e publicado uma vez so"*. A reprise passa sem
    excecao porque ela e uma **copia**, com identificador proprio.
    """

    id_desafio_dia: UUID
    dt_dia: date
    id_desafio: UUID
    dh_encerramento: datetime
    dh_publicacao: datetime


class Tentativa(BaseModel):
    """Uma linha de `desafio_dia.tb002_tentativa` — e uma partida jogada.

    ⚠️ `id_partida` nao e conveniencia de replay: e **condicao de leitura do
    log**. A reconstrucao do tabuleiro de Pontinhos a partir das arestas assume
    comecar de um tabuleiro vazio, e um desafio nao comeca vazio — a posicao
    inicial so e alcancavel por `tentativa → dia → desafio`.

    `nu_tempo_ms` e o tempo **desta** tentativa. O tempo do dia e a soma, e a
    soma se faz na consulta.
    """

    id_tentativa: UUID
    id_desafio_dia: UUID
    id_usuario: UUID
    id_partida: UUID
    nu_sequencia: int = Field(gt=0)
    ic_resolveu: bool
    nu_tempo_ms: int = Field(ge=0)
    dh_inicio: datetime
    dh_fim: datetime


class Resolucao(BaseModel):
    """Uma linha de `desafio_dia.tb003_resolucao` — a tentativa que deu certo.

    ⚠️ `nu_lance_cumpre_desafio` e o **`nu_ordem`** da jogada, nao o `nu_lance`.
    `nu_ordem` e sequencia continua de eventos: nunca recua e nunca se repete.
    `nu_lance` recua quando alguem desfaz uma jogada, e pode repetir — como
    ponteiro para uma linha so, ele seria uma armadilha esperando o dia em que
    "voltar jogada" chegue ao desafio.

    `nu_xp` fica entre 18 e 30: 18 e o piso por resolver, e o teto de 30/dia e da
    colecao. O arredondamento acontece **uma vez**, no fim — as parcelas em
    `tb004_xp_desafio` tem casas decimais.
    """

    id_resolucao: UUID
    id_desafio_dia: UUID
    id_usuario: UUID
    id_tentativa: UUID
    nu_lance_cumpre_desafio: int = Field(gt=0)
    nu_xp: int = Field(ge=XP_PISO_POR_RESOLVER, le=XP_TETO_DO_DIA)
    nu_versao_catalogo: int
    co_auditoria: EstadoAuditoria = "pendente"
    de_auditoria: Optional[str] = None
    dh_resolucao: datetime


class LinhaDeXp(BaseModel):
    """Uma linha de `desafio_dia.tb004_xp_desafio` — o extrato, aberto.

    ⚠️ **Uma linha carrega a conta inteira**: a medida crua, a mesma medida
    normalizada em [0,1], o peso dentro de `Q` e a parcela em XP. Guardar so o XP
    faria o Raio-X mostrar *"+1,8"* sem poder dizer de onde saiu.

    A formula: `XP = 18 + 12 x Q`, e **cada linha vale `12 x vr_peso x
    vr_normalizado`** — a linha `base` vale os 18 fixos.

    ⚠️ **Tres das quatro parcelas correm ao contrario**: mais tentativas, mais
    tempo e mais dicas dao MENOS XP. A inversao acontece no `vr_normalizado`, e a
    direcao de cada feito vem do catalogo — nao e escrita de novo aqui. Uma
    parcela na direcao errada **nao daria erro nenhum**: so pagaria mais a quem
    jogou pior.

    ⚠️ `vr_xp` e `Decimal`, nunca `float`. As parcelas tem casas decimais, e
    arredondar cada uma faria a soma nao bater com o total.
    """

    id_xp_desafio: UUID
    id_desafio_dia: UUID
    id_usuario: UUID
    # As tres ancoras. As duas nulas ao mesmo tempo significam a linha de
    # `ajuste`: ela e **do dia**, nao de um evento.
    id_resolucao: Optional[UUID] = None
    id_tentativa: Optional[UUID] = None
    nu_tipo_xp: int
    co_tipo_xp: str
    nu_feito: Optional[int] = None
    co_feito: Optional[str] = None
    vr_medida: Optional[Decimal] = None
    vr_normalizado: Optional[Decimal] = Field(default=None, ge=0, le=1)
    vr_peso: Optional[Decimal] = Field(default=None, ge=0, le=1)
    vr_xp: Decimal

    @property
    def e_linha_de_feito(self) -> bool:
        """Esta linha aponta para um feito do catalogo?

        Espelha o `ck003_feito` da migracao. Existe para que o codigo nao repita
        `nu_tipo_xp in (5, 6)` espalhado — e para que a pergunta tenha **um**
        lugar onde ser respondida no dia em que um tipo novo com feito aparecer.
        """
        return self.nu_tipo_xp in TIPOS_XP_COM_FEITO


class PoderConsumido(BaseModel):
    """Uma linha de `desafio_dia.tb005_poder_consumido` — a dica que foi gasta.

    ⚠️ Presa a **tentativa**, e nao ao dia: e ali que a dica foi de fato gasta, e
    guardar assim permite ver depois se o poder esta consertando um deslize ou
    procurando o lance certo por tentativa e erro.

    ⚠️ **O teto continua sendo de duas dicas por DESAFIO**, e o contador do dia e
    uma soma sobre as tentativas — fechar o aplicativo encerra a tentativa, nao o
    dia, e um contador que vivesse na tentativa daria dicas infinitas a quem
    reabrisse.

    O grau (1 = regiao ou peca · 2 = o lance) fica na linha porque as duas dicas
    nao sao a mesma coisa, e a segunda so faz sentido depois da primeira.
    """

    id_poder_consumido: UUID
    id_tentativa: UUID
    nu_tipo_poder: int
    co_tipo_poder: str
    nu_grau: int = Field(ge=1, le=2)
    dh_consumo: datetime


class Reacao(BaseModel):
    """Uma linha de `desafio_dia.tb006_reacao` — palmas, uau ou fogo.

    ⚠️ Pende da **resolucao**, nao da tentativa: o quadro so mostra quem
    resolveu, e nao se reage ao que nao aparece. Mascote nao recebe reacao.

    Uma por pessoa por linha do quadro — a pessoa pode **trocar** a sua, nao
    acumular.

    ⚠️ `co_emoji` vem do banco, e `co_chave_i18n` tambem: o **simbolo** viaja
    como dado (trocar um emoji nao deveria exigir versao nova na loja), mas o
    **rotulo** e codigo — leitor de tela le no idioma da pessoa, e este banco nao
    fala tres idiomas.
    """

    id_reacao: UUID
    id_resolucao: UUID
    id_usuario: UUID
    nu_tipo_reacao: int
    co_tipo_reacao: str
    co_emoji: str
    co_chave_i18n: str
    dh_reacao: datetime
