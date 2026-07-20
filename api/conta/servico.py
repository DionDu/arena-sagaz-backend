"""Serviço de conta — tarefa T035.

Regras de negócio do login/cadastro, acima do repositório:
- **upsert por `uid`**: se já existe conta para o Firebase uid, atualiza; senão, cria;
- **geração de `co_usuario`** única (com retentativa em colisão);
- **validação de idade ≥ 13** ao criar (FR-005a).

Depende do [RepositorioUsuario] (acesso a dados) e da sessão (para `rollback` na
retentativa). É testável com fakes — não precisa de banco real.
"""
from __future__ import annotations

import asyncio
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


def provedores_do_token(identidade: IdentidadeFirebase) -> list[tuple[str, str]]:
    """Lista os provedores que o Firebase declara **agora** para esta conta.

    Sai da claim `firebase.identities` do ID token, que tem esta cara::

        {"google.com": ["108…"], "email": ["a@b.com"]}

    Ou seja: o provedor → as identidades dele. É a **fonte da verdade** — e é o
    único jeito de o nosso banco descobrir que um provedor foi **REMOVIDO**, coisa
    que o Firebase faz sozinho (ver `reconciliar_provedores` no repositório).

    A chave `email` corresponde ao `sign_in_provider` `password` (o Firebase usa
    nomes diferentes nos dois lugares) — daí o remapeamento explícito.

    Devolve `[]` se a claim não vier (token atípico): quem chama entende isso como
    "não sei", e prefere não mexer a apagar vínculo por engano.
    """
    identities = (identidade.claims.get("firebase") or {}).get("identities") or {}
    if not isinstance(identities, dict):
        return []

    pares: list[tuple[str, str]] = []
    for chave, valores in identities.items():
        # Na claim o provedor de senha aparece como "email"; no sign_in_provider,
        # como "password". Normalizamos para o nosso código único: "email".
        co_provedor = "email" if chave == "email" else mapear_provedor(chave)
        for valor in valores or []:
            pares.append((co_provedor, str(valor)))
    return pares


def calcular_idade(nascimento: date, hoje: Optional[date] = None) -> int:
    """Idade em anos completos (mesma regra do app, no servidor)."""
    hoje = hoje or date.today()
    anos = hoje.year - nascimento.year
    # Tupla (mês, dia): compara se o aniversário ainda não chegou neste ano.
    if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return anos


def _exigir_idade_minima(nascimento: Optional[date]) -> None:
    """Recusa (422 `idade_minima`) uma data de nascimento que resulte em idade
    abaixo de [IDADE_MINIMA]. `None` passa (campo não informado).

    Centralizado para valer em TODOS os pontos que gravam a data — criação
    (`_criar_novo`), reentrada (`_atualizar_existente`) e edição de perfil
    (`atualizar_perfil_usuario`). Assim a trava etária (COPPA/FR-005a) não pode
    ser burlada trocando a data depois de a conta existir (NEG-02)."""
    if nascimento is not None and calcular_idade(nascimento) < IDADE_MINIMA:
        raise ErroNegocio(
            "É preciso ter ao menos $IDADE anos.".replace("$IDADE", str(IDADE_MINIMA)),
            "idade_minima",
            status_http=422,
        )


