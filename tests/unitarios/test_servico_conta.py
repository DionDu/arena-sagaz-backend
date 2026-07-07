"""Testes do ServicoConta (T035) — upsert por uid, idade e co_usuario, com fakes."""
import asyncio
from datetime import date

import pytest

from api.conta.codigo_usuario import ALFABETO, TAMANHO
from api.conta.modelos import SessaoRequest
from api.conta.servico import ServicoConta, calcular_idade, mapear_provedor
from api.nucleo.excecoes import ErroNegocio, ErroNaoEncontrado
from api.nucleo.seguranca_firebase import IdentidadeFirebase
from tests.unitarios.fakes_conta import FakeRepoUsuario, FakeSession


def _servico(repo):
    return ServicoConta(repo=repo, sessao=FakeSession())


def _identidade(uid="u1", email="a@b.com", provedor="password"):
    return IdentidadeFirebase(uid=uid, email=email, provedor=provedor)


# ── helpers puros ────────────────────────────────────────────────────────────


def test_mapear_provedor():
    assert mapear_provedor("google.com") == "google"
    assert mapear_provedor("password") == "email"
    assert mapear_provedor("apple.com") == "apple"
    assert mapear_provedor("anonymous") == "anonimo"
    assert mapear_provedor("") == "desconhecido"


def test_calcular_idade():
    hoje = date(2026, 6, 28)
    assert calcular_idade(date(2000, 6, 28), hoje) == 26
    assert calcular_idade(date(2008, 12, 31), hoje) == 17


# ── criação ──────────────────────────────────────────────────────────────────


def test_cria_conta_nova_gera_codigo_e_vincula_provedor():
    repo = FakeRepoUsuario()
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(provedor="google.com"),
            SessaoRequest(no_exibicao="Fernando", dt_nascimento=date(1990, 1, 1)),
        )
    )
    assert len(perfil.co_usuario) == TAMANHO
    assert all(ch in ALFABETO for ch in perfil.co_usuario)
    assert perfil.co_provedor_principal == "google"
    assert perfil.provedores == ["google"]
    assert perfil.no_exibicao == "Fernando"
    assert len(repo.criadas) == 1


def test_cria_sem_data_nascimento_responde_422():
    with pytest.raises(ErroNegocio) as exc:
        asyncio.run(
            _servico(FakeRepoUsuario()).garantir_sessao(
                _identidade(), SessaoRequest()
            )
        )
    assert exc.value.codigo == "data_nascimento_obrigatoria"
    assert exc.value.status_http == 422


def test_cria_menor_de_13_responde_422_idade_minima():
    hoje = date.today()
    nasc = date(hoje.year - 10, hoje.month, max(1, hoje.day))
    with pytest.raises(ErroNegocio) as exc:
        asyncio.run(
            _servico(FakeRepoUsuario()).garantir_sessao(
                _identidade(), SessaoRequest(dt_nascimento=nasc)
            )
        )
    assert exc.value.codigo == "idade_minima"
    assert exc.value.status_http == 422


def test_exatamente_13_cria_conta():
    hoje = date.today()
    nasc = date(hoje.year - 13, hoje.month, max(1, hoje.day))
    perfil = asyncio.run(
        _servico(FakeRepoUsuario()).garantir_sessao(
            _identidade(), SessaoRequest(dt_nascimento=nasc)
        )
    )
    assert perfil.co_provedor_principal == "email"


# ── reentrada (upsert) ───────────────────────────────────────────────────────


def _conta_existente(uid="u1"):
    return {
        "id_usuario": f"id-{uid}",
        "co_usuario": "k7m3p9rt",
        "co_identidade_externa": uid,
        "no_exibicao": "Antigo",
        "no_email": "a@b.com",
        "dt_nascimento": date(1990, 1, 1),
        "co_provedor_principal": "email",
        "co_idioma_preferido": "pt",
        "ic_convidado": False,
    }


