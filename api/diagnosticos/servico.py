"""A regra do diagnóstico, separada da rota e do banco.

Por que existe uma camada aqui, se ela é fina: a rota fica responsável só pelo
HTTP (cabeçalhos, status, resposta) e este arquivo pelo **o quê** se grava. É o
mesmo desenho de `api/notificacoes/servico_preferencias.py`, e é o que permite
testar a rota sem Postgres nenhum — o teste troca o serviço por um fake, em uma
linha.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.diagnosticos.repositorio import RepositorioDiagnostico


class ServicoDiagnostico:
    """Registra relatos de motor nativo indisponível."""

    def __init__(
        self, repo: RepositorioDiagnostico, sessao: AsyncSession
    ) -> None:
        self.repo = repo
        self.sessao = sessao

    async def registrar_motor_nativo(
        self, uid: Optional[str], dados: dict[str, Any]
    ) -> tuple[str, int]:
        """Resolve o dono (se houver), grava e confirma a transação.

        Devolve `(id_diagnostico, qt_ocorrencias)`. O contador vem do UPSERT do
        repositório: `1` na primeira vez, e o total acumulado dali em diante —
        a tabela guarda **uma linha por configuração**, não uma por relato.

        [uid] é o identificador do Firebase, ou `None` para convidado. Três
        caminhos levam a um relato **sem dono**, e os três são legítimos:

        * não havia token (convidado);
        * o token era inválido ou estava expirado;
        * o token era válido, mas a pessoa ainda não completou o perfil — o uid
          existe no Firebase e a conta ainda não existe aqui.

        ⚠️ Em nenhum deles o relato é descartado. Um diagnóstico sem dono
        continua dizendo qual aparelho, qual ABI e qual build quebraram, que é
        tudo o que se precisa para consertar.
        """
        id_usuario = None
        if uid is not None:
            id_usuario = await self.repo.id_usuario_por_identidade(uid)

        id_diagnostico, ocorrencias = await self.repo.registrar_motor_nativo(
            {**dados, "id_usuario": id_usuario}
        )
        # O serviço é dono da transação — o repositório só escreve. Sem este
        # `commit` a linha morre junto com a sessão da requisição.
        await self.sessao.commit()
        return id_diagnostico, ocorrencias
