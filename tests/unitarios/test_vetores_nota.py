"""🔒 OS VETORES DA NOTA: o servidor e o app calculam o mesmo XP (T106).

O que estes casos protegem:

  · ⚠️ **a conta do servidor nao muda calada**: o documento e regenerado em
    memoria pela conta de hoje (`montar_extrato` + `pontuacao_do_extrato`) e
    comparado com o arquivo. Uma mudanca na regua, na curva ou no arredondamento
    reprova aqui - e o conserto e consciente: um vetor NOVO, ou a explicacao de
    por que o antigo descrevia algo impossivel;
  · **as duas copias sao byte-identicas** (SHA-256): a do app roda em
    `test/core/desafios/vetores_nota_test.dart`, contra `qualidade.dart`;
  · **as duas reguas estao representadas**: a 1 (os dias antigos) e a 2.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.gerar_vetores_nota import (
    SAIDA_APP,
    SAIDA_BACKEND,
    texto_do_documento,
)


def test_o_arquivo_e_o_que_a_conta_do_servidor_produz_HOJE():
    """⚠️ Se reprovar, a conta do servidor mudou - de proposito ou nao.

    Regenere com `scripts/gerar_vetores_nota.py` SO depois de entender a
    diferenca: um vetor e um caso que o app tambem tem de passar.
    """
    assert SAIDA_BACKEND.read_text(encoding="utf-8") == texto_do_documento()


def test_as_duas_copias_sao_byte_identicas():
    """A do app e a mesma que o servidor confere."""
    if not SAIDA_APP.exists():
        pytest.skip("o repositorio do app nao esta ao lado deste")
    backend = hashlib.sha256(SAIDA_BACKEND.read_bytes()).hexdigest()
    app = hashlib.sha256(SAIDA_APP.read_bytes()).hexdigest()
    assert backend == app


def test_ha_vetores_das_DUAS_reguas():
    """Um documento so com uma versao deixaria a outra sem prova."""
    documento = json.loads(SAIDA_BACKEND.read_text(encoding="utf-8"))
    versoes = {v["regua_nota"]["versao"] for v in documento["vetores"]}
    assert versoes == {1, 2}


def test_os_perfis_da_8zzo_estao_nos_vetores():
    """Os numeros da tabela que o dono aprovou, escritos a mao (§8zzo)."""
    documento = json.loads(SAIDA_BACKEND.read_text(encoding="utf-8"))
    pontuacao = {v["id"]: v["esperado"]["pontuacao"] for v in documento["vetores"]}
    assert [
        pontuacao["v2-1a-sem-dica-no-piso"],
        pontuacao["v2-1a-sem-dica-3x-o-piso"],
        pontuacao["v2-1a-1-dica-2x-o-piso"],
        pontuacao["v2-2a-sem-dica-2x-o-piso"],
        pontuacao["v2-9-tentativas-no-piso"],
        pontuacao["v2-4-tentativas-2-dicas-3x"],
        pontuacao["v2-30-tentativas-10-dicas-20x"],
    ] == [30, 29, 28, 25, 22, 20, 16]
    # O empate que motivou a regua: 25 x 25 na regua 1, 23 x 22 na 2.
    assert pontuacao["v1-fernando-25"] == 25
    assert pontuacao["v2-maria-2-tentativas-2-dicas-54s"] == 23
    assert pontuacao["v2-fernando-9-tentativas-38s"] == 22
