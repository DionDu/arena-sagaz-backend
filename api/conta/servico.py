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
from api.conta.moderacao import validar_nome_exibicao
from api.conta.modelos import (
    AceiteLegalRequest,
    AceiteLegalResposta,
    AtualizarPerfilRequest,
    ConsentimentoRequest,
    ConsentimentoResposta,
    ExclusaoContaResposta,
    PerfilUsuario,
    SessaoRequest,
)
from api.nucleo.excecoes import ErroNegocio, ErroNaoEncontrado
from api.nucleo.log import obter_logger
from api.nucleo.seguranca_firebase import (
    AdminUsuariosFirebase,
    IdentidadeFirebase,
    obter_admin_usuarios,
)

log = obter_logger("api.conta.servico")

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

    def __init__(
        self, repo: Any, sessao: Any, admin: Optional[AdminUsuariosFirebase] = None
    ) -> None:
        # `repo` é um RepositorioUsuario; `sessao` é a AsyncSession (para rollback
        # e commit). Tipados como Any para aceitar fakes nos testes.
        self.repo = repo
        self.sessao = sessao
        # `admin` apaga o usuário no Firebase na exclusão de conta (US4). Fica
        # opcional para os testes que não exercitam exclusão poderem omiti-lo.
        self.admin = admin

    async def garantir_sessao(
        self, identidade: IdentidadeFirebase, dados: SessaoRequest
    ) -> PerfilUsuario:
        """Ponto de entrada do `POST /v1/conta/sessao`: cria ou atualiza a conta
        do dono do token e devolve o perfil."""
        existente = await self.repo.buscar_por_identidade_externa(identidade.uid)
        if existente is not None:
            return await self._atualizar_existente(existente, dados, identidade)
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

    async def atualizar_perfil_usuario(
        self, identidade: IdentidadeFirebase, dados: AtualizarPerfilRequest
    ) -> PerfilUsuario:
        """Edita o perfil (nome e/ou idioma) — `PATCH /v1/conta/perfil` (US4).

        O nome passa pela moderação ([validar_nome_exibicao]); o idioma é gravado
        como veio. Devolve o perfil atualizado.
        """
        usuario = await self._usuario_obrigatorio(identidade)

        # Modera/normaliza o nome só se ele foi informado no corpo.
        no_exibicao = dados.no_exibicao
        if no_exibicao is not None:
            no_exibicao = validar_nome_exibicao(no_exibicao)

        atualizada = await self.repo.atualizar_perfil(
            id_usuario=usuario["id_usuario"],
            no_exibicao=no_exibicao,
            co_idioma_preferido=dados.co_idioma_preferido,
        )
        # Se nada mudou (corpo vazio), mantém a linha que já tínhamos.
        linha = atualizada if atualizada is not None else usuario
        return await self._montar_perfil(linha)

    async def excluir_conta(
        self, identidade: IdentidadeFirebase
    ) -> ExclusaoContaResposta:
        """Exclui (anonimiza) a conta do usuário atual — `DELETE /v1/conta` (US4).

        Ordem das ações:
        1. **Anonimiza** a conta na nossa base (zera PII) e apaga as tabelas-filhas
           com dado pessoal — este é o requisito legal (LGPD) que controlamos e
           que precisa ser **durável**.
        2. **Best-effort:** apaga o usuário no Firebase (Admin SDK). Se falhar,
           apenas registramos no log e seguimos: a remoção de PII na nossa base já
           aconteceu, e a sessão do cliente será encerrada de qualquer forma.
        """
        usuario = await self._usuario_obrigatorio(identidade)
        id_usuario = usuario["id_usuario"]

        await self.repo.anonimizar_usuario(id_usuario)
        await self.repo.remover_dados_vinculados(id_usuario)

        admin = self.admin or obter_admin_usuarios()
        try:
            await admin.excluir_usuario(identidade.uid)
        except Exception:  # noqa: BLE001 — best-effort: não derruba a exclusão
            # Sem PII no log (Constituição, Princípio IV) — só o evento.
            log.warning(
                "Falha ao excluir usuário no Firebase (conta já anonimizada na base)"
            )

        return ExclusaoContaResposta(ic_anonimizado=True)

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
        self,
        linha: dict[str, Any],
        dados: SessaoRequest,
        identidade: IdentidadeFirebase,
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
        # Registra o provedor com que a pessoa entrou AGORA. Assim, quem criou a
        # conta por e-mail e depois entrou com Google passa a ter os DOIS
        # provedores vinculados na nossa base (antes só o de criação aparecia).
        # `vincular_provedor` é idempotente (ON CONFLICT DO NOTHING).
        await self.repo.vincular_provedor(
            id_usuario=linha["id_usuario"],
            co_provedor=mapear_provedor(identidade.provedor),
            co_identidade_provedor=identidade.uid,
        )
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
