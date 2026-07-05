"""Repositório de conta — tarefa T014.

**Regra de ouro do projeto (memória `convencao-banco-dados`):** a **LEITURA** é
feita pelas VIEWs `conta.vwNNN_*` e a **ESCRITA** nas tabelas `conta.tbNNN_*`.
Este módulo concentra esse acesso para que nenhuma rota escreva SQL solta.

Como as migrações foram escritas em SQL puro (sem ORM), aqui usamos
`sqlalchemy.text(...)` com **parâmetros nomeados** (`:nome`) — nunca interpolação
de string — para evitar SQL injection.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RepositorioUsuario:
    """Acesso a conta de usuário e seus vínculos (provedores, aceites, consentimento).

    Recebe uma [AsyncSession] por requisição (ver `obter_sessao` em `banco.py`).
    Os métodos de **escrita** dão `flush` (para obter o RETURNING) mas **não**
    dão `commit`: quem orquestra a transação (a camada de serviço/rota) decide
    quando confirmar — assim várias escritas entram juntas, atômicas.
    """

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Leituras (sempre pela VIEW) ─────────────────────────────────────────

    async def buscar_por_identidade_externa(
        self, co_identidade_externa: str
    ) -> Optional[dict[str, Any]]:
        """Acha o usuário pelo `uid` do Firebase (chave de identidade). É a
        consulta do login: "já existe conta para este Firebase uid?"."""
        sql = text(
            "SELECT * FROM conta.vw001_usuario "
            "WHERE co_identidade_externa = :id"
        )
        resultado = await self.sessao.execute(sql, {"id": co_identidade_externa})
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    async def buscar_por_email(self, no_email: str) -> Optional[dict[str, Any]]:
        sql = text("SELECT * FROM conta.vw001_usuario WHERE no_email = :email")
        resultado = await self.sessao.execute(sql, {"email": no_email})
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    async def buscar_por_codigo(self, co_usuario: str) -> Optional[dict[str, Any]]:
        sql = text("SELECT * FROM conta.vw001_usuario WHERE co_usuario = :co")
        resultado = await self.sessao.execute(sql, {"co": co_usuario})
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    # ── Escritas (sempre na TABELA) ─────────────────────────────────────────

    async def criar(
        self,
        *,
        co_usuario: str,
        co_identidade_externa: str,
        co_provedor_principal: str,
        co_idioma_preferido: str = "pt",
        no_exibicao: Optional[str] = None,
        no_email: Optional[str] = None,
        dt_nascimento: Optional[date] = None,
        ic_convidado: bool = False,
    ) -> dict[str, Any]:
        """Insere um usuário novo e devolve a linha criada (com id e timestamps).

        O `*` na assinatura força todos os argumentos a serem **nomeados** na
        chamada (mais legível e à prova de troca de ordem).
        """
        sql = text(
            """
            INSERT INTO conta.tb001_usuario
                (co_usuario, co_identidade_externa, no_exibicao, no_email,
                 dt_nascimento, co_provedor_principal, co_idioma_preferido,
                 ic_convidado)
            VALUES
                (:co_usuario, :co_identidade_externa, :no_exibicao, :no_email,
                 :dt_nascimento, :co_provedor_principal, :co_idioma_preferido,
                 :ic_convidado)
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(
            sql,
            {
                "co_usuario": co_usuario,
                "co_identidade_externa": co_identidade_externa,
                "no_exibicao": no_exibicao,
                "no_email": no_email,
                "dt_nascimento": dt_nascimento,
                "co_provedor_principal": co_provedor_principal,
                "co_idioma_preferido": co_idioma_preferido,
                "ic_convidado": ic_convidado,
            },
        )
        return dict(resultado.mappings().first())

    async def atualizar_perfil(
        self,
        *,
        id_usuario: str,
        no_exibicao: Optional[str] = None,
        dt_nascimento: Optional[date] = None,
        co_idioma_preferido: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Atualiza nome/nascimento/idioma. `COALESCE(:x, coluna)` mantém o valor
        atual quando o parâmetro vier `NULL` (ou seja, "não mexa neste campo").
        Também carimba `dh_atualizacao = now()`."""
        sql = text(
            """
            UPDATE conta.tb001_usuario
            SET no_exibicao = COALESCE(:no_exibicao, no_exibicao),
                dt_nascimento = COALESCE(:dt_nascimento, dt_nascimento),
                co_idioma_preferido =
                    COALESCE(:co_idioma_preferido, co_idioma_preferido),
                dh_atualizacao = now()
            WHERE id_usuario = :id_usuario
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(
            sql,
            {
                "id_usuario": id_usuario,
                "no_exibicao": no_exibicao,
                "dt_nascimento": dt_nascimento,
                "co_idioma_preferido": co_idioma_preferido,
            },
        )
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    async def registrar_ultimo_acesso(self, id_usuario: str) -> None:
        """Marca o login atual (`dh_ultimo_acesso = now()`)."""
        sql = text(
            "UPDATE conta.tb001_usuario SET dh_ultimo_acesso = now() "
            "WHERE id_usuario = :id"
        )
        await self.sessao.execute(sql, {"id": id_usuario})

    async def vincular_provedor(
        self,
        *,
        id_usuario: str,
        co_provedor: str,
        co_identidade_provedor: str,
    ) -> dict[str, Any]:
        """Registra um provedor vinculado (Google/Apple/...). `ON CONFLICT DO
        NOTHING` torna a operação **idempotente**: religar o mesmo provedor não
        duplica nem dá erro."""
        sql = text(
            """
            INSERT INTO conta.tb002_provedor_login
                (id_usuario, co_provedor, co_identidade_provedor)
            VALUES (:id_usuario, :co_provedor, :co_identidade_provedor)
            ON CONFLICT (co_provedor, co_identidade_provedor) DO NOTHING
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(
            sql,
            {
                "id_usuario": id_usuario,
                "co_provedor": co_provedor,
                "co_identidade_provedor": co_identidade_provedor,
            },
        )
        linha = resultado.mappings().first()
        return dict(linha) if linha else {}

    async def listar_provedores(self, id_usuario: str) -> list[dict[str, Any]]:
        sql = text(
            "SELECT * FROM conta.vw002_provedor_login "
            "WHERE id_usuario = :id ORDER BY dh_vinculo"
        )
        resultado = await self.sessao.execute(sql, {"id": id_usuario})
        return [dict(linha) for linha in resultado.mappings().all()]

    async def registrar_aceite_legal(
        self,
        *,
        id_usuario: str,
        co_documento: str,
        co_versao: str,
        co_idioma: str,
    ) -> dict[str, Any]:
        """Grava um aceite de documento legal (termos/privacidade). **Idempotente
        por (usuário, documento, versão)** (NEG-05): re-aceitar a MESMA versão não
        cria linha nova nem erra — devolve o aceite ORIGINAL (o primeiro daquela
        versão, que é o que vale para auditoria). Versões diferentes seguem gerando
        linhas novas (histórico preservado). Depende da constraint
        `uq_aceite_usuario_documento_versao` (migração 0004)."""
        sql = text(
            """
            INSERT INTO conta.tb003_aceite_legal
                (id_usuario, co_documento, co_versao, co_idioma)
            VALUES (:id_usuario, :co_documento, :co_versao, :co_idioma)
            ON CONFLICT (id_usuario, co_documento, co_versao) DO UPDATE
                -- no-op que preserva a linha original mas permite o RETURNING.
                SET co_idioma = conta.tb003_aceite_legal.co_idioma
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(
            sql,
            {
                "id_usuario": id_usuario,
                "co_documento": co_documento,
                "co_versao": co_versao,
                "co_idioma": co_idioma,
            },
        )
        return dict(resultado.mappings().first())

    async def definir_consentimento(
        self,
        *,
        id_usuario: str,
        ic_rastreamento: bool,
        ic_marketing: bool,
    ) -> dict[str, Any]:
        """Define o consentimento (rastreamento/marketing). É **1 linha por
        usuário**: `ON CONFLICT (id_usuario)` faz *upsert* (cria ou atualiza)."""
        sql = text(
            """
            INSERT INTO conta.tb004_consentimento
                (id_usuario, ic_rastreamento, ic_marketing)
            VALUES (:id_usuario, :ic_rastreamento, :ic_marketing)
            ON CONFLICT (id_usuario) DO UPDATE
                SET ic_rastreamento = EXCLUDED.ic_rastreamento,
                    ic_marketing = EXCLUDED.ic_marketing,
                    dh_atualizacao = now()
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(
            sql,
            {
                "id_usuario": id_usuario,
                "ic_rastreamento": ic_rastreamento,
                "ic_marketing": ic_marketing,
            },
        )
        return dict(resultado.mappings().first())

    # ── Exclusão de conta (US4) — anonimização, não DELETE da linha ─────────

    async def anonimizar_usuario(self, id_usuario: str) -> Optional[dict[str, Any]]:
        """Apaga os dados pessoais (PII) do usuário **mantendo a linha**.

        Estratégia (data-model.md): em vez de `DELETE` (que perderia a
        integridade de eventuais agregados/estatísticas que apontem para
        `id_usuario`), **anonimizamos**:
        - zera nome, e-mail e data de nascimento;
        - desliga o `co_identidade_externa` (o uid do Firebase) — assim, se a
          pessoa recriar a conta depois, vira um usuário **novo**;
        - marca `ic_anonimizado = TRUE` e grava um `co_anonimo` (UUID aleatório)
          como rótulo opaco e estável da conta extinta.
        """
        sql = text(
            """
            UPDATE conta.tb001_usuario
            SET no_exibicao           = NULL,
                no_email              = NULL,
                dt_nascimento         = NULL,
                co_identidade_externa = NULL,
                ic_anonimizado        = TRUE,
                co_anonimo            = gen_random_uuid(),
                dh_atualizacao        = now()
            WHERE id_usuario = :id_usuario
            RETURNING *
            """
        )
        resultado = await self.sessao.execute(sql, {"id_usuario": id_usuario})
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    async def remover_dados_vinculados(self, id_usuario: str) -> None:
        """Apaga as tabelas-filhas que carregam dado pessoal/identidade: provedores
        (tb002), consentimento (tb004), tokens de dispositivo (tb005) e
        preferências de notificação (tb006).

        **Mantemos `tb003_aceite_legal`** de propósito: é registro de auditoria
        legal (qual versão de termos foi aceita, quando) e **não contém PII** —
        só o `id_usuario`, que após a anonimização aponta para uma conta sem
        dados pessoais.
        """
        for tabela in (
            "tb002_provedor_login",
            "tb004_consentimento",
            "tb005_dispositivo_notificacao",
            "tb006_preferencia_notificacao",
        ):
            await self.sessao.execute(
                text(f"DELETE FROM conta.{tabela} WHERE id_usuario = :id"),
                {"id": id_usuario},
            )
