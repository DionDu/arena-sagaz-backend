"""Serviço de sincronização (spec 006 / US1 — T032/T033).

Orquestra a ingestão dos eventos da outbox do app e o merge convidado→conta.
A lógica de idempotência (por ``co_evento`` na ingestão e por
``co_lote_migracao`` no merge) é delegada ao repositório, que a garante numa
transação. Aqui ficam a orquestração e as validações de contrato.

O ``id_usuario`` do dono NUNCA vem do cliente: vem do token (resolvido em
``usuario_autenticado``), e é ele que o serviço usa para gravar/pontuar.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

from api.nucleo.dependencias_conta_nuvem import UsuarioAutenticado
from api.nucleo.excecoes import ErroNegocio
from api.sincronizacao.validacao import (
    MAX_EVENTOS_POR_LOTE,
    MAX_TAMANHO_CO_EVENTO,
    validar_evento,
    validar_progressao_convidado,
    validar_reconciliacao,
)

logger = logging.getLogger(__name__)


class RepositorioSincronizacaoProtocolo(Protocol):
    """Contrato do repositório usado pelo serviço (real em produção; fake nos
    testes de contrato). Definir como ``Protocol`` deixa o serviço testável sem
    banco."""

    async def gravar_evento(
        self,
        *,
        id_usuario: str,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava UM evento de partida de forma idempotente. Devolve ``True`` se
        inseriu (evento novo) ou ``False`` se já existia (retry — no-op)."""
        ...

    async def gravar_conquista(
        self,
        *,
        id_usuario: str,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava UMA conquista desbloqueada, idempotente por
        ``(id_usuario, co_conquista)``. Devolve ``True`` se inseriu."""
        ...

    async def reconciliar_progressao(
        self,
        *,
        id_usuario: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Aplica o snapshot autoritativo do app como reparo (GREATEST + união
        de conquistas). Não retorna nada — é um upsert de reconciliação."""
        ...

    async def aplicar_merge_se_novo(
        self,
        *,
        id_usuario: str,
        co_lote_migracao: str,
        progressao_convidado: dict[str, Any],
    ) -> bool:
        """Aplica o merge convidado→conta de forma idempotente por lote. Devolve
        ``True`` se aplicou ou ``False`` se o lote já havia sido aplicado."""
        ...

    async def obter_progressao(self, id_usuario: str) -> dict[str, Any]:
        """Progressão atual do usuário (dict pronto para a resposta)."""
        ...

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
        """Arquiva no log um evento que NÃO pôde ser aplicado (para diagnóstico).
        ``co_motivo`` = ``rejeitado_contrato`` (validação) ou ``falha_processamento``
        (exceção ao gravar). Nunca deve lançar por conteúdo do payload."""
        ...


class ServicoSincronizacao:
    """Casos de uso de sincronização. Recebe o repositório por injeção; guarda
    também a `sessao` (como o ServicoConta) para a ROTA confirmar a transação
    (`await servico.sessao.commit()`) — assim toda a ingestão é atômica."""

    def __init__(
        self,
        repo: RepositorioSincronizacaoProtocolo,
        sessao: Any = None,
    ) -> None:
        self.repo = repo
        self.sessao = sessao

    async def ingerir_eventos(
        self, usuario: UsuarioAutenticado, corpo: dict[str, Any]
    ) -> dict[str, Any]:
        """Ingesta um lote de eventos. Cada evento é aplicado no MÁXIMO uma vez
        (idempotência por ``co_evento``). Devolve aceitos/ignorados/**rejeitados**/
        **falhas** + a progressão reconciliada (fonte da verdade).

        **Blindagem por evento (à prova de bala):** um evento nunca derruba o lote.
        Há dois modos de "não aplicado", ambos ARQUIVADOS no log para diagnóstico e
        devolvidos ao app (que então EXPURGA o evento local — o servidor guarda a
        evidência):

        - **``rejeitados``** — reprovado na validação (malformado/fora dos tetos,
          SEG-05/06). Nem toca no repositório.
        - **``falhas``** — passou na validação mas EXPLODIU ao gravar. Cada gravação
          roda num **SAVEPOINT** (``begin_nested``): a exceção desfaz só ESSE evento
          (não o lote), é capturada e arquivada como ``falha_processamento``. Sem
          isso, um erro inesperado viraria **500** e o app reenviaria para sempre até
          o dead-letter (SEG-10)."""
        eventos = corpo.get("eventos")
        if not isinstance(eventos, list):
            raise ErroNegocio(
                "Corpo inválido: 'eventos' deve ser uma lista.",
                "eventos_invalidos",
                status_http=400,
            )
        # Teto do tamanho do lote (SEG-07): protege o banco de um único request que
        # geraria um número enorme de INSERTs.
        if len(eventos) > MAX_EVENTOS_POR_LOTE:
            raise ErroNegocio(
                f"Lote grande demais (máximo {MAX_EVENTOS_POR_LOTE} eventos).",
                "lote_grande_demais",
                status_http=413,
            )

        aceitos: list[str] = []
        ignorados: list[str] = []
        rejeitados: list[dict[str, Any]] = []
        falhas: list[str] = []
        for evento in eventos:
            eh_dict = isinstance(evento, dict)
            co_tipo = evento.get("co_tipo") if eh_dict else None

            # Valida ANTES de tocar no repositório: nada malformado/abusivo chega
            # ao SQL (evita 500 e injeção de XP).
            codigo = validar_evento(evento)
            if codigo is not None:
                ce = evento.get("co_evento") if eh_dict else None
                # Não devolve um co_evento gigante de volta (poda ao teto).
                if isinstance(ce, str):
                    ce = ce[:MAX_TAMANHO_CO_EVENTO]
                # Arquiva o rejeitado (o servidor já tem o payload em mãos).
                await self.repo.arquivar_evento_rejeitado(
                    id_usuario=usuario.id_usuario,
                    co_evento=ce,
                    co_tipo=co_tipo,
                    co_motivo="rejeitado_contrato",
                    de_codigo=codigo,
                    payload=(evento.get("payload") if eh_dict else evento),
                )
                rejeitados.append({"co_evento": ce, "codigo": codigo})
                continue

            co_evento = evento["co_evento"]
            payload = evento.get("payload") or {}
            try:
                # SAVEPOINT por evento: se a gravação explodir, desfaz SÓ este
                # evento (o lote e os eventos bons seguem íntegros).
                async with self.sessao.begin_nested():
                    # Despacha pelo tipo (ausente = "partida", retrocompatível).
                    if (co_tipo or "partida") == "conquista":
                        inserido = await self.repo.gravar_conquista(
                            id_usuario=usuario.id_usuario,
                            co_evento=co_evento,
                            payload=payload,
                        )
                    else:
                        inserido = await self.repo.gravar_evento(
                            id_usuario=usuario.id_usuario,
                            co_evento=co_evento,
                            payload=payload,
                        )
            except Exception as exc:  # noqa: BLE001 — blindagem por evento é o objetivo
                # O savepoint já reverteu este evento. Arquiva o payload cru (sem
                # re-rodar a lógica que falhou) e segue. `falhas` → o app expurga.
                await self.repo.arquivar_evento_rejeitado(
                    id_usuario=usuario.id_usuario,
                    co_evento=co_evento,
                    co_tipo=co_tipo,
                    co_motivo="falha_processamento",
                    de_codigo=f"{type(exc).__name__}: {exc}",
                    payload=payload,
                )
                falhas.append(co_evento)
                continue

            (aceitos if inserido else ignorados).append(co_evento)

        # Sincronizar partidas É "acessar": carimba o último acesso (a criação já
        # carimba; aqui cobrimos as reaberturas, que nem sempre rechamam /sessao).
        await self.repo.registrar_atividade(usuario.id_usuario)
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {
            "aceitos": aceitos,
            "ignorados": ignorados,
            "rejeitados": rejeitados,
            "falhas": falhas,
            "progressao": progressao,
        }

    async def merge_convidado(
        self, usuario: UsuarioAutenticado, corpo: dict[str, Any]
    ) -> dict[str, Any]:
        """Funde a progressão do convidado na conta, idempotente por
        ``co_lote_migracao``."""
        co_lote = corpo.get("co_lote_migracao")
        if (
            not isinstance(co_lote, str)
            or not co_lote
            or len(co_lote) > MAX_TAMANHO_CO_EVENTO
        ):
            raise ErroNegocio(
                "Corpo inválido: falta 'co_lote_migracao'.",
                "lote_ausente",
                status_http=400,
            )
        resumo = corpo.get("progressao_convidado") or {}

        # Tetos anti-fraude (SEG-05): sem isto, 1 request injeta XP infinito na
        # conta (o merge é o vetor mais perigoso). Recusa valores absurdos/forjados.
        codigo = validar_progressao_convidado(resumo)
        if codigo is not None:
            # A recusa fica registrada ANTES do 422 (T166 da spec 010) - ver
            # `_arquivar_recusa`. O lote vai no lugar do `co_evento`: é ele que
            # liga a linha do log ao convidado que tentou migrar.
            await self._arquivar_recusa(
                usuario,
                co_tipo="merge_convidado",
                co_evento=co_lote,
                codigo=codigo,
                payload=resumo,
            )
            raise ErroNegocio(
                "Progressão do convidado inválida ou fora dos limites.",
                codigo,
                status_http=422,
            )

        aplicado = await self.repo.aplicar_merge_se_novo(
            id_usuario=usuario.id_usuario,
            co_lote_migracao=co_lote,
            progressao_convidado=resumo,
        )
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {"aplicado": aplicado, "progressao": progressao}

    async def reconciliar_progressao(
        self, usuario: UsuarioAutenticado, corpo: dict[str, Any]
    ) -> dict[str, Any]:
        """Reconcilia (repara) a progressão do servidor com o snapshot
        autoritativo do app — o FALLBACK que garante que XP/conquistas não se
        percam quando um evento é abandonado (dead-letter) ou falha. Os mesmos
        tetos anti-fraude do merge valem aqui (o snapshot também é um vetor de
        injeção). Devolve a progressão resultante."""
        resumo = corpo.get("progressao") or {}
        codigo = validar_reconciliacao(resumo)
        if codigo is not None:
            # A recusa fica registrada ANTES do 422 (T166 da spec 010). A
            # reconciliação não tem identificador próprio: `co_evento` vai nulo.
            await self._arquivar_recusa(
                usuario,
                co_tipo="reconciliacao",
                co_evento=None,
                codigo=codigo,
                payload=resumo,
            )
            raise ErroNegocio(
                "Progressão inválida ou fora dos limites.",
                codigo,
                status_http=422,
            )
        await self.repo.reconciliar_progressao(
            id_usuario=usuario.id_usuario,
            snapshot=resumo,
        )
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {"progressao": progressao}

    async def _arquivar_recusa(
        self,
        usuario: UsuarioAutenticado,
        *,
        co_tipo: str,
        co_evento: str | None,
        codigo: str,
        payload: Any,
    ) -> None:
        """Registra em ``log.tb001_evento_sync_rejeitado`` a recusa (422) de um
        retrato de progressão - a reconciliação ou o merge do convidado.

        **Por que existe (T166 da spec 010, 30/10/2026).** Até aqui só os eventos
        do LOTE reprovados iam para o log. A recusa da reconciliação levantava o
        422 e não deixava rastro: em 9 contas do ``prd`` ela era recusada a cada
        sincronização (``progressao_inconsistente``), o bônus das conquistas nunca
        chegava ao ranking, e a tabela que o dono consultava estava vazia.

        **Por que faz ``commit`` aqui, e não na rota.** A rota só confirma a
        transação quando dá certo; com o 422, a sessão fecha sem ``commit`` e o
        banco desfaz tudo - inclusive esta linha. Confirmar aqui é seguro porque a
        validação é o PRIMEIRO passo dos dois casos de uso: neste instante não há
        outra escrita pendente na sessão além da do log.

        ⚠️ **O diagnóstico nunca troca a resposta.** Se arquivar ou confirmar
        falhar, a sessão é desfeita, o servidor anota um aviso, e quem chamou
        levanta o MESMO 422 de sempre - o app (inclusive a 1.3.1 em campo) não
        enxerga diferença nenhuma.

        As colunas seguem as linhas que o lote já grava: ``co_motivo`` é a
        categoria (``rejeitado_contrato``, a de toda reprovação na validação) e o
        código da ``validacao.py`` vai em ``de_codigo``; quem distingue a
        reconciliação do merge e das partidas é o ``co_tipo``.
        """
        try:
            await self.repo.arquivar_evento_rejeitado(
                id_usuario=usuario.id_usuario,
                co_evento=co_evento,
                co_tipo=co_tipo,
                co_motivo="rejeitado_contrato",
                de_codigo=codigo,
                payload=payload,
            )
            await self.sessao.commit()
        except Exception:  # noqa: BLE001 - o log não pode derrubar a resposta
            # `exception` anota a pilha no log do servidor (Railway). O
            # `rollback` limpa a sessão, que pode ter ficado num estado de erro.
            logger.exception(
                "Não foi possível arquivar a recusa de %s (%s)", co_tipo, codigo
            )
            try:
                await self.sessao.rollback()
            except Exception:  # noqa: BLE001
                logger.exception("O rollback depois do arquivamento falhou")

    async def estado(self, usuario: UsuarioAutenticado) -> dict[str, Any]:
        """Estado atual da progressão no servidor."""
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {"progressao": progressao}
