"""Modelos do schema `desafio` — a LINHA DE PRODUCAO (T024).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE AQUI NAO HA `class Desafio(Base)` COM `Mapped[...]`
═══════════════════════════════════════════════════════════════════════════

A tarefa T024 pedia *"models SQLAlchemy"*. Ao implementar, isso nao se sustenta
neste repositorio, e vale registrar o porque em vez de repetir a tentativa:

**O projeto nao tem ORM declarativo em lugar nenhum.** Toda a API fala com o
banco por `sqlalchemy.text(...)` com parametros nomeados, **lendo pelas VIEWs** —
`api/sincronizacao/repositorio.py` tem mais de mil linhas nesse estilo, e
`api/nucleo/banco.py` entrega uma `AsyncSession`, nao uma `DeclarativeBase`.

Introduzir mapeamento declarativo agora criaria **duas formas** de falar com o
mesmo banco, e as duas discordariam em silencio no primeiro ponto em que o
mapeamento envelhecesse. Pior: um `Mapped[...]` mapeia **tabela**, e a convencao
do projeto e que a leitura nunca toca a tabela (`data-model.md`, "Como ler").

**O que este arquivo entrega, entao**, e o que a tarefa realmente precisa:

  1. **os vocabularios fechados**, como `Literal` — o mesmo recurso que
     `api/conta/modelos.py` usa para `IdiomaSuportado`. Digitar `'aprovado'`
     errado passa a ser erro de tipo, nao linha recusada pelo banco;
  2. **os nomes das VIEWs**, em constantes. Uma consulta que digite
     `desafio.tb001_desafio` em vez de `vw001_desafio` fura a convencao sem que
     nada acuse — com a constante, o desvio fica visivel;
  3. **os modelos Pydantic** do que cruza fronteira, com o carimbo de qual
     coluna cada campo espelha.

⚠️ **Campo so se ACRESCENTA nestes modelos, nunca se remove nem se renomeia**:
varias versoes do aplicativo convivem em campo lendo a mesma resposta.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════
# 1. As VIEWs — por onde se le
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Nao ha constante para as TABELAS de proposito. Quem escreve neste schema e
# o job, e ele monta o `INSERT` no seu proprio modulo; a API nunca insere aqui.
# Uma constante com o nome da tabela seria um convite a le-la direto.

VW_DESAFIO = "desafio.vw001_desafio"
VW_MEDICAO_REGUA = "desafio.vw002_medicao_regua"
VW_FEITO_DESAFIO = "desafio.vw003_feito_desafio"
VW_TIPO_DESAFIO = "desafio.vw901_tipo_desafio"
VW_CATALOGO_FEITO = "desafio.vw902_catalogo_feito"
VW_PERFIL_DIFICULDADE = "desafio.vw903_perfil_dificuldade"
VW_MOTOR = "desafio.vw904_motor"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os vocabularios fechados
# ═══════════════════════════════════════════════════════════════════════════
#
# `Literal` e uma lista fechada de valores: o Pydantic recusa qualquer coisa
# fora dela, e o verificador de tipos acusa antes mesmo de rodar. Cada um destes
# espelha um `CHECK` da migracao `0018` — e um teste confere que os dois nao
# divergiram, porque duas listas iguais escritas em dois arquivos e exatamente o
# tipo de duplicacao que envelhece torto.

# Como a posicao inicial esta escrita. O Pontinhos precisa da SEQUENCIA de
# lances (a posse de uma caixa e historico: nao esta no tabuleiro); as damas
# cabem numa FEN (cada peca carrega a sua cor na propria casa).
FormatoPosicao = Literal["sequencia_lances", "fen"]

# Os quatro mascotes. ⚠️ `magno` e o nome do 4o no banco e no codigo; "Sagaz" e
# o nome do DEGRAU de dificuldade, nao do personagem.
Personagem = Literal["cacau", "pita", "tex", "magno"]

# O estado na esteira de curadoria. ⛔ So `aprovado` e servido ao aplicativo —
# nunca o candidato (RF-DES-012a).
EstadoCuradoria = Literal["candidato", "aprovado", "descartado"]

# Como a medida crua vira um numero entre 0 e 1.
#   faixa   → precisa de vr_min e vr_max
#   fracao  → precisa de co_sobre (o denominador)
#   nenhuma → medido e exibido, NAO pontuado (exige peso zero)
Normalizacao = Literal["faixa", "fracao", "nenhuma"]

# A leitura natural de um feito. ⚠️ `marco_atingido` e a direcao de quem nao tem
# gradacao (venceu, empatou, desafio concluido) — foi ela que faltava no
# `data-model.md` ate 09/09/2026.
DirecaoFeito = Literal["maior_melhor", "menor_melhor", "marco_atingido"]

# Se o servidor consegue RECALCULAR o feito a partir do log de lances.
ProcedenciaFeito = Literal["tabuleiro", "sessao"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. Os modelos
# ═══════════════════════════════════════════════════════════════════════════


class FeitoDoDesafio(BaseModel):
    """Uma linha de `desafio.tb003_feito_desafio`, ja com o catalogo resolvido.

    Espelha `vw003_feito_desafio`, que entrega `co_feito`, `co_unidade` e
    `co_direcao` ao lado do peso — e e por isso que a publicacao consegue montar
    o bloco de feitos da resposta sem juntar duas tabelas a mao.

    ⚠️ **Peso zero e legitimo**: o feito continua sendo medido e exibido no
    Raio-X, so nao conta para a nota. `co_normalizacao = 'nenhuma'` so existe com
    peso zero, e o `CHECK` da migracao amarra os dois.
    """

    nu_feito: int
    co_feito: str
    co_unidade: str
    co_direcao: DirecaoFeito
    co_procedencia: ProcedenciaFeito
    nu_ordem: int = Field(gt=0)
    # `Decimal` e nao `float`: peso e dinheiro da nota. Somar 0.6 + 0.4 em ponto
    # flutuante nao da 1.0, e um teste que exige soma 1,000 reprovaria por isso.
    vr_peso: Decimal = Field(ge=0, le=1)
    co_normalizacao: Normalizacao
    vr_min: Optional[Decimal] = None
    vr_max: Optional[Decimal] = None
    co_sobre: Optional[str] = None


class MedicaoDaRegua(BaseModel):
    """Uma linha de `desafio.tb002_medicao_regua`: um mascote, uma taxa.

    Uma linha **por mascote**, e e isso que a torna tabela em vez de um par de
    colunas: descartar um desafio por *"duro demais"* e por *"banal"* sao motivos
    diferentes, e e a taxa por nivel que os separa.
    """

    co_personagem: Personagem
    nu_execucoes: int = Field(gt=0)
    nu_resolveu: int = Field(ge=0)
    co_versao_perfil: str
    co_versao_motor: str
    dh_medicao: datetime

    @property
    def taxa(self) -> float:
        """A fracao de execucoes em que aquele mascote resolveu.

        Calculada, e nao guardada: uma coluna com a divisao poderia discordar dos
        dois numeros que a originaram, e ai nao haveria como saber qual esta
        certo.
        """
        return self.nu_resolveu / self.nu_execucoes


class Desafio(BaseModel):
    """Uma linha de `desafio.tb001_desafio` — a unidade jogavel.

    ⚠️ **Este modelo NAO e a resposta do endpoint.** Ele e a linha como ela vive
    no banco; o que o aplicativo baixa e menor e tem outra forma (ver
    `contracts/desafio-publicado.md`). Confundir os dois entregaria o gabarito
    junto com o enunciado — `js_solucao` esta aqui e ⛔ **nunca** viaja antes de
    a pessoa resolver.

    Os pares de campos que costumam gerar duvida:

    `co_formato_posicao` + `js_posicao_inicial` — duas formas de escrever
    posicao, e uma coluna que diz qual. E o que faz um jogo novo caber sem
    migracao.

    `co_chave_objetivo` + `js_objetivo` — a chave e de i18n, ⛔ **nunca a frase
    pronta**: ela viajaria num idioma so. O JSON traz os valores que entram nos
    espacos da frase.
    """

    id_desafio: UUID

    co_jogo: str
    co_modalidade: Optional[str] = None
    co_variante: str
    co_formato_posicao: FormatoPosicao
    js_posicao_inicial: dict[str, Any]

    nu_tipo_desafio: int
    co_tipo_desafio: str
    js_chegada: dict[str, Any]
    ic_chegada_encerra_partida: bool

    co_chave_objetivo: str
    js_objetivo: dict[str, Any]

    co_personagem: Personagem
    nu_semente: int = Field(ge=1, le=4_294_967_295)

    js_solucao: dict[str, Any]
    nu_lances_solucao: int = Field(gt=0)

    nu_tempo_piso_ms: int = Field(gt=0)
    nu_tempo_teto_ms: int = Field(gt=0)

    nu_versao_catalogo: int

    co_versao_minima: str
    co_versao_perfil: str
    co_versao_motor: str
    nu_teto_log: int

    co_curadoria: EstadoCuradoria
    de_motivo_descarte: Optional[str] = None
    id_desafio_origem: Optional[UUID] = None
    ic_reprise: bool = False

    dh_geracao: datetime


class PerfilDeDificuldade(BaseModel):
    """Uma linha de `desafio.tb903_perfil_dificuldade` — com que numeros se mediu.

    ⚠️ **Esta dimensao nao e semeada por migracao**: quem a escreve e o job, ao
    carregar `motores/perfis/<versao>.json` pela primeira vez. Uma migracao que
    soubesse a taxa de erro da Cacau estaria publicando calibracao por `INSERT`.

    `js_perfil` e um JSON livre porque **a forma e por jogo**: damas nao tem
    temperatura de CNN, e Pontinhos nao tem multiplicador de motor.
    """

    co_versao_perfil: str
    co_jogo: str
    co_personagem: Personagem
    js_perfil: dict[str, Any]
    co_arquivo: str
    # SHA-256 em hexadecimal: 64 caracteres, sempre. E ele que liga a linha ao
    # commit em que aqueles numeros estavam no ar.
    co_sha256: str = Field(min_length=64, max_length=64)
    dh_vigencia: datetime
