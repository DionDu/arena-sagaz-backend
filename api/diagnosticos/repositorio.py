"""Acesso a `log.tb002_diagnostico_motor_nativo`.

Segue a regra de ouro do projeto: **escrita na tabela, leitura pela VIEW**, e
sempre com parâmetros nomeados (`:nome`) — nunca interpolação de string, que é
por onde entra SQL injection.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RepositorioDiagnostico:
    """Grava relatos de motor nativo indisponível."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def id_usuario_por_identidade(
        self, co_identidade_externa: str
    ) -> Optional[Any]:
        """Resolve o `id_usuario` interno a partir do `uid` do Firebase.

        `None` quando ainda não há conta para esse uid — e isso **não impede o
        registro**: o relato vale igual sem dono. Ver a regra 2 no cabeçalho da
        migração 0016.
        """
        sql = text(
            "SELECT id_usuario FROM conta.vw001_usuario "
            "WHERE co_identidade_externa = :uid"
        )
        resultado = await self.sessao.execute(sql, {"uid": co_identidade_externa})
        linha = resultado.mappings().first()
        return linha["id_usuario"] if linha else None

    async def registrar_motor_nativo(self, dados: dict[str, Any]) -> str:
        """Insere um relato e devolve o `id_diagnostico` gerado pelo banco.

        `RETURNING` traz de volta a chave que o `DEFAULT gen_random_uuid()`
        acabou de criar, numa viagem só — sem ele seria preciso gerar o UUID
        aqui e o banco deixaria de ser a fonte da chave.

        ⚠️ Escreve na **tabela**, não na view. Só a leitura passa pela view.
        """
        sql = text(
            """
            INSERT INTO log.tb002_diagnostico_motor_nativo
                (id_usuario, co_jogo, co_motor, co_motivo, de_motivo,
                 co_versao_binario_esperada, co_versao_binario_encontrada,
                 co_plataforma, co_versao_so, no_modelo_aparelho, co_abi,
                 co_versao_app, co_flavor, co_modo_build)
            VALUES
                (:id_usuario, :co_jogo, :co_motor, :co_motivo, :de_motivo,
                 :co_versao_binario_esperada, :co_versao_binario_encontrada,
                 :co_plataforma, :co_versao_so, :no_modelo_aparelho, :co_abi,
                 :co_versao_app, :co_flavor, :co_modo_build)
            RETURNING id_diagnostico
            """
        )
        resultado = await self.sessao.execute(sql, dados)
        return str(resultado.scalar_one())
