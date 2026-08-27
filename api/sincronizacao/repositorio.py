"""Repositório de sincronização (spec 006 / US1 — T032/T033).

Escrita nas tabelas ``partida.*``/``jogo_pontinhos.*``/``progressao.*`` e leitura
pelas VIEWs, com ``sqlalchemy.text(...)`` e parâmetros nomeados (nunca
interpolação — anti-SQL-injection). Segue o mesmo estilo de ``api/conta/repositorio.py``.

⚠️ TESTES DE INTEGRAÇÃO PENDENTES: este SQL só roda contra o Postgres com a
migração ``0003_conta_nuvem`` aplicada. Os testes de CONTRATO (T023/T024) usam um
repositório FALSO e validam o serviço/rotas sem banco. A validação do SQL real
depende de aplicar a migração (Railway des) e rodar os testes de integração.

Idempotência:
 • ingestão de partida → ``INSERT ... ON CONFLICT (co_evento) DO NOTHING RETURNING``;
 • merge convidado → ``INSERT ... ON CONFLICT (co_lote_migracao) DO NOTHING RETURNING``.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.sincronizacao import dimensoes

logger = logging.getLogger(__name__)

# As chaves de extensao que ESTE backend sabe gravar. Tudo o que nao estiver
# aqui e das chaves genericas da jogada e uma extensao de um jogo que ainda nao
# existe deste lado.
_EXTENSOES_CONHECIDAS = frozenset({"pontinhos", "velha", "damas"})

# Quantas recusas o servidor aceita por partida.
#
# ⚠️ **O app já conta 50 e para de gravar. Este teto é o SEGUNDO**, e existe
# porque o servidor não pode confiar na contagem do cliente: um defeito em laço
# num app em campo mandaria milhares de linhas, e quem paga a conta do banco é
# este lado. O excedente é DESCARTADO com aviso — nunca faz o evento ser
# rejeitado, pela mesma assimetria da V-5: perder algumas recusas é barato,
# perder a partida inteira não é.
_TETO_DE_RECUSAS_POR_PARTIDA = 50

# Os campos da jogada GENERICA. Precisam ser listados para distinguir "campo da
# jogada" de "extensao de jogo" ao varrer o dicionario recebido.
_CAMPOS_GENERICOS_DA_JOGADA = frozenset(
    {
        "id_jogada",
        "nu_ordem",
        "nu_jogador",
        "dh_jogada",
        "nu_timer_ms",
        "nu_tempo_decisao_ms",
        "co_origem_decisao",
        # O poder "voltar jogada" (T203). ⚠️ Sao GENERICOS, e nao das damas: o
        # poder nasceu em `lib/core/poderes/` e vale para qualquer jogo do hub.
        # Uma jogada desfeita e uma jogada desfeita em qualquer tabuleiro.
        "nu_lance",
        "ic_cancelada",
        "co_poder",
        "dh_cancelamento",
    }
)


# Os campos da PARTIDA generica. Mesmo papel da lista de jogada acima, para o
# nivel de cima: distinguir "campo da partida" de "extensao de jogo".
#
# ⚠️ Esta lista nasceu em 20/08/2026, com as damas, e ela conserta um ponto cego:
# ate entao NENHUM jogo tinha extensao de PARTIDA, entao a varredura so existia
# para a jogada. Um app que mandasse `partida["xadrez"]` nao seria avisado —
# nao daria erro, mas tambem nao deixaria rastro nenhum de que faltava um
# ingestor. O buraco nao era teorico: as damas sao justamente o primeiro caso.
_CAMPOS_GENERICOS_DA_PARTIDA = frozenset(
    {
        "id_partida",
        "co_evento",
        "co_jogo",
        "co_variante",
        "co_modo",
        "id_usuario",
        "id_usuario_j2",
        "co_dificuldade",
        "nu_placar_j1",
        "nu_placar_j2",
        "ic_pontua",
        "co_status",
        "co_lote_migracao",
        "dh_inicio",
        "dh_fim",
        "nu_offset_minuto_j1",
        "nu_offset_minuto_j2",
        # Quantos USOS de poder houve na partida (T204). ⚠️ So chega quando e
        # maior que zero: o app o omite no caso comum, para o payload dos jogos
        # sem poder continuar byte a byte igual ao que ja esta em campo.
        "qt_usos_poder",
        # Campo de app antigo: a coluna sumiu na migracao 0007 e o valor e
        # ignorado, mas ele ainda chega. Listar aqui evita um warning inutil a
        # cada partida de quem nao atualizou.
        "co_anonimo",
    }
)


def _avisar_extensao_desconhecida(jogada: dict[str, Any]) -> None:
    """Registra (sem rejeitar) uma extensao de jogo que este backend nao conhece.

    ⚠️ **Ignorar e deliberado** — decisao V-5 de
    `specs/007-jogo-da-velha/data-model.md`, e diretriz do dono em 2026-08-06:
    nada do jogo novo pode quebrar quem esta com o app antigo.

    A assimetria e o que decide. Rejeitar faz o app **descartar o evento
    inteiro** (contrato escrito no proprio `validacao.py`), jogando fora a
    **partida completa** do usuario para nao perder um detalhe que este backend
    nao saberia guardar de todo modo. Ignorar perde o detalhe; rejeitar perde a
    partida.

    O `warning` existe para que o silencio nao seja total: e ele que avisa que
    ha um app em campo mais novo que este backend, e que falta um ingestor.
    """
    _avisar(jogada, _CAMPOS_GENERICOS_DA_JOGADA, "jogada")


def _avisar_extensao_de_partida_desconhecida(partida: dict[str, Any]) -> None:
    """O mesmo da funcao acima, um nivel acima: na PARTIDA.

    Existe desde 20/08/2026, quando as damas trouxeram a primeira extensao de
    partida do app. Antes disso a varredura so cobria a jogada, e uma extensao
    de partida desconhecida passava em silencio TOTAL — sem erro e sem rastro.
    """
    _avisar(partida, _CAMPOS_GENERICOS_DA_PARTIDA, "partida")


def _avisar(dado: dict[str, Any], genericos: frozenset[str], onde: str) -> None:
    """O corpo comum das duas funcoes acima.

    ⚠️ **Uma funcao, e nao duas parecidas.** As duas varreduras fazem exatamente
    a mesma coisa sobre dicionarios diferentes; escreve-las duas vezes e o
    caminho conhecido para uma delas ganhar uma correcao que a outra nao recebe.

    Um valor que nao e `dict` nao e extensao — e so um campo solto que este
    backend nao conhece (um campo novo da partida generica, por exemplo), e
    ignora-lo em silencio e o comportamento correto: e exatamente a tolerancia a
    mudancas aditivas que o contrato de versionamento da API exige.
    """
    for chave in dado:
        if chave in genericos or chave in _EXTENSOES_CONHECIDAS:
            continue
        if not isinstance(dado.get(chave), dict):
            continue
        logger.warning(
            "Extensao de %s desconhecida: %r. O evento foi ACEITO e a extensao "
            "ignorada (decisao V-5). Provavel app mais novo que este backend; "
            "falta o ingestor deste jogo.",
            onde,
            chave,
        )


def _data(valor: Any) -> date | None:
    """Converte para ``date`` (coluna ``dt_ultimo_dia_jogado`` é DATE, e o
    asyncpg é estrito: DATE quer ``date``, não ``datetime`` nem ``str``). Aceita
    ``date``/``datetime``/ISO-string; qualquer coisa inválida vira ``None``."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    dt = _dt(valor)
    return dt.date() if dt else None


