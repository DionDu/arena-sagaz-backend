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


def test_reentrada_nao_duplica_e_atualiza_nome():
    repo = FakeRepoUsuario(existente=_conta_existente())
    perfil = asyncio.run(
        _servico(repo).garantir_sessao(
            _identidade(), SessaoRequest(no_exibicao="Novo Nome")
        )
    )
    # Mesma conta (mesmo código), nome atualizado, nada criado.
    assert perfil.co_usuario == "k7m3p9rt"
    assert perfil.no_exibicao == "Novo Nome"
    assert repo.criadas == []


def test_obter_perfil_inexistente_responde_404():
    with pytest.raises(ErroNaoEncontrado):
        asyncio.run(_servico(FakeRepoUsuario()).obter_perfil(_identidade()))
