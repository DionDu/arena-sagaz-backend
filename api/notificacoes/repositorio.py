"""Repositório de notificações — acesso a `tb005_dispositivo_notificacao` e
`tb006_preferencia_notificacao`.

Segue a **regra de ouro** do projeto (memória `convencao-banco-dados`): LEITURA
pelas VIEWs `conta.vwNNN_*`, ESCRITA nas tabelas `conta.tbNNN_*`. Usa
`sqlalchemy.text(...)` com **parâmetros nomeados** (`:nome`) — nunca interpolação
de string — contra SQL injection. Escritas dão `flush` mas não `commit` (quem
orquestra a transação é o serviço/rota).
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RepositorioNotificacao:
    """Dispositivos (tokens FCM) e preferências por categoria de um usuário."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Leituras (sempre pela VIEW) ─────────────────────────────────────────

    async def id_usuario_por_identidade(
        self, co_identidade_externa: str
    ) -> Optional[Any]:
        """Resolve o `id_usuario` (UUID interno) a partir do `uid` do Firebase.
        `None` se ainda não há conta para esse uid (ex.: perfil não completado)."""
        sql = text(
            "SELECT id_usuario FROM conta.vw001_usuario "
            "WHERE co_identidade_externa = :uid"
        )
        resultado = await self.sessao.execute(sql, {"uid": co_identidade_externa})
        linha = resultado.mappings().first()
        return linha["id_usuario"] if linha else None

    async def listar_preferencias(
        self, id_usuario: Any
    ) -> list[dict[str, Any]]:
        """Preferências (categoria + ic_ativo) do usuário."""
        sql = text(
            "SELECT co_categoria, ic_ativo "
            "FROM conta.vw006_preferencia_notificacao "
            "WHERE id_usuario = :id ORDER BY co_categoria"
        )
        resultado = await self.sessao.execute(sql, {"id": id_usuario})
        return [dict(linha) for linha in resultado.mappings().all()]

    # ── Escritas (sempre na TABELA) ─────────────────────────────────────────

    async def upsert_dispositivo(
        self,
        id_usuario: Optional[Any],
        co_token_fcm: str,
        sg_plataforma: str,
        co_idioma: str,
        co_fuso: Optional[str] = None,
        nu_offset_minuto: Optional[int] = None,
    ) -> None:
        """Insere o token; se o token já existe (UNIQUE), **atualiza** o dono, a
        plataforma, o idioma, o fuso e `dh_atualizacao`. É o UPSERT por
        `co_token_fcm` descrito no data-model (token igual = mesma linha).

        ⚠️ `co_fuso`/`nu_offset_minuto` usam **COALESCE** no UPDATE: um app ANTIGO
        (que não envia esses campos) não pode **apagar** o fuso que uma versão nova
        já tinha gravado. Sem o COALESCE, bastaria o usuário abrir a versão velha
        num segundo aparelho — ou o app reenviar o registro por outro caminho — para
        zerar o dado. O padrão é `EXCLUDED.x` só quando `x` veio preenchido."""
        sql = text(
            """
            INSERT INTO conta.tb005_dispositivo_notificacao
                (id_usuario, co_token_fcm, sg_plataforma, co_idioma,
                 co_fuso, nu_offset_minuto)
            VALUES (:id_usuario, :token, :plataforma, :idioma,
                    :fuso, :offset_minuto)
            ON CONFLICT (co_token_fcm) DO UPDATE SET
                id_usuario       = EXCLUDED.id_usuario,
                sg_plataforma    = EXCLUDED.sg_plataforma,
                co_idioma        = EXCLUDED.co_idioma,
                co_fuso          = COALESCE(EXCLUDED.co_fuso,
                                            conta.tb005_dispositivo_notificacao.co_fuso),
                nu_offset_minuto = COALESCE(EXCLUDED.nu_offset_minuto,
                                            conta.tb005_dispositivo_notificacao.nu_offset_minuto),
                dh_atualizacao   = now()
            """
        )
        await self.sessao.execute(
            sql,
            {
                "id_usuario": id_usuario,
                "token": co_token_fcm,
                "plataforma": sg_plataforma,
                "idioma": co_idioma,
                "fuso": co_fuso,
                "offset_minuto": nu_offset_minuto,
            },
        )

    async def remover_dispositivo(
        self, co_token_fcm: str, id_usuario: Optional[Any] = None
    ) -> int:
        """Apaga a linha do token (logout/expiração) **restrita ao dono**. Devolve
        quantas linhas saíram (0 se o token não existia ou era de outro usuário).

        Filtra por dono para impedir IDOR (SEG-08): um usuário só apaga o próprio
        token. `id_usuario` NULL (convidado) casa com tokens ainda sem dono. Como o
        registro sempre reatribui o token ao usuário no login (upsert), na prática
        um usuário logado remove o token que é dele."""
        sql = text(
            "DELETE FROM conta.tb005_dispositivo_notificacao "
            "WHERE co_token_fcm = :token "
            "  AND id_usuario IS NOT DISTINCT FROM :id_usuario"
        )
        resultado = await self.sessao.execute(
            sql, {"token": co_token_fcm, "id_usuario": id_usuario}
        )
        return resultado.rowcount or 0

    async def upsert_preferencia(
        self, id_usuario: Any, co_categoria: str, ic_ativo: bool
    ) -> None:
        """Define (cria ou atualiza) uma preferência de categoria do usuário.
        UPSERT por (`id_usuario`, `co_categoria`) — a constraint única da tabela."""
        sql = text(
            """
            INSERT INTO conta.tb006_preferencia_notificacao
                (id_usuario, co_categoria, ic_ativo)
            VALUES (:id_usuario, :categoria, :ativo)
            ON CONFLICT (id_usuario, co_categoria) DO UPDATE SET
                ic_ativo       = EXCLUDED.ic_ativo,
                dh_atualizacao = now()
            """
        )
        await self.sessao.execute(
            sql,
            {"id_usuario": id_usuario, "categoria": co_categoria, "ativo": ic_ativo},
        )

    async def upsert_marketing_consentimento(
        self, id_usuario: Any, ic_marketing: bool
    ) -> None:
        """Grava o **consentimento de marketing** na `tb004_consentimento`
        (fonte única / registro LGPD). É para onde a categoria `marketing` da
        tela de notificações é roteada — a `vw006` lê o marketing daqui.

        UPSERT por `id_usuario` (UNIQUE na tb004). Só toca em `ic_marketing`;
        `ic_rastreamento` mantém o valor existente (ou o default no insert)."""
        sql = text(
            """
            INSERT INTO conta.tb004_consentimento (id_usuario, ic_marketing)
            VALUES (:id, :ativo)
            ON CONFLICT (id_usuario) DO UPDATE SET
                ic_marketing   = EXCLUDED.ic_marketing,
                dh_atualizacao = now()
            """
        )
        await self.sessao.execute(sql, {"id": id_usuario, "ativo": ic_marketing})