def _dt(valor: Any) -> datetime | None:
    """Converte uma string ISO-8601 (como o app envia, ex.:
    ``2026-07-04T11:38:00.000``) em ``datetime``.

    ⚠️ CRÍTICO: o ``asyncpg`` é ESTRITO com tipos — ele NÃO aceita ``str`` para
    colunas ``TIMESTAMPTZ`` (espera um ``datetime``), e lança ``DataError`` se
    receber uma string. Sem esta conversão, gravar uma partida estoura com 500 e
    o evento fica "pendente" para sempre no app. ``None`` e ``datetime`` passam
    direto; string inválida vira ``None`` (a coluna NOT NULL então acusa o
    problema de forma clara)."""
    if valor is None or isinstance(valor, datetime):
        return valor
    try:
        # `Z` (UTC) → offset explícito, que o fromisoformat entende.
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def _offset(valor: Any) -> int | None:
    """Sanitiza o offset de fuso (minutos em relação ao UTC, ex.: −180 = BRT).

    Só aceita inteiro dentro de −840..+840 (UTC−14 a UTC+14, os extremos que
    existem de verdade). Qualquer outra coisa vira ``None`` — assim um valor podre
    do cliente NÃO estoura o CHECK da coluna e derruba a partida inteira com 500.
    A coluna é anulável de propósito (apps antigos não mandam este campo)."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor if -840 <= valor <= 840 else None


def _inteiro_nao_negativo(valor: Any, *, teto: int = 999) -> int:
    """Sanitiza uma CONTAGEM que vem do cliente (hoje: ``qt_usos_poder``).

    Devolve ``0`` para qualquer coisa que nao seja um inteiro dentro de
    ``0..teto`` — inclusive ``None``, que e o caso comum: o app so envia a chave
    quando ela e maior que zero, para o payload dos jogos sem poder continuar
    identico ao que ja esta em campo.

    ⚠️ **Por que sanitizar em vez de confiar.** A coluna e ``SMALLINT NOT NULL``
    com ``CHECK (qt_usos_poder >= 0)``. Um valor podre do cliente — negativo, uma
    string, um numero absurdo — estouraria o CHECK ou o tipo e derrubaria a
    **partida inteira** com 500; e a partida da pessoa ficaria presa para sempre
    na fila de sincronizacao daquele aparelho. E a mesma assimetria da decisao
    V-5, e a mesma escolha de :func:`_offset`: perder um numero de telemetria e
    barato, perder a partida nao e.

    ⚠️ ``bool`` e ``int`` em Python (``True == 1``), e por isso ele e recusado
    explicitamente: ``"qt_usos_poder": true`` viraria "um uso" em silencio.

    O teto de 999 nao e uma regra de jogo — os limites por personagem vivem no
    Remote Config e mudam sem migracao. Ele so barra o absurdo.
    """
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor if 0 <= valor <= teto else 0


def calcular_sequencia_de_dias(dias: list[date]) -> int:
    """Calcula a "chama" (sequência) a partir da lista de **dias LOCAIS distintos**
    em que o jogador jogou, em ordem CRESCENTE.

    É a MESMA regra "gentil" do app (``ProgressaoProvider._atualizarSequencia``),
    reproduzida aqui para o servidor ser a fonte autoritativa:

    - primeiro dia → 1;
    - jogou no dia seguinte (gap = 1) → **+1**;
    - faltou alguns dias (gap > 1) → **decai** ``gap-1``, nunca abaixo de 1
      (não zera: a chama é gentil).

    Como os dias são DISTINTOS e ORDENADOS, o gap é sempre ≥ 1 (não há o caso
    "relógio voltou" daqui). Lista vazia → 0 (nunca jogou)."""
    seq = 0
    anterior: date | None = None
    for dia in dias:
        if anterior is None:
            seq = 1
        else:
            gap = (dia - anterior).days
            if gap == 1:
                seq += 1
            elif gap > 1:
                seq = max(1, seq - (gap - 1))
        anterior = dia
    return seq


def _versoes_do_motor(bruto: Any) -> Any:
    """Normaliza `co_versao_motor` para a forma composta `dart_X[|rust_Y]`.

    Desde a migracao `0014` a coluna guarda as versoes dos DOIS motores:
    `dart_1.1.0|rust_0.2.0`, ou `dart_1.1.0` quando o aparelho nao tinha o
    binario nativo.

    (!) **Isto existe para a invariante nao depender de qual build sincronizou.**
    Uma build anterior a 27/08/2026 manda `1.1.0` — a versao do Dart, sem
    prefixo. Deixa-la passar daria DUAS formas na mesma coluna, e todo
    `split_part` teria de adivinhar qual esta lendo. Prefixando aqui, a regra
    *"toda linha e `dart_X` ou `dart_X|rust_Y`"* vale sempre.

    Nao e reescrever o que o app disse: aquela build so conhecia o motor Dart, e
    `dart_1.1.0` diz exatamente isso, por extenso.
    """
    if not isinstance(bruto, str) or not bruto:
        return bruto
    # Ja composto? O prefixo do primeiro pedaco denuncia.
    if bruto.split("|", 1)[0].startswith("dart_"):
        return bruto
    return f"dart_{bruto}"


class RepositorioSincronizacao:
    """Acesso a partidas/jogadas/XP/progressão para a sincronização.

    Recebe a [AsyncSession] da requisição. Faz `flush` (para o RETURNING) mas
    NÃO faz `commit` — quem orquestra a transação é a rota (tudo atômico).
    """

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Ingestão de um evento de partida (idempotente por co_evento) ──────────

    async def gravar_evento(
        self,
        *,
        id_usuario: str,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava a partida + jogadas + extensão Pontinhos + XP e incrementa a
        progressão, tudo na transação da requisição. Idempotente: se o
        ``co_evento`` já existe, não faz nada e devolve ``False``.

        ⚠️ O app **ainda pode enviar** ``co_anonimo`` no payload da partida, mas a
        coluna **não existe mais** (migração 0007) e o campo é **ignorado**. Quem
        identifica o dono é o ``id_usuario`` do token — e ele já é um pseudônimo
        (a exclusão de conta ANONIMIZA a linha, não a deleta). Apps antigos em
        campo continuam funcionando: o campo extra do payload simplesmente não é
        lido.
        """
        partida = payload.get("partida") or {}

        # 1) Partida (raiz do evento). ON CONFLICT no co_evento garante o dedupe.
        #    O id_usuario é SEMPRE o do token (ignora qualquer valor do cliente).
        sql_partida = text(
            """
            INSERT INTO partida.tb001_partida
              (id_partida, co_evento, co_jogo, co_variante, co_modo, id_usuario,
               id_usuario_j2, co_dificuldade, nu_placar_j1,
               nu_placar_j2, ic_pontua, co_status, co_lote_migracao,
               dh_inicio, dh_fim, nu_offset_minuto_j1, nu_offset_minuto_j2,
               qt_usos_poder)
            VALUES
              (:id_partida, :co_evento, :co_jogo, :co_variante, :co_modo,
               :id_usuario, :id_usuario_j2, :co_dificuldade,
               :nu_placar_j1, :nu_placar_j2, :ic_pontua, :co_status,
               :co_lote_migracao, :dh_inicio, :dh_fim,
               :nu_offset_minuto_j1, :nu_offset_minuto_j2,
               :qt_usos_poder)
            ON CONFLICT (co_evento) DO NOTHING
            RETURNING id_partida
            """
        )
        resultado = await self.sessao.execute(
            sql_partida,
            {
                "id_partida": partida.get("id_partida"),
                "co_evento": co_evento,
                "co_jogo": partida.get("co_jogo"),
                "co_variante": partida.get("co_variante"),
                "co_modo": partida.get("co_modo"),
                "id_usuario": id_usuario,
                "id_usuario_j2": partida.get("id_usuario_j2"),
                "co_dificuldade": partida.get("co_dificuldade"),
                "nu_placar_j1": partida.get("nu_placar_j1", 0),
                "nu_placar_j2": partida.get("nu_placar_j2", 0),
                "ic_pontua": partida.get("ic_pontua", False),
                "co_status": partida.get("co_status", "concluida"),
                "co_lote_migracao": partida.get("co_lote_migracao"),
                # asyncpg exige datetime (não string ISO) para timestamptz.
                "dh_inicio": _dt(partida.get("dh_inicio")),
                "dh_fim": _dt(partida.get("dh_fim")),
                # Fuso do jogador no momento da partida (offset UTC em MINUTOS).
                # OPCIONAIS: o app só passa a enviá-los na próxima versão, e as
                # versões já publicadas continuam funcionando (viram NULL).
                # Necessários porque `timestamptz` guarda o INSTANTE, não o fuso
                # de origem — sem eles não dá para saber que a partida foi jogada
                # "às 21h da noite do jogador".
                "nu_offset_minuto_j1": _offset(partida.get("nu_offset_minuto_j1")),
                "nu_offset_minuto_j2": _offset(partida.get("nu_offset_minuto_j2")),
                # Quantos USOS de poder houve nesta partida (T204).
                #
                # ⚠️ **`0` no default, e nao `None`.** A coluna e `NOT NULL
                # DEFAULT 0`, e a ausencia da chave significa exatamente zero: o
                # app que nao a envia e o app que nao tem o recurso. E `0` e o
                # que faz `qt_usos_poder = 0` ser um filtro utilizavel para a
                # reputacao do Magno (T208) sem `COALESCE` em toda consulta.
                #
                # ⚠️ **Conta USOS, e nao jogadas canceladas** — um uso de
                # "voltar jogada" desfaz duas jogadas, e um poder futuro pode nao
                # desfazer nenhuma.
                "qt_usos_poder": _inteiro_nao_negativo(partida.get("qt_usos_poder")),
            },
        )
        if resultado.first() is None:
            return False  # co_evento já existia → retry no-op

        id_partida = partida.get("id_partida")

        # 1b) Extensão de PARTIDA, quando o jogo tiver uma.
        #
        # ⚠️ **As damas são o PRIMEIRO caso do app.** Até 20/08/2026 nenhum jogo
        # tinha extensão de partida — Pontinhos e velha só estendem a *jogada* —,
        # e é por isso que este bloco não existia. Ele vem **depois** do INSERT
        # da partida genérica porque a FK aponta para ela, e **antes** das
        # jogadas porque as recusas (que viajam dentro dele) referenciam a
        # partida, não a jogada.
        damas_da_partida = partida.get("damas")
        if damas_da_partida:
            await self._gravar_partida_damas(id_partida, damas_da_partida)

        # Uma extensão de partida que não é nenhuma das conhecidas: registra e
        # segue. Mesma regra da jogada (V-5) — ignorar perde o detalhe, rejeitar
        # perderia a partida.
        _avisar_extensao_de_partida_desconhecida(partida)

        # 2) Jogadas (genéricas) + extensão do Pontinhos, na ordem recebida.
        for jogada in payload.get("jogadas", []):
            await self._gravar_jogada(id_partida, jogada)

        # 3) Parcelas de XP da partida.
        for parcela in payload.get("xp", []):
            await self._gravar_xp(id_partida, id_usuario, parcela)

        # 4) Incrementa a progressão (só se a partida pontua).
        await self._incrementar_progressao(id_usuario, partida, payload.get("xp", []))
        return True

    async def _gravar_jogada(self, id_partida: str, jogada: dict[str, Any]) -> None:
        # O app envia a STRING (`'cpu'`); a coluna guarda o NÚMERO. A dimensão faz
        # a tradução. Código que não existe vira 9999 (em vez de estourar a FK com
        # 500 e travar a fila de sincronização do aparelho para sempre).
        nu_origem, _ = await dimensoes.resolver(
            self.sessao,
            "origem_decisao",
            jogada.get("co_origem_decisao", "humano"),
        )
        await self.sessao.execute(
            text(
                """
                INSERT INTO partida.tb002_jogada
                  (id_jogada, id_partida, nu_ordem, nu_jogador, dh_jogada,
                   nu_timer_ms, nu_tempo_decisao_ms, nu_origem_decisao,
                   nu_lance, ic_cancelada, co_poder, dh_cancelamento)
                VALUES
                  (:id_jogada, :id_partida, :nu_ordem, :nu_jogador, :dh_jogada,
                   :nu_timer_ms, :nu_tempo_decisao_ms, :nu_origem_decisao,
                   :nu_lance, :ic_cancelada, :co_poder, :dh_cancelamento)
                """
            ),
            {
                "id_jogada": jogada.get("id_jogada"),
                "id_partida": id_partida,
                "nu_ordem": jogada.get("nu_ordem"),
                "nu_jogador": jogada.get("nu_jogador"),
                "dh_jogada": _dt(jogada.get("dh_jogada")),
                "nu_timer_ms": jogada.get("nu_timer_ms"),
                "nu_tempo_decisao_ms": jogada.get("nu_tempo_decisao_ms", 0),
                "nu_origem_decisao": nu_origem,
                # ── O poder "voltar jogada" (T203) ─────────────────────────
                #
                # ⚠️ **`nu_lance` NAO e `nu_ordem`, e a coluna fica NULA quando o
                # app nao a manda.** `nu_ordem` e sequencia continua de EVENTOS
                # (nunca recua, nunca repete — a tabela tem `UNIQUE (id_partida,
                # nu_ordem)`); `nu_lance` e o numero do lance no TABULEIRO, que
                # recua junto com o desfazer. Nos jogos sem poder os dois sao
                # iguais, e a view entrega `COALESCE(nu_lance, nu_ordem)` pronto
                # em `nu_lance_efetivo`.
                #
                # Preencher aqui com `nu_ordem` seria tentador e errado: passaria
                # a afirmar que o app **disse** qual era o lance, quando ele nao
                # disse — e no dia em que um jogo enviasse os dois diferentes
                # ninguem saberia distinguir o valor real do inventado.
                "nu_lance": jogada.get("nu_lance"),
                # As tres do cancelamento chegam JUNTAS ou nenhuma — o app tem o
                # mesmo `assert`, e a tabela tem o CHECK
                # `ck_jogada_cancelamento_completo`. Aqui o default e o caso
                # comum: a jogada nao foi desfeita.
                "ic_cancelada": bool(jogada.get("ic_cancelada", False)),
                "co_poder": jogada.get("co_poder"),
                "dh_cancelamento": _dt(jogada.get("dh_cancelamento")),
            },
        )
        # Extensão específica do JOGO (1:1), quando presente no payload.
        #
        # ⚠️ **Chave desconhecida é IGNORADA, nunca rejeitada** (decisão V-5 de
        # `specs/007-jogo-da-velha/data-model.md`, e diretriz do dono em
        # 2026-08-06: nada do jogo novo pode quebrar quem está com o app antigo).
        #
        # O motivo é assimétrico e é o que decide: rejeitar faz o app
        # **descartar o evento inteiro** — contrato escrito no próprio
        # `validacao.py` — jogando fora a **partida completa** do usuário para
        # não perder um detalhe que este backend não saberia guardar de todo
        # modo. Ignorar perde o detalhe; rejeitar perde a partida.
        pontinhos = jogada.get("pontinhos")
        if pontinhos:
            await self._gravar_jogada_pontinhos(jogada.get("id_jogada"), pontinhos)

        velha = jogada.get("velha")
        if velha:
            await self._gravar_jogada_velha(jogada.get("id_jogada"), velha)

        damas = jogada.get("damas")
        if damas:
            await self._gravar_jogada_damas(jogada.get("id_jogada"), damas)

        # Uma extensão que não é nenhuma das conhecidas: registra e segue.
        _avisar_extensao_desconhecida(jogada)

    async def _gravar_jogada_pontinhos(
        self, id_jogada: Any, pontinhos: dict[str, Any]
    ) -> None:
        """Telemetria do Pontinhos (1:1 com a jogada genérica).

        ⚠️ O app **ainda envia** `ar_tabuleiro_antes`/`ar_tabuleiro_apos`, mas essas
        colunas **não existem mais** (migração 0006). Nós as **ignoramos em
        silêncio**: o tabuleiro é RECONSTRUÍDO da sequência de arestas
        (`reconstrutor_partida_pontinhos.py`), e guardá-lo era pagar disco por algo
        derivável (~316 B por lance — o maior corte de espaço do redesenho).
        Ignorar em vez de rejeitar é o que permite este backend subir ANTES do app.
        """
        nu_acao, acao_desconhecida = await dimensoes.resolver(
            self.sessao, "acao", pontinhos.get("co_acao")
        )
        nu_situacao, situacao_desconhecida = await dimensoes.resolver(
            self.sessao, "situacao", pontinhos.get("co_situacao")
        )

        # Se o código não existe na dimensão, a coluna guarda 9999 — mas a string
        # CRUA não pode se perder: é a única pista do que precisa ser cadastrado.
        js_extra = pontinhos.get("js_extra")
        if acao_desconhecida or situacao_desconhecida:
            js_extra = dict(js_extra) if isinstance(js_extra, dict) else {}
            if acao_desconhecida:
                js_extra["co_acao_desconhecido"] = pontinhos.get("co_acao")
            if situacao_desconhecida:
                js_extra["co_situacao_desconhecido"] = pontinhos.get("co_situacao")

        await self.sessao.execute(
            text(
                """
                INSERT INTO jogo_pontinhos.tb002_jogada
                  (id_jogada, co_jogador, co_aresta, nu_caixas_fechadas,
                   nu_acao, nu_situacao, ar_probabilidade_cnn, ar_score_busca,
                   nu_profundidade, js_extra)
                VALUES
                  (:id_jogada, :co_jogador, :co_aresta, :nu_caixas,
                   :nu_acao, :nu_situacao, :ar_prob, :ar_score,
                   :nu_prof, :js_extra)
                """
            ),
            {
                "id_jogada": id_jogada,
                # ±1: valores CONTRATUAIS (aparecem na matriz da CNN). Não mexer.
                "co_jogador": pontinhos.get("co_jogador"),
                # Sem as matrizes, ESTA é a coluna mais crítica da tabela: é dela
                # que o tabuleiro inteiro é reconstruído.
                "co_aresta": pontinhos.get("co_aresta"),
                "nu_caixas": pontinhos.get("nu_caixas_fechadas", 0),
                "nu_acao": nu_acao,
                "nu_situacao": nu_situacao,
                "ar_prob": pontinhos.get("ar_probabilidade_cnn"),
                "ar_score": pontinhos.get("ar_score_busca"),
                "nu_prof": pontinhos.get("nu_profundidade"),
                # ⚠️ asyncpg quer uma STRING JSON para JSONB (não um dict Python) —
                # passar o dict cru levanta DataError e vira 500.
                "js_extra": json.dumps(js_extra) if js_extra is not None else None,
            },
        )

    async def _gravar_jogada_velha(self, id_jogada: Any, velha: dict) -> None:
        """Extensao do Jogo da Velha (1:1 com a jogada generica).

        Muito menor que a irma do Pontinhos, e de proposito: **nao ha treino**
        (RF-VLH-007). A velha e minimax exato no proprio aparelho, nao CNN, entao
        nao existe softmax, score de busca nem profundidade a guardar. O que
        sobra e o que permite AUDITAR:

        - **`ic_otimo`** — dele depende o XP (RF-VLH-045/046). Um numero que
          decide recompensa e nao e verificavel no servidor e a palavra do
          aparelho.
        - **`co_celula` + `nu_ordem`** — com os dois, a partida inteira se
          remonta para o suporte.

        ⚠️ `ic_otimo` chega `None` para lances da CPU, e a coluna e anulavel de
        proposito (V-4): `False` significaria "a CPU jogou mal" e falsearia
        qualquer analise de qualidade feita sobre esta tabela.
        """
        # ⚠️ A dimensao e a **da velha**, nao a generica `"acao"`. Usar a antiga
        # faria toda acao deste jogo ser procurada na tabela do Pontinhos, cair
        # no sentinela 9999, e a telemetria do jogo novo nascer cega.
        nu_acao, acao_desconhecida = await dimensoes.resolver(
            self.sessao, "acao_velha", velha.get("co_acao")
        )

        # Codigo fora da dimensao: a coluna guarda 9999, mas a string CRUA nao
        # pode se perder — e a unica pista do que precisa ser cadastrado.
        js_extra = velha.get("js_extra")
        if acao_desconhecida:
            js_extra = dict(js_extra) if isinstance(js_extra, dict) else {}
            js_extra["co_acao_desconhecido"] = velha.get("co_acao")

        await self.sessao.execute(
            text(
                """
                INSERT INTO jogo_velha.tb002_jogada
                  (id_jogada, co_jogador, co_celula, ic_otimo, nu_acao, js_extra)
                VALUES
                  (:id_jogada, :co_jogador, :co_celula, :ic_otimo, :nu_acao,
                   :js_extra)
                """
            ),
            {
                "id_jogada": id_jogada,
                # +1 / -1: o SINAL, como no Pontinhos. O generico usa 1/2.
                "co_jogador": velha.get("co_jogador"),
                "co_celula": velha.get("co_celula"),
                "ic_otimo": velha.get("ic_otimo"),
                "nu_acao": nu_acao,
                # asyncpg quer uma STRING JSON para JSONB (nao um dict Python) —
                # passar o dict cru levanta DataError e vira 500.
                "js_extra": json.dumps(js_extra) if js_extra is not None else None,
            },
        )

    async def _gravar_partida_damas(self, id_partida: Any, damas: dict) -> None:
        """Extensao de PARTIDA das damas — a primeira do app (RF-DAM-115g).

        **Por que uma partida precisa de extensao, se as outras nao precisaram.**
        Porque o replay das damas depende de saber COM QUAL MOTOR ela foi jogada.
        Uma regra corrigida muda a lista de lances legais; um replay rodado com
        motor diferente reconstroi uma partida que **nunca aconteceu**, e nada no
        dado denuncia. `co_versao_motor` e `co_versao_contrato` sao o carimbo que
        impede isso.

        **As recusas viajam DENTRO deste objeto** (decisao D-23), e nao como
        chave de raiz do payload: a raiz nao e do jogo. Se fosse, ou o nucleo
        aprenderia o que e uma recusa — que nem todo jogo tem —, ou uma extensao
        poderia sobrescrever `partida`, `jogadas` ou `xp` sem que nada acusasse.
        """
        await self.sessao.execute(
            text(
                """
                INSERT INTO jogo_damas.tb001_partida
                  (id_partida, co_versao_motor, co_versao_contrato,
                   co_fen_inicial, co_cor_j1, nu_semente_partida, js_extra)
                VALUES
                  (:id_partida, :co_versao_motor, :co_versao_contrato,
                   :co_fen_inicial, :co_cor_j1, :nu_semente_partida, :js_extra)
                """
            ),
            {
                "id_partida": id_partida,
                "co_versao_motor": _versoes_do_motor(damas.get("co_versao_motor")),
                "co_versao_contrato": damas.get("co_versao_contrato"),
                "co_fen_inicial": damas.get("co_fen_inicial"),
                # ⚠️ O banco fala 'branca'/'preta', nunca 'azul'/'vermelho'. A
                # cor do tema muda; a cor das damas nao muda ha duzentos anos.
                "co_cor_j1": damas.get("co_cor_j1"),
                "nu_semente_partida": damas.get("nu_semente_partida"),
                # asyncpg quer uma STRING JSON para JSONB (nao um dict Python) —
                # passar o dict cru levanta DataError e vira 500.
                "js_extra": (
                    json.dumps(damas["js_extra"])
                    if damas.get("js_extra") is not None
                    else None
                ),
            },
        )

        await self._gravar_recusas_damas(id_partida, damas.get("recusas") or [])

    async def _gravar_recusas_damas(self, id_partida: Any, recusas: list) -> None:
        """As tentativas que a REGRA barrou (RF-DAM-115j/115k/115l).

        **Por que uma tabela propria.** Uma recusa nao tem ordem propria — varias
        acontecem antes de um unico lance efetivado — e `partida.tb002_jogada`
        tem `UNIQUE (id_partida, nu_ordem)`. Enfia-las ali quebraria a chave.

        ⚠️ **A recusa pode ser ORFA, por construcao.** O `nu_ordem` dela aponta
        para um lance que ainda nao existe quando ela e gravada, e que pode nunca
        existir — se a pessoa abandonar a partida logo depois. Por isso a FK e
        para a PARTIDA, e por isso um `JOIN` com as jogadas precisa ser `LEFT`.
        E sao exatamente essas recusas orfas as mais interessantes: recusa
        seguida de abandono e o sintoma mais forte de recusa **indevida**.
        """
        if len(recusas) > _TETO_DE_RECUSAS_POR_PARTIDA:
            logger.warning(
                "Partida %s enviou %d recusas; o teto e %d. As excedentes foram "
                "DESCARTADAS (o evento segue aceito). O app ja conta o proprio "
                "teto: receber mais que isso sugere defeito em laco na tela.",
                id_partida,
                len(recusas),
                _TETO_DE_RECUSAS_POR_PARTIDA,
            )
            recusas = recusas[:_TETO_DE_RECUSAS_POR_PARTIDA]

        for recusa in recusas:
            # O app manda a STRING (`'captura_obrigatoria'`); a coluna guarda o
            # NUMERO. Codigo que este backend nao conhece vira 9999 em vez de
            # estourar a FK com 500 e travar a fila do aparelho para sempre.
            nu_regra, _ = await dimensoes.resolver(
                self.sessao, "regra_recusa_damas", recusa.get("co_regra")
            )
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO jogo_damas.tb003_recusa
                      (id_recusa, id_partida, nu_ordem, nu_sequencia,
                       nu_casa_origem, nu_casa_destino, nu_regra, dh_recusa)
                    VALUES
                      (:id_recusa, :id_partida, :nu_ordem, :nu_sequencia,
                       :nu_casa_origem, :nu_casa_destino, :nu_regra, :dh_recusa)
                    ON CONFLICT (id_partida, nu_ordem, nu_sequencia) DO NOTHING
                    """
                ),
                {
                    # ⚠️ O `id_recusa` e gerado AQUI: o payload nao o traz, porque
                    # a recusa nao precisa de identidade no aparelho — ela nunca
                    # e referenciada por nada. Gerar em Python (e nao com
                    # `gen_random_uuid()`) evita depender de extensao do Postgres.
                    "id_recusa": str(uuid.uuid4()),
                    "id_partida": id_partida,
                    "nu_ordem": recusa.get("nu_ordem"),
                    "nu_sequencia": recusa.get("nu_sequencia"),
                    "nu_casa_origem": recusa.get("nu_casa_origem"),
                    "nu_casa_destino": recusa.get("nu_casa_destino"),
                    "nu_regra": nu_regra or dimensoes.NU_DESCONHECIDO,
                    "dh_recusa": _dt(recusa.get("dh_recusa")),
                },
            )

    async def _gravar_jogada_damas(self, id_jogada: Any, damas: dict) -> None:
        """Extensao de JOGADA das damas — uma linha por LANCE (RF-DAM-114/115e).

        ⚠️ **Por LANCE, nao por salto.** Uma captura tripla e UM lance, e o
        caminho inteiro cabe em `co_lance` (`18x9x2`). Quem come tres pecas pousa
        em tres casas — o `x` separa as CASAS por onde a peca passou, nao as
        pecas capturadas.

        ⚠️ **A telemetria chega `None` no lance HUMANO**, e as colunas sao
        anulaveis de proposito. Nao ha busca a medir, e um zero gravado falsearia
        qualquer media feita sobre esta tabela. `NULL` significa "nao se aplica",
        que e a verdade — mesma logica do `ic_otimo` da velha.
        """
        # A dimensao e a **das damas**. Usar a de outro jogo faria todo motivo de
        # parada ser procurado na tabela errada e cair no sentinela — a
        # telemetria nasceria cega, sem erro e sem log de falha.
        nu_motivo, motivo_desconhecido = await dimensoes.resolver(
            self.sessao, "motivo_parada_damas", damas.get("co_motivo_parada_busca")
        )

        # Codigo fora da dimensao: a coluna guarda 9999, mas a string CRUA nao
        # pode se perder — e a unica pista do que precisa ser cadastrado.
        js_extra = damas.get("js_extra")
        if motivo_desconhecido:
            js_extra = dict(js_extra) if isinstance(js_extra, dict) else {}
            js_extra["co_motivo_parada_busca_desconhecido"] = damas.get(
                "co_motivo_parada_busca"
            )

        await self.sessao.execute(
            text(
                """
                INSERT INTO jogo_damas.tb002_jogada
                  (id_jogada, co_jogador, co_lance, co_fen_antes,
                   qt_captura_pedra, qt_captura_dama, ic_promoveu,
                   co_tipo_peca_inicio, qt_nos_visitados,
                   nu_profundidade_atingida, nu_motivo_parada_busca,
                   nu_tempo_busca_ms, nu_avaliacao_brancas, nu_semente,
                   co_motor_busca, qt_consultas_base, qt_acertos_base,
                   js_extra)
                VALUES
                  (:id_jogada, :co_jogador, :co_lance, :co_fen_antes,
                   :qt_captura_pedra, :qt_captura_dama, :ic_promoveu,
                   :co_tipo_peca_inicio, :qt_nos_visitados,
                   :nu_profundidade_atingida, :nu_motivo_parada_busca,
                   :nu_tempo_busca_ms, :nu_avaliacao_brancas, :nu_semente,
                   :co_motor_busca, :qt_consultas_base, :qt_acertos_base,
                   :js_extra)
                """
            ),
            {
                "id_jogada": id_jogada,
                # +1 / -1: o SINAL, como no Pontinhos e na velha. O generico
                # usa 1/2. Sao convencoes diferentes de proposito.
                "co_jogador": damas.get("co_jogador"),
                "co_lance": damas.get("co_lance"),
                # Qual motor escolheu o lance: 'dart' ou 'rust'.
                #
                # ⚠️ Nao ha `.get(..., "dart")` aqui, e e de proposito: um padrao
                # faria toda jogada de um app antigo — que nao manda o campo —
                # ser gravada como Dart, o que por acaso ate seria verdade hoje.
                # No dia em que deixasse de ser, a gestao de defeitos estaria
                # olhando um dado inventado sem nada denunciar. `None` significa
                # "este app nao disse", que e a verdade.
                "co_motor_busca": damas.get("co_motor_busca"),
                "co_fen_antes": damas.get("co_fen_antes"),
                # ⚠️ Decompostas (V-8), e nunca um total com um subconjunto:
                # somar duas colunas e trivial, separar depois e impossivel.
                "qt_captura_pedra": damas.get("qt_captura_pedra", 0),
                "qt_captura_dama": damas.get("qt_captura_dama", 0),
                "ic_promoveu": damas.get("ic_promoveu", False),
                # O que a peca ERA ao COMECAR o lance. Uma pedra que come tres e
                # coroa no ultimo salto grava 'pedra' + ic_promoveu=true.
                "co_tipo_peca_inicio": damas.get("co_tipo_peca_inicio"),
                "qt_nos_visitados": damas.get("qt_nos_visitados"),
                "nu_profundidade_atingida": damas.get("nu_profundidade_atingida"),
                "nu_motivo_parada_busca": nu_motivo,
                "nu_tempo_busca_ms": damas.get("nu_tempo_busca_ms"),
                # ⚠️ Centesimos de pedra, no referencial das BRANCAS sempre —
                # quando quem move e preto, o app ja manda o valor invertido
                # (invariante I-12). E e a nota da BUSCA, nao a avaliacao
                # estatica da posicao de `co_fen_antes` (V-11).
                "nu_avaliacao_brancas": damas.get("nu_avaliacao_brancas"),
                # Sem ela o replay nao reproduz — e e justamente nos niveis que
                # ERRAM DE PROPOSITO que a semente decide o resultado.
                "nu_semente": damas.get("nu_semente"),
                # O *probing* da base de finais: quantas vezes a busca perguntou
                # a base neste lance, e quantas dessas perguntas tiveram
                # resposta. E a RAZAO entre os dois que diz se consultar durante
                # a busca se paga.
                #
                # ⚠️ **Sem default, e `None` nao e `0`.** `None` = "nao houve
                # busca" (lance do humano, lance unico, lance vindo pronto da
                # base); `0` = "houve busca e ela nao consultou uma vez sequer",
                # que e o estado normal com o probing desligado. Um `.get(..., 0)`
                # aqui apagaria a distincao e faria toda media incluir lances em
                # que busca nenhuma aconteceu.
                "qt_consultas_base": damas.get("qt_consultas_base"),
                "qt_acertos_base": damas.get("qt_acertos_base"),
                "js_extra": json.dumps(js_extra) if js_extra is not None else None,
            },
        )

    async def _gravar_xp(
        self,
        id_partida: str,
        id_usuario: str,
        parcela: dict[str, Any],
    ) -> None:
        # String do app → chave numérica da dimensão (9999 se não existir).
        nu_tipo_xp, _ = await dimensoes.resolver(
            self.sessao, "tipo_xp", parcela.get("co_tipo_xp")
        )
        await self.sessao.execute(
            text(
                """
                INSERT INTO partida.tb003_xp_partida
                  (id_xp_partida, id_partida, id_usuario, nu_tipo_xp,
                   nu_xp, co_referencia, dh_registro)
                VALUES
                  (gen_random_uuid(), :id_partida, :id_usuario,
                   :nu_tipo_xp, :nu_xp, :co_referencia, now())
                """
            ),
            {
                "id_partida": id_partida,
                "id_usuario": id_usuario,
                # A coluna é NOT NULL: se a parcela vier sem tipo, 9999 preserva o
                # XP (que é o dado que importa) em vez de derrubar a partida.
                "nu_tipo_xp": nu_tipo_xp or dimensoes.NU_DESCONHECIDO,
                "nu_xp": parcela.get("nu_xp", 0),
                "co_referencia": parcela.get("co_referencia"),
            },
        )

    async def _incrementar_progressao(
        self,
        id_usuario: str,
        partida: dict[str, Any],
        xp: list[dict[str, Any]],
    ) -> None:
        # Partidas que NÃO pontuam (pvp_local) não mexem em XP/contadores.
        if not partida.get("ic_pontua"):
            return
        xp_ganho = sum(int(p.get("nu_xp", 0)) for p in xp)
        j1 = int(partida.get("nu_placar_j1", 0))
        j2 = int(partida.get("nu_placar_j2", 0))
        vit = 1 if j1 > j2 else 0
        der = 1 if j1 < j2 else 0
        emp = 1 if j1 == j2 else 0
        # Dia da partida (da data de fim, ou início): avança dt_ultimo_dia_jogado
        # sem nunca retroceder (GREATEST). Mantém a coluna "fresca" a cada partida
        # sincronizada, mesmo sem a reconciliação rodar.
        dia = _data(partida.get("dh_fim") or partida.get("dh_inicio"))
        # Upsert por id_usuario (única). NOTA: a "chama" (nu_sequencia_atual) NÃO
        # é recomputada aqui (depende de datas) — fica para o merge/reconciliação;
        # o app é a fonte da sequência até lá.
        # `AS prog`: alias do alvo para referenciar o valor ANTIGO no DO UPDATE
        # (o Postgres não aceita schema.tabela.coluna nesse contexto — precisa do
        # nome/alias da tabela).
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   dt_ultimo_dia_jogado, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :xp, 1, :vit,
                   :der, :emp, :dia, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total,
                  nu_partidas = prog.nu_partidas + 1,
                  nu_vitorias = prog.nu_vitorias + EXCLUDED.nu_vitorias,
                  nu_derrotas = prog.nu_derrotas + EXCLUDED.nu_derrotas,
                  nu_empates = prog.nu_empates + EXCLUDED.nu_empates,
                  -- GREATEST ignora NULL: nunca regride a última data jogada.
                  dt_ultimo_dia_jogado = GREATEST(
                      prog.dt_ultimo_dia_jogado, EXCLUDED.dt_ultimo_dia_jogado),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "xp": xp_ganho,
                "vit": vit,
                "der": der,
                "emp": emp,
                "dia": dia,
            },
        )

    # ── Merge convidado→conta (idempotente por co_lote_migracao) ──────────────

    async def aplicar_merge_se_novo(
        self,
        *,
        id_usuario: str,
        co_lote_migracao: str,
        progressao_convidado: dict[str, Any],
    ) -> bool:
        """Carimba o lote e, se for novo, soma a progressão do convidado à conta
        (XP/contadores somam; sequência fica a MAIOR; conquistas união).

        A identidade do convidado NÃO participa disto: o app manda o
        ``co_lote_migracao`` (que dá a idempotência) e os TOTAIS. O dono do
        resultado é sempre o ``id_usuario`` do token.
        """
        # 1) Registra o lote (idempotência). Se já existia, não aplica de novo.
        lote = await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb003_lote_migracao
                  (co_lote_migracao, id_usuario, dh_aplicado)
                VALUES (:lote, :id_usuario, now())
                ON CONFLICT (co_lote_migracao) DO NOTHING
                RETURNING co_lote_migracao
                """
            ),
            {"lote": co_lote_migracao, "id_usuario": id_usuario},
        )
        if lote.first() is None:
            return False  # lote já aplicado → no-op

        r = progressao_convidado
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   nu_sequencia_atual, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :xp, :part, :vit,
                   :der, :emp, :seq, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total,
                  nu_partidas = prog.nu_partidas + EXCLUDED.nu_partidas,
                  nu_vitorias = prog.nu_vitorias + EXCLUDED.nu_vitorias,
                  nu_derrotas = prog.nu_derrotas + EXCLUDED.nu_derrotas,
                  nu_empates = prog.nu_empates + EXCLUDED.nu_empates,
                  -- a "chama" não soma: fica a MAIOR das duas.
                  nu_sequencia_atual = GREATEST(
                      prog.nu_sequencia_atual, EXCLUDED.nu_sequencia_atual),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "xp": int(r.get("nu_xp_total", 0)),
                "part": int(r.get("nu_partidas", 0)),
                "vit": int(r.get("nu_vitorias", 0)),
                "der": int(r.get("nu_derrotas", 0)),
                "emp": int(r.get("nu_empates", 0)),
                "seq": int(r.get("nu_sequencia_atual", 0)),
            },
        )

        # Conquistas: união (a chave única id_usuario+co_conquista evita duplicar).
        for co_conquista in r.get("conquistas", []) or []:
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO progressao.tb002_conquista_usuario
                      (id_conquista_usuario, id_usuario, co_conquista,
                       dh_desbloqueio)
                    VALUES (gen_random_uuid(), :id_usuario, :co_conquista, now())
                    ON CONFLICT (id_usuario, co_conquista) DO NOTHING
                    """
                ),
                {"id_usuario": id_usuario, "co_conquista": co_conquista},
            )
        return True

    # ── Evento de CONQUISTA (idempotente por id_usuario + co_conquista) ───────

    async def gravar_conquista(
        self,
        *,
        id_usuario: str,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava UMA conquista desbloqueada. Idempotente pela chave natural
        ``(id_usuario, co_conquista)`` — reenviar o mesmo desbloqueio não duplica.
        O XP da conquista NÃO entra aqui (já sobe nas parcelas de XP da partida);
        esta linha é só o REGISTRO do desbloqueio. Devolve ``True`` se inseriu."""
        conquista = payload.get("conquista") or {}
        # Conflito: mantém a MENOR data de desbloqueio (a PRIMEIRA vez que o humano
        # a atingiu, em qualquer aparelho) — não a primeira a CHEGAR ao servidor.
        # `RETURNING (xmax = 0)`: xmax=0 só numa INSERÇÃO nova → distingue
        # "inseriu agora" (aceito) de "já existia/atualizou a data" (ignorado).
        resultado = await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb002_conquista_usuario AS tb
                  (id_conquista_usuario, id_usuario, co_conquista, dh_desbloqueio)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_conquista,
                   COALESCE(:dh, now()))
                ON CONFLICT (id_usuario, co_conquista) DO UPDATE SET
                  dh_desbloqueio = LEAST(tb.dh_desbloqueio, EXCLUDED.dh_desbloqueio)
                RETURNING (xmax = 0) AS inserido
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_conquista": conquista.get("co_conquista"),
                "dh": _dt(conquista.get("dh_desbloqueio")),
            },
        )
        return bool(resultado.scalar())

    # ── Reconciliação de progressão (fallback autoritativo — app é a verdade) ──

    async def reconciliar_progressao(
        self,
        *,
        id_usuario: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Aplica o snapshot AUTORITATIVO do app como REPARO: contadores sobem por
        ``GREATEST`` (nunca regridem — fecham o buraco de eventos perdidos sem
        duplicar), a "chama"/última data idem, e as conquistas entram por união.
        Roda quando a outbox está sem pendências, então o servidor já tem os
        eventos confirmados e o ``GREATEST`` é no-op quando nada se perdeu."""
        r = snapshot
        await self.sessao.execute(
            text(
                """
                INSERT INTO progressao.tb001_progressao_usuario AS prog
                  (id_progressao, id_usuario, nu_xp_total,
                   nu_partidas, nu_vitorias, nu_derrotas, nu_empates,
                   nu_sequencia_atual, dt_ultimo_dia_jogado, dh_atualizacao)
                VALUES
                  (gen_random_uuid(), :id_usuario, :xp, :part, :vit,
                   :der, :emp, :seq, :dia, now())
                ON CONFLICT (id_usuario) DO UPDATE SET
                  nu_xp_total = GREATEST(prog.nu_xp_total, EXCLUDED.nu_xp_total),
                  nu_partidas = GREATEST(prog.nu_partidas, EXCLUDED.nu_partidas),
                  nu_vitorias = GREATEST(prog.nu_vitorias, EXCLUDED.nu_vitorias),
                  nu_derrotas = GREATEST(prog.nu_derrotas, EXCLUDED.nu_derrotas),
                  nu_empates = GREATEST(prog.nu_empates, EXCLUDED.nu_empates),
                  nu_sequencia_atual = GREATEST(
                      prog.nu_sequencia_atual, EXCLUDED.nu_sequencia_atual),
                  dt_ultimo_dia_jogado = GREATEST(
                      prog.dt_ultimo_dia_jogado, EXCLUDED.dt_ultimo_dia_jogado),
                  dh_atualizacao = now()
                """
            ),
            {
                "id_usuario": id_usuario,
                "xp": int(r.get("nu_xp_total", 0)),
                "part": int(r.get("nu_partidas", 0)),
                "vit": int(r.get("nu_vitorias", 0)),
                "der": int(r.get("nu_derrotas", 0)),
                "emp": int(r.get("nu_empates", 0)),
                "seq": int(r.get("nu_sequencia_atual", 0)),
                "dia": _data(r.get("dt_ultimo_dia_jogado")),
            },
        )
        # Conquistas: união idempotente (mesma chave do merge).
        for co_conquista in r.get("conquistas", []) or []:
            await self.sessao.execute(
                text(
                    """
                    INSERT INTO progressao.tb002_conquista_usuario
                      (id_conquista_usuario, id_usuario, co_conquista,
                       dh_desbloqueio)
                    VALUES (gen_random_uuid(), :id_usuario, :co_conquista, now())
                    ON CONFLICT (id_usuario, co_conquista) DO NOTHING
                    """
                ),
                {"id_usuario": id_usuario, "co_conquista": co_conquista},
            )

    # ── Arquivo de eventos NÃO aplicados (diagnóstico) ───────────────────────

    # Teto do dump guardado no log: o payload é dado não-confiável; truncamos para
    # o log não virar vetor de inchaço do banco do servidor.
    _MAX_JS_LOG = 20_000

    async def arquivar_evento_rejeitado(
        self,
        *,
        id_usuario: str,
        co_evento: str | None,
        co_tipo: str | None,
        co_motivo: str,
        de_codigo: str | None,
        payload: Any,
    ) -> None:
        """Grava em ``log.tb001_evento_sync_rejeitado`` um evento que NÃO pôde ser
        aplicado (``co_motivo`` = ``rejeitado_contrato`` ou ``falha_processamento``).
        É append-only: nunca falha por duplicidade. O ``payload`` é serializado em
        texto e truncado (dado não-confiável)."""
        import json

        try:
            js = payload if isinstance(payload, str) else json.dumps(
                payload, ensure_ascii=False, default=str
            )
        except (TypeError, ValueError):
            # Payload bizarro que nem serializa: guarda a representação crua.
            js = repr(payload)
        js = js[: self._MAX_JS_LOG]
        de_codigo = de_codigo[:200] if isinstance(de_codigo, str) else de_codigo
        await self.sessao.execute(
            text(
                """
                INSERT INTO log.tb001_evento_sync_rejeitado
                  (id_log, id_usuario, co_evento, co_tipo, co_motivo,
                   de_codigo, js_payload, dh_registro)
                VALUES
                  (gen_random_uuid(), :id_usuario, :co_evento,
                   :co_tipo, :co_motivo, :de_codigo, :js_payload, now())
                """
            ),
            {
                "id_usuario": id_usuario,
                "co_evento": co_evento[:64] if isinstance(co_evento, str) else co_evento,
                "co_tipo": co_tipo[:30] if isinstance(co_tipo, str) else co_tipo,
                "co_motivo": co_motivo,
                "de_codigo": de_codigo,
                "js_payload": js,
            },
        )

    # ── Leitura (pela VIEW) ───────────────────────────────────────────────────

    async def registrar_atividade(self, id_usuario: str) -> None:
        """Carimba ``conta.tb001_usuario.dh_ultimo_acesso = now()`` a cada
        sincronização de partidas (``POST /eventos``). É o sinal CONFIÁVEL de
        "último acesso": o app reabre restaurando a sessão de forma ASSÍNCRONA e
        esse caminho nem sempre rechama ``/sessao`` — então depender só do login
        deixava a coluna parada (às vezes NULL) mesmo para quem joga todo dia."""
        await self.sessao.execute(
            text(
                "UPDATE conta.tb001_usuario SET dh_ultimo_acesso = now() "
                "WHERE id_usuario = :id"
            ),
            {"id": id_usuario},
        )

    async def recalcular_chama(
        self, id_usuario: str
    ) -> tuple[int, date | None, int]:
        """Recalcula a "chama" (sequência), o último dia jogado e o TOTAL de dias
        jogados de forma **AUTORITATIVA**, a partir dos DIAS LOCAIS distintos das
        partidas concluídas que pontuam (``vs_cpu``). Persiste sequência e data
        (SOBRESCREVE — não ``GREATEST`` — pois é a verdade derivada do histórico)
        e devolve ``(sequencia, ultimo_dia, total_de_dias)``.

        O **total de dias** é simplesmente ``len(dias)`` — a mesma lista que a
        sequência já usa, então sai de graça. Ele existe por causa do relato de
        12/08/2026: a conquista "10 Dias na Arena" nunca saía porque o contador
        equivalente do app (``diasJogadosTotal``) vive só no aparelho, dentro de
        ``js_estado_local``, e se perde quando o rascunho local é sobrescrito.
        Um número que o servidor sabe recalcular do histórico é reconstruível; um
        contador que só incrementa no aparelho, não. O app adota este por
        ``GREATEST`` e volta a merecer a conquista sem rejogar nada.

        É a **correção definitiva** do bug da chama: antes o "dia jogado" saía de
        ``dh_fim`` lido em **UTC**, então uma partida das 21h–23h no Brasil (BRT,
        UTC−3) caía no **dia seguinte** e a sequência nunca crescia. Aqui o dia é o
        dia do **relógio do jogador**, reconstruído com o offset gravado em cada
        partida (``nu_offset_minuto_j1``): ``(dh em UTC) + offset``.

        Se o jogador ainda não tem partidas que pontuam, **NÃO** mexe na linha
        (para não zerar uma sequência vinda de merge de convidado cujas partidas
        ainda não subiram) e devolve ``(0, None, 0)``."""
        resultado = await self.sessao.execute(
            text(
                """
                SELECT DISTINCT
                  ((COALESCE(dh_fim, dh_inicio) AT TIME ZONE 'UTC')
                     + make_interval(mins => COALESCE(nu_offset_minuto_j1, 0)))::date
                    AS dia
                FROM partida.tb001_partida
                WHERE id_usuario = :id
                  AND ic_pontua = true
                  AND co_status = 'concluida'
                ORDER BY dia
                """
            ),
            {"id": id_usuario},
        )
        dias = [linha[0] for linha in resultado.all()]
        if not dias:
            return (0, None, 0)
        seq = calcular_sequencia_de_dias(dias)
        ultimo = dias[-1]
        # Dias DIFERENTES jogados (dedicação). A consulta já traz DISTINCT, então
        # o tamanho da lista é o total — nada de consulta extra.
        total_dias = len(dias)
        # SOBRESCREVE (a verdade é o histórico). A linha existe: partidas que
        # pontuam sempre criam/atualizam a progressão em `_incrementar_progressao`.
        await self.sessao.execute(
            text(
                """
                UPDATE progressao.tb001_progressao_usuario
                SET nu_sequencia_atual = :seq,
                    dt_ultimo_dia_jogado = :dia,
                    dh_atualizacao = now()
                WHERE id_usuario = :id
                """
            ),
            {"id": id_usuario, "seq": seq, "dia": ultimo},
        )
        # O total de dias NÃO é persistido de propósito: ele é derivado do log e
        # recalculado a cada leitura, como a sequência. Guardá-lo exigiria uma
        # migração em produção para ganhar nada — e criaria uma segunda cópia da
        # mesma verdade, que é justamente a origem do defeito que isto conserta.
        return (seq, ultimo, total_dias)

    async def obter_progressao(self, id_usuario: str) -> dict[str, Any]:
        """Progressão atual (com nu_nivel/co_patente calculados pela VIEW) +
        a lista de conquistas. É o que o app PUXA para reconciliar o banco local
        (convergência multi-dispositivo). Se o usuário ainda não tem linha,
        devolve zeros (mas ainda lê as conquistas, que podem existir sem linha).

        A **chama** é recomputada aqui de forma autoritativa (ver
        [recalcular_chama]) para todo mundo se auto-corrigir na próxima leitura —
        inclusive retroativamente."""
        conquistas = await self._conquistas_de(id_usuario)
        resultado = await self.sessao.execute(
            text(
                "SELECT * FROM progressao.vw001_progressao_usuario "
                "WHERE id_usuario = :id"
            ),
            {"id": id_usuario},
        )
        linha = resultado.mappings().first()
        if linha is None:
            return {
                "nu_xp_total": 0,
                "nu_partidas": 0,
                "nu_vitorias": 0,
                "nu_derrotas": 0,
                "nu_empates": 0,
                "nu_sequencia_atual": 0,
                "dt_ultimo_dia_jogado": None,
                # Sem linha de progressão = sem partida que pontua = zero dias.
                "nu_dias_jogados": 0,
                "nu_nivel": 1,
                "co_patente": "aprendiz",
                "conquistas": conquistas,
            }
        saida = dict(linha)
        saida["conquistas"] = conquistas
        # Chama autoritativa (recomputa dos dias LOCAIS de jogo e sobrescreve).
        # A `saida` foi lida da VIEW ANTES do update, então refletimos aqui os
        # valores novos. Só sobrescreve quando há histórico (ultimo != None).
        seq, ultimo, total_dias = await self.recalcular_chama(id_usuario)
        # `nu_dias_jogados` é campo ADITIVO (2026-08-13): apps antigos em campo o
        # ignoram, como manda a diretriz de versionamento da API. Vai sempre —
        # inclusive zero — para o app não ter de distinguir "ausente" de "zero".
        saida["nu_dias_jogados"] = total_dias
        if ultimo is not None:
            saida["nu_sequencia_atual"] = seq
            saida["dt_ultimo_dia_jogado"] = ultimo
        return saida

    async def _conquistas_de(self, id_usuario: str) -> list[str]:
        """Ids das conquistas do usuário (ordenados, para resposta estável)."""
        resultado = await self.sessao.execute(
            text(
                "SELECT co_conquista FROM progressao.tb002_conquista_usuario "
                "WHERE id_usuario = :id ORDER BY co_conquista"
            ),
            {"id": id_usuario},
        )
        return [r[0] for r in resultado]
