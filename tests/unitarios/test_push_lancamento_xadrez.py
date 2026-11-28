"""Testes do script do push de lançamento do Xadrez (`scripts/push_lancamento_xadrez.py`).

Não enviam nada: conferem só o que o script MONTA. O objetivo é pegar, antes de
um envio de produção, os erros que o FCM não acusa - um tópico com nome errado
devolve sucesso e não chega a ninguém.
"""
import importlib.util
from pathlib import Path

import pytest

from api.notificacoes.servico import ServicoNotificacoes

# O script não é um pacote importável (`scripts/` não tem `__init__.py`), então
# ele é carregado pelo caminho do arquivo. `parents[2]` sobe de
# `tests/unitarios/` até `arena-sagaz-backend/`.
_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "push_lancamento_xadrez.py"
_spec = importlib.util.spec_from_file_location("push_lancamento_xadrez", _CAMINHO)
push = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(push)


@pytest.mark.parametrize("idioma", ["pt", "en", "es"])
def test_cada_idioma_vai_para_o_seu_topico_e_so_para_quem_quer_novidades(idioma):
    """O destino real tem de ser `todos_<idioma>` E `novidades`, nessa condição.

    Passa o corpo montado pelo MESMO serviço que a rota usa, com um enviador
    falso que só anota o destino - é a conferência que o FCM não faz.
    """
    destinos = []

    def enviador_falso(titulo, corpo, dados, topico, condicao):
        destinos.append((topico, condicao, dados))
        return "id-falso"

    corpo = push.montar_corpo(idioma)
    ServicoNotificacoes(enviador_falso).enviar_broadcast(
        titulo=corpo["titulo"],
        corpo=corpo["corpo"],
        dados=corpo["dados"],
        idioma=corpo["idioma"],
        topicos=corpo["topicos"],
    )

    topico, condicao, dados = destinos[0]
    assert topico is None
    assert condicao == f"'todos_{idioma}' in topics && 'novidades' in topics"
    # O toque leva à Home, que toda versão em campo conhece.
    assert dados == {"rota": "/home"}


def test_os_tres_idiomas_tem_textos_diferentes():
    """Um texto copiado sem traduzir chegaria no idioma errado para alguém."""
    titulos = {push.TEXTOS[i]["titulo"] for i in ("pt", "en", "es")}
    corpos = {push.TEXTOS[i]["corpo"] for i in ("pt", "en", "es")}
    assert len(titulos) == 3 and len(corpos) == 3


def test_a_plataforma_entra_na_condicao_quando_pedida():
    """Com `--plataforma android`, o iOS fica de fora (ex.: Apple ainda não aprovou)."""
    corpo = push.montar_corpo("pt", plataforma="android")
    assert corpo["plataforma"] == "android"
    assert "plataforma" not in push.montar_corpo("pt")
