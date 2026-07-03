"""Serviço de sincronização (spec 006 / US1 — T032/T033).

Orquestra a ingestão dos eventos da outbox do app e o merge convidado→conta.
A lógica de idempotência (por ``co_evento`` na ingestão e por
``co_lote_migracao`` no merge) é delegada ao repositório, que a garante numa
transação. Aqui ficam a orquestração e as validações de contrato.

O ``id_usuario`` do dono NUNCA vem do cliente: vem do token (resolvido em
``usuario_autenticado``), e é ele que o serviço usa para gravar/pontuar.
"""
from __future__ import annotations

from typing import Any, Protocol

from api.nucleo.dependencias_conta_nuvem import UsuarioAutenticado
from api.nucleo.excecoes import ErroNegocio


class RepositorioSincronizacaoProtocolo(Protocol):
    """Contrato do repositório usado pelo serviço (real em produção; fake nos
    testes de contrato). Definir como ``Protocol`` deixa o serviço testável sem
    banco."""

    async def gravar_evento(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        """Grava UM evento de partida de forma idempotente. Devolve ``True`` se
        inseriu (evento novo) ou ``False`` se já existia (retry — no-op)."""
        ...

    async def aplicar_merge_se_novo(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_lote_migracao: str,
        progressao_convidado: dict[str, Any],
    ) -> bool:
        """Aplica o merge convidado→conta de forma idempotente por lote. Devolve
        ``True`` se aplicou ou ``False`` se o lote já havia sido aplicado."""
        ...

    async def obter_progressao(self, id_usuario: str) -> dict[str, Any]:
        """Progressão atual do usuário (dict pronto para a resposta)."""
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
        (idempotência por ``co_evento``). Devolve aceitos/ignorados + a
        progressão reconciliada (fonte da verdade)."""
        eventos = corpo.get("eventos")
        if not isinstance(eventos, list):
            raise ErroNegocio(
                "Corpo inválido: 'eventos' deve ser uma lista.",
                "eventos_invalidos",
                status_http=400,
            )

        aceitos: list[str] = []
        ignorados: list[str] = []
        for evento in eventos:
            co_evento = evento.get("co_evento")
            if not co_evento:
                raise ErroNegocio(
                    "Evento sem 'co_evento'.", "evento_sem_id", status_http=400
                )
            inserido = await self.repo.gravar_evento(
                id_usuario=usuario.id_usuario,
                co_anonimo=usuario.co_anonimo,
                co_evento=co_evento,
                payload=evento.get("payload") or {},
            )
            (aceitos if inserido else ignorados).append(co_evento)

        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {
            "aceitos": aceitos,
            "ignorados": ignorados,
            "progressao": progressao,
        }

    async def merge_convidado(
        self, usuario: UsuarioAutenticado, corpo: dict[str, Any]
    ) -> dict[str, Any]:
        """Funde a progressão do convidado na conta, idempotente por
        ``co_lote_migracao``."""
        co_lote = corpo.get("co_lote_migracao")
        if not co_lote:
            raise ErroNegocio(
                "Corpo inválido: falta 'co_lote_migracao'.",
                "lote_ausente",
                status_http=400,
            )
        resumo = corpo.get("progressao_convidado") or {}

        aplicado = await self.repo.aplicar_merge_se_novo(
            id_usuario=usuario.id_usuario,
            co_anonimo=usuario.co_anonimo,
            co_lote_migracao=co_lote,
            progressao_convidado=resumo,
        )
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {"aplicado": aplicado, "progressao": progressao}

    async def estado(self, usuario: UsuarioAutenticado) -> dict[str, Any]:
        """Estado atual da progressão no servidor."""
        progressao = await self.repo.obter_progressao(usuario.id_usuario)
        return {"progressao": progressao}