def test_reentrada_preserva_nome_existente():
    # REGRA: a sessão (login) NÃO sobrescreve um nome já salvo. O nome que vem do
    # provedor a cada login é ignorado quando o usuário já tem um nome no banco.
    repo = FakeRepoUsuario(existente=_conta_existente())  # no_exibicao="Antigo"
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(), SessaoRequest(no_exibicao="Nome Do Provedor")
        )
    )
    # Mesma conta, nome PRESERVADO, nada criado.
    assert perfil.co_usuario == "k7m3p9rt"
    assert perfil.no_exibicao == "Antigo"
    assert repo.criadas == []


def test_reentrada_preenche_nome_quando_vazio():
    # Se o nome no banco está VAZIO, aí sim a sessão aceita o nome do provedor.
    conta = _conta_existente()
    conta["no_exibicao"] = None
    repo = FakeRepoUsuario(existente=conta)
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(), SessaoRequest(no_exibicao="Nome Do Provedor")
        )
    )
    assert perfil.no_exibicao == "Nome Do Provedor"


def test_obter_perfil_inexistente_responde_404():
    with pytest.raises(ErroNaoEncontrado):
        asyncio.run(_servico(FakeRepoUsuario()).obter_perfil(_identidade()))


def test_reentrada_vincula_provedor_atual():
    # Conta criada por e-mail; agora a pessoa entra com Google → o provedor
    # Google passa a constar vinculado (antes só o de criação aparecia).
    repo = FakeRepoUsuario(existente=_conta_existente())
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(provedor="google.com"), SessaoRequest()
        )
    )
    assert "google" in perfil.provedores


# ── moderação de nome na sessão (NEG-01) ─────────────────────────────────────


def test_criacao_com_nome_proibido_grava_none_nao_derruba_login():
    # Nome reprovado na moderação (contém "admin") NÃO derruba o login: a conta é
    # criada, mas sem apelido (fica None) — a pessoa define depois pelo PATCH.
    repo = FakeRepoUsuario()
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(),
            SessaoRequest(no_exibicao="admin", dt_nascimento=date(1990, 1, 1)),
        )
    )
    assert perfil.no_exibicao is None
    assert len(repo.criadas) == 1


def test_criacao_com_nome_curto_grava_none():
    repo = FakeRepoUsuario()
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(),
            SessaoRequest(no_exibicao="ab", dt_nascimento=date(1990, 1, 1)),
        )
    )
    assert perfil.no_exibicao is None


def test_reentrada_preenche_nome_vazio_passa_por_moderacao():
    # Nome do provedor reprovado NÃO preenche o vazio (fica None).
    conta = _conta_existente()
    conta["no_exibicao"] = None
    repo = FakeRepoUsuario(existente=conta)
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(), SessaoRequest(no_exibicao="moderador")
        )
    )
    assert perfil.no_exibicao is None


# ── revalidação de idade ao trocar data de nascimento (NEG-02) ───────────────


def test_reentrada_trocar_data_para_menor_de_13_responde_422():
    hoje = date.today()
    menor = date(hoje.year - 8, hoje.month, max(1, hoje.day))
    repo = FakeRepoUsuario(existente=_conta_existente())
    with pytest.raises(ErroNegocio) as exc:
        asyncio.run(
            _servico(repo).garantir_sessao(
                _identidade(), SessaoRequest(dt_nascimento=menor)
            )
        )
    assert exc.value.codigo == "idade_minima"
    assert exc.value.status_http == 422


def test_reentrada_corrigir_data_mantendo_maioridade_ok():
    # Corrigir a data para outra data de ADULTO é permitido (usabilidade).
    repo = FakeRepoUsuario(existente=_conta_existente())
    nova = date(1988, 5, 20)
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(), SessaoRequest(dt_nascimento=nova)
        )
    )
    assert perfil.dt_nascimento == nova