def _nome_moderado_para_sessao(nome: Optional[str]) -> Optional[str]:
    """Modera o nome recebido na SESSÃO (login/reentrada). Se o nome for inválido
    (curto/longo/proibido — ver [validar_nome_exibicao]), devolve `None` em vez de
    lançar erro: o login NÃO pode falhar por causa de um apelido (o `co_usuario` é
    a identidade real; o nome é cosmético). A edição EXPLÍCITA de nome é pelo
    `PATCH /conta/perfil`, que **rejeita** nome inválido com 422 (NEG-01)."""
    if nome is None:
        return None
    try:
        return validar_nome_exibicao(nome)
    except ErroNegocio:
        return None


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

        # Modera/normaliza o nome só se ele foi informado no corpo. Aqui a edição é
        # EXPLÍCITA (a pessoa digitou o nome), então nome inválido REJEITA com 422
        # (diferente da sessão, que apenas ignora) — NEG-01.
        no_exibicao = dados.no_exibicao
        if no_exibicao is not None:
            no_exibicao = validar_nome_exibicao(no_exibicao)

        # Data de nascimento é editável (corrigir erro de digitação), mas SEMPRE
        # revalida idade >= 13 (NEG-02). Melhor que bloquear de vez: o usuário
        # conserta a data, e a trava etária continua garantida.
        _exigir_idade_minima(dados.dt_nascimento)

        atualizada = await self.repo.atualizar_perfil(
            id_usuario=usuario["id_usuario"],
            no_exibicao=no_exibicao,
            dt_nascimento=dados.dt_nascimento,
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

        # **Confirma a anonimização AGORA**, antes de tocar no Firebase. Assim a
        # remoção de PII na nossa base fica DURÁVEL mesmo que o passo do Firebase
        # demore/trave (antes o commit vinha só no fim — se o Firebase travava, a
        # transação era desfeita e a conta permanecia com os dados).
        await self.sessao.commit()

        # Apaga no Firebase — **best-effort com TIMEOUT** para nunca travar a
        # resposta (o Admin SDK pode demorar/pendurar). Se falhar/estourar, só
        # registramos: a PII na nossa base já foi removida.
        admin = self.admin or obter_admin_usuarios()
        try:
            await asyncio.wait_for(
                admin.excluir_usuario(identidade.uid), timeout=8.0
            )
        except Exception:  # noqa: BLE001 — best-effort: não derruba a exclusão
            # Sem PII no log (Constituição, Princípio IV) — só o evento.
            log.warning(
                "Falha/timeout ao excluir usuário no Firebase "
                "(conta já anonimizada na base)"
            )

        return ExclusaoContaResposta(ic_anonimizado=True)

    async def _apagar_identidade_orfa(self, identidade: IdentidadeFirebase) -> None:
        """Apaga no Firebase um usuário que autenticou mas **não pôde virar conta**.

        Best-effort **com timeout**, igual à exclusão de conta: se o Admin SDK
        falhar ou demorar, não travamos nem trocamos a resposta — o usuário
        continua recebendo o 422 `idade_minima`, que é o que importa para ele. O
        que fica é um registro no log para sabermos que sobrou um órfão.

        Não há transação a desfazer aqui: chegamos neste ponto **antes** de
        qualquer escrita na nossa base (a conta não foi criada).
        """
        try:
            # `obter_admin_usuarios()` entra no `try` de propósito: ele inicializa o
            # Firebase Admin e levanta quando não há credencial (o caso dos testes).
            admin = self.admin or obter_admin_usuarios()
            await asyncio.wait_for(admin.excluir_usuario(identidade.uid), timeout=8.0)
        except Exception:  # noqa: BLE001 — best-effort: não muda a resposta
            # Sem PII no log (Constituição, Princípio IV) — só o evento.
            log.warning(
                "Falha/timeout ao apagar no Firebase a identidade recusada por "
                "idade mínima (nenhuma conta foi criada)"
            )

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
        # REGRA DE NOME (definitiva): se JÁ existe nome salvo, ele MANDA — o nome
        # que vem do provedor a cada login (Google/Apple/…) NÃO o sobrescreve. Só
        # preenchemos pelo provedor quando o nome ainda está VAZIO. A troca
        # explícita de nome é pelo `PATCH /conta/perfil`, não pela sessão. O nome
        # que preenche o vazio passa pela **moderação** (NEG-01); se reprovado,
        # fica None (não derruba o login).
        nome_atual = (linha.get("no_exibicao") or "").strip()
        no_exibicao_efetivo = (
            _nome_moderado_para_sessao(dados.no_exibicao) if not nome_atual else None
        )

        # Data de nascimento pode ser corrigida na reentrada, mas SEMPRE revalida
        # idade >= 13 (NEG-02) — impede burlar a trava etária depois de criada a
        # conta. `None` (não veio no corpo) passa direto.
        _exigir_idade_minima(dados.dt_nascimento)

        # Só atualiza o que veio no corpo (o repositório usa COALESCE: campo nulo
        # mantém o valor atual).
        if (
            no_exibicao_efetivo is not None
            or dados.dt_nascimento is not None
            or dados.co_idioma_preferido is not None
        ):
            atualizada = await self.repo.atualizar_perfil(
                id_usuario=linha["id_usuario"],
                no_exibicao=no_exibicao_efetivo,
                dt_nascimento=dados.dt_nascimento,
                co_idioma_preferido=dados.co_idioma_preferido,
            )
            if atualizada is not None:
                linha = atualizada
        # RECONCILIA os provedores com o que o Firebase declara AGORA (não apenas
        # acrescenta). O Firebase REMOVE provedores sozinho — com "uma conta por
        # e-mail" ligado, entrar com Google numa conta de e-mail/senha NÃO VERIFICADA
        # faz a senha ser descartada. Como a nossa tabela só inseria, ela continuava
        # exibindo um provedor que já não existia: mentia exatamente quando alguém a
        # consultava para investigar um problema de login.
        provedores = provedores_do_token(identidade)
        if provedores:
            await self.repo.reconciliar_provedores(linha["id_usuario"], provedores)
            # O provedor que CRIOU a conta pode ter sido justamente o removido. Se
            # ele não existe mais, `co_provedor_principal` passa a apontar para o
            # provedor da entrada atual — senão a tb001 mentiria igual à tb002.
            codigos = {p for p, _ in provedores}
            if linha.get("co_provedor_principal") not in codigos:
                atual = mapear_provedor(identidade.provedor)
                await self.repo.definir_provedor_principal(
                    linha["id_usuario"], atual if atual in codigos else next(iter(codigos))
                )
        else:
            # Token sem a claim `identities` (atípico): cai no comportamento antigo,
            # só registrando o provedor da entrada atual. Melhor um dado velho do que
            # apagar vínculos por causa de um token que não sabemos ler.
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
            # A conta NÃO nasce — mas o usuário do Firebase JÁ NASCEU. No login
            # social (Google/Apple) o Firebase autentica ANTES de nós sabermos a
            # idade: quando a data chega aqui e reprova, já existe lá um registro
            # com o e-mail e o nome de uma criança, sem conta nenhuma apontando
            # para ele. Apagá-lo é obrigação, não faxina: é PII de menor sem
            # finalidade (LGPD art. 14) e um uid órfão que continuaria logando.
            #
            # Este é o ÚNICO ponto do serviço que apaga por idade, e é de propósito:
            # `_atualizar_existente` e `atualizar_perfil_usuario` também rejeitam
            # menores (NEG-02), mas ali a conta EXISTE — um adulto que erra a data
            # de nascimento só pode receber um 422, jamais ter a conta destruída.
            await self._apagar_identidade_orfa(identidade)
            raise ErroNegocio(
                "É preciso ter ao menos $IDADE anos.".replace(
                    "$IDADE", str(IDADE_MINIMA)
                ),
                "idade_minima",
                status_http=422,
            )

        # Modera o nome antes de gravar (NEG-01). Nome reprovado vira None (a conta
        # é criada sem apelido; a pessoa define depois pelo PATCH). Usa model_copy
        # para não mutar o request original.
        dados = dados.model_copy(
            update={"no_exibicao": _nome_moderado_para_sessao(dados.no_exibicao)}
        )

        provedor = mapear_provedor(identidade.provedor)
        linha = await self._criar_com_codigo_unico(
            identidade=identidade, dados=dados, provedor=provedor
        )
        # Registra os provedores da conta recém-criada.
        #
        # ⚠️ Usa a MESMA fonte da reentrada (a claim `firebase.identities`) — antes
        # daqui gravava `co_identidade_provedor = identidade.uid`, e isso gerava uma
        # linha DUPLICADA: a criação punha `('email', <uid>)` e o login seguinte, ao
        # reconciliar, punha `('email', 'fulano@x.com')`. As duas conviviam, e a
        # tabela mostrava o provedor `email` duas vezes (bug medido em 2026-07-12).
        provedores = provedores_do_token(identidade)
        if provedores:
            await self.repo.reconciliar_provedores(linha["id_usuario"], provedores)
        else:
            # Token sem a claim (atípico): grava ao menos o provedor da entrada.
            await self.repo.vincular_provedor(
                id_usuario=linha["id_usuario"],
                co_provedor=provedor,
                co_identidade_provedor=identidade.uid,
            )
        # A criação TAMBÉM é um acesso: sem isto, `dh_ultimo_acesso` nascia NULL e
        # só era preenchido num RE-login futuro. Como o app reabre com a sessão
        # restaurada de forma ASSÍNCRONA (e esse caminho nem sempre rechama
        # `/sessao`), a coluna podia ficar NULL para sempre em quem usa o app todo
        # dia. Carimbar aqui garante que a conta nasce com um acesso registrado.
        await self.repo.registrar_ultimo_acesso(linha["id_usuario"])
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
