"""Serviço de conta — tarefa T035.

Regras de negócio do login/cadastro, acima do repositório:
- **upsert por `uid`**: se já existe conta para o Firebase uid, atualiza; senão, cria;
- **geração de `co_usuario`** única (com retentativa em colisão);
- **validação de idade ≥ 13** ao criar (FR-005a).

Depende do [RepositorioUsuario] (acesso a dados) e da sessão (para `rollback` na
retentativa). É testável com fakes — não precisa de banco real.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from api.conta.codigo_usuario import gerar_codigo_usuario
from api.conta.modelos import (
    AceiteLegalRequest,
    AceiteLegalResposta,
    ConsentimentoRequest,
    ConsentimentoResposta,
    PerfilUsuario,
    SessaoRequest,
)
from api.nucleo.excecoes import ErroNegocio, ErroNaoEncontrado
from api.nucleo.seguranca_firebase import IdentidadeFirebase

# Idade mínima para criar conta (espelha `idadeMinimaConta` no app).
IDADE_MINIMA = 13

# Quantas vezes tentamos gerar um co_usuario único antes de desistir.
_MAX_TENTATIVAS_CODIGO = 10

# Tradução do `sign_in_provider` do Firebase para o nosso `co_provedor`.
_MAPA_PROVEDOR = {
    "google.com": "google",
    "apple.com": "apple",
    "facebook.com": "facebook",
    "password": "email",
    "anonymous": "anonimo",
}


def mapear_provedor(sign_in_provider: str) -> str:
    """Converte o provedor do Firebase no nosso código curto (default: o próprio)."""
    return _MAPA_PROVEDOR.get(sign_in_provider, sign_in_provider or "desconhecido")


def calcular_idade(nascimento: date, hoje: Optional[date] = None) -> int:
    """Idade em anos completos (mesma regra do app, no servidor)."""
    hoje = hoje or date.today()
    anos = hoje.year - nascimento.year
    # Tupla (mês, dia): compara se o aniversário ainda não chegou neste ano.
    if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return anos


class ServicoConta:
    """Orquestra a conta de usuário (criação/atualização e perfil)."""

    def __init__(self, repo: Any, sessao: Any) -> None:
        # `repo` é um RepositorioUsuario; `sessao` é a AsyncSession (para rollback
        # e commit). Tipados como Any para aceitar fakes nos testes.
        self.repo = repo
        self.sessao = sessao

    async def garantir_sessao(
        self, identidade: IdentidadeFirebase, dados: SessaoRequest
    ) -> PerfilUsuario:
        """Ponto de entrada do `POST /v1/conta/sessao`: cria ou atualiza a conta
        do dono do token e devolve o perfil."""
        existente = await self.repo.buscar_por_identidade_externa(identidade.uid)
        if existente is not None:
            return await self._atualizar_existente(existente, dados)
        return await self._criar_novo(identidade, dados)

    async def obter_perfil(self, identidade: IdentidadeFirebase) -> PerfilUsuario:
        """Perfil do usuário atual (`GET /v1/conta/perfil`). 404 se não houver
        conta ainda (o app deve chamar `/sessao` primeiro)."""
        linha = await self.repo.buscar_por_identidade_externa(identidade.uid)
        if linha is None:
            raise ErroNaoEncontrado("Conta não encontrada.", "conta_inexistente")
        return await self._montar_perfil(linha)

    async def registrar_aceite(
        self, identidade: IdentidadeFirebase, dados: AceiteLegalRequest
    ) -> AceiteLegalResposta:
        """Registra o aceite de um documento legal (US3). Exige conta criada."""
        usuario = await self._usuario_obrigatorio(identidade)
        linha = await self.repo.registrar_aceite_legal(
            id_usuario=usuario["id_usuario"],
            co_documento=dados.co_documento,
            co_versao=dados.co_versao,
            co_idioma=dados.co_idioma,
        )
        return AceiteLegalResposta.de_linha(linha)

    async def definir_consentimento(
        self, identidade: IdentidadeFirebase, dados: ConsentimentoRequest
    ) -> ConsentimentoResposta:
        """Define o consentimento (rastreamento/marketing) — US3 (upsert)."""
        usuario = await self._usuario_obrigatorio(identidade)
        linha = await self.repo.definir_consentimento(
            id_usuario=usuario["id_usuario"],
            ic_rastreamento=dados.ic_rastreamento,
            ic_marketing=dados.ic_marketing,
        )
        return ConsentimentoResposta.de_linha(linha)

    async def _usuario_obrigatorio(
        self, identidade: IdentidadeFirebase
    ) -> dict[str, Any]:
        """Busca a conta pelo uid; 404 se não existir (deve chamar /sessao antes)."""
        linha = await self.repo.buscar_por_identidade_externa(identidade.uid)
        if linha is None:
            raise ErroNaoEncontrado("Conta não encontrada.", "conta_inexistente")
        return linha

    # ── internos ────────────────────────────────────────────────────────────

    async def _atualizar_existente(
        self, linha: dict[str, Any], dados: SessaoRequest
    ) -> PerfilUsuario:
        # Só atualiza o que veio no corpo (o repositório usa COALESCE).
        if (
            dados.no_exibicao is not None
            or dados.dt_nascimento is not None
            or dados.co_idioma_preferido is not None
        ):
            atualizada = await self.repo.atualizar_perfil(
                id_usuario=linha["id_usuario"],
                no_exibicao=dados.no_exibicao,
                dt_nascimento=dados.dt_nascimento,
                co_idioma_preferido=dados.co_idioma_preferido,
            )
            if atualizada is not None:
                linha = atualizada
        await self.repo.registrar_ultimo_acesso(linha["id_usuario"])
        return await self._montar_perfil(linha)

    async def _criar_novo(
        self, identidade: IdentidadeFirebase, dados: SessaoRequest
    ) -> PerfilUsuario:
        # Conta nova exige data de nascimento e idade mínima (FR-005/005a).
        if dados.dt_nascimento is None:
            raise ErroNegocio(
                "Data de nascimento obrigatória para criar conta.",
                "data_nascimento_obrigatoria",
                status_http=422,
            )
        if calcular_idade(dados.dt_nascimento) < IDADE_MINIMA:
            raise ErroNegocio(
                "É preciso ter ao menos $IDADE anos.".replace(
                    "$IDADE", str(IDADE_MINIMA)
                ),
                "idade_minima",
                status_http=422,
            )

        provedor = mapear_provedor(identidade.provedor)
        linha = await self._criar_com_codigo_unico(
            identidade=identidade, dados=dados, provedor=provedor
        )
        # Registra o vínculo do provedor que originou a conta.
        await self.repo.vincular_provedor(
            id_usuario=linha["id_usuario"],
            co_provedor=provedor,
            co_identidade_provedor=identidade.uid,
        )
        return await self._montar_perfil(linha)

    async def _criar_com_codigo_unico(
        self, *, identidade: IdentidadeFirebase, dados: SessaoRequest, provedor: str
    ) -> dict[str, Any]:
        """Tenta criar a conta gerando um `co_usuario`; em colisão (UNIQUE),
        rola atrás e tenta de novo. Se for corrida de criação pelo mesmo uid,
        devolve a conta que o outro pedido criou."""
        ultimo_erro: Optional[Exception] = None
        for _ in range(_MAX_TENTATIVAS_CODIGO):
            codigo = gerar_codigo_usuario()
            try:
                return await self.repo.criar(
                    co_usuario=codigo,
                    co_identidade_externa=identidade.uid,
                    co_provedor_principal=provedor,
                    co_idioma_preferido=dados.co_idioma_preferido or "pt",
                    no_exibicao=dados.no_exibicao,
                    no_email=identidade.email,
                    dt_nascimento=dados.dt_nascimento,
                )
            except IntegrityError as e:
                ultimo_erro = e
                await self.sessao.rollback()
                # Pode ter sido outra requisição criando a MESMA conta (mesmo uid).
                existente = await self.repo.buscar_por_identidade_externa(
                    identidade.uid
                )
                if existente is not None:
                    return existente
                # Senão, foi colisão de co_usuario → tenta outro código.
                continue
        raise ErroNegocio(
            "Não foi possível gerar um código de usuário único.",
            "codigo_usuario_indisponivel",
            status_http=500,
        ) from ultimo_erro

    async def _montar_perfil(self, linha: dict[str, Any]) -> PerfilUsuario:
        # Lê os provedores vinculados (só códigos) para compor a resposta.
        vinculos = await self.repo.listar_provedores(linha["id_usuario"])
        codigos = [v["co_provedor"] for v in vinculos]
        return PerfilUsuario.de_linha(linha, provedores=codigos)
