"""As provas do xadrez e o xadrez no gerador e na regua (spec 012, T076).

O que se confere:

  1. ⛔ o cadeado: `PROVAS` tem exatamente os onze tipos do xadrez;
  2. as recusas baratas: o objetivo no 1o lance, a espia presa, a classe que
     come sem lance; e a posicao boa passa;
  3. o sorteio dos problemas de mate (so os que cabem na janela, o mesmo dia
     da o mesmo problema, o formato do contrato §1);
  4. o jogador do desafio (o estado com o FEN de depois, a vez que alterna, a
     semente obrigatoria);
  5. o gerador de ponta a ponta: um candidato do mate (o Magno cru) e um da
     base (com o perseguidor), com gabarito que o juiz
     julga cumprido, e reprodutivel pela data;
  6. a bancada da regua mede um candidato do xadrez;
  7. ⛔ os tipos do xadrez em `SOLUCIONADOR_POR_TIPO` sao os dez sem vitoria.
"""

from __future__ import annotations

import random
import threading
from datetime import date

import pytest

from job import gerador as gerador_mod
from job import posicao_inicial as posicao_mod
from job import provas_xadrez as pv
from job import regua as regua_mod
from job.editorial import EDITORIAL_FORA_DO_AR
from job.posicoes_xadrez import SemPosicaoXadrez
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR
from motores.juiz import julgar_desafio
from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorDartIndisponivel

#: Os onze tipos do xadrez, das receitas (no ar ou fora dele).
TIPOS_DO_XADREZ = {
    t for t, r in {**RECEITAS, **RECEITAS_FORA_DO_AR}.items() if r.co_jogo == "xadrez"
}


@pytest.fixture(scope="module")
def motor():
    """O executavel, ou o pulo com a receita."""
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executavel do xadrez compilado: {erro}")


def _posicao(fen: str, **extra) -> dict:
    return {
        "jogo": "xadrez", "modalidade": "tradicional", "fen": fen,
        "cor_da_pessoa": "branca", **extra, "origem": "base_equilibrada",
    }


def _chegada(co_tipo: str, **parametros) -> dict:
    return RECEITAS_FORA_DO_AR[co_tipo].montar(parametros)


# ═══════════════════════════════════════════════════════════════════════════
# 1. O cadeado e as recusas
# ═══════════════════════════════════════════════════════════════════════════


def test_provas_tem_exatamente_os_doze_tipos_do_xadrez():
    """Os onze da 1.6.0 (com as duas espias) e a troca, que saiu do ar e
    continua no banco (§8zzzz64)."""
    assert len(TIPOS_DO_XADREZ) == 12
    assert set(pv.PROVAS) == TIPOS_DO_XADREZ


def test_tipo_sem_prova_falha_alto(motor):
    with pytest.raises(KeyError, match="nao tem prova"):
        pv.provar("xadrez_inventado", _posicao("7k/8/8/8/8/8/8/6K1 w - - 0 1"), {}, motor=motor)


def test_o_objetivo_no_primeiro_lance_e_recusado(motor):
    """O cavalo espiao come o alvo de cara: resolve-se num toque."""
    posicao = _posicao("7k/p7/8/3b4/8/2N5/P7/6K1 w - - 0 1", marcas={"espia": "c3", "alvo": "d5"})
    prova = pv.provar("xadrez_espia_alvo", posicao, _chegada("xadrez_espia_alvo", lances=8), motor=motor)
    assert not prova.passou and "1o lance" in prova.motivo


def test_a_espia_presa_e_recusada_nos_tipos_em_que_ela_anda(motor):
    """A torre espia de a1, presa pelo peao de a2 e pelo cavalo de b1."""
    posicao = _posicao("7k/p7/8/8/8/8/P7/RN4K1 w - - 0 1", marcas={"espia": "a1"})
    comer = pv.provar(
        "xadrez_espia_comer", posicao, _chegada("xadrez_espia_comer", capturas=2, lances=8), motor=motor
    )
    assert not comer.passou and "espia" in comer.motivo
    # No proteger ela pode ficar parada: so a recusa comum vale.
    proteger = pv.provar(
        "xadrez_espia_proteger", posicao, _chegada("xadrez_espia_proteger", lances=10), motor=motor
    )
    assert proteger.passou, proteger.motivo


def test_a_classe_que_come_sem_lance_e_recusada(motor):
    posicao = _posicao("7k/p7/8/8/8/8/P7/RN4K1 w - - 0 1", classes={"come": "torre"})
    prova = pv.provar(
        "xadrez_comer_com", posicao, _chegada("xadrez_comer_com", capturas=2, lances=8, come="torre"),
        motor=motor,
    )
    assert not prova.passou and "torre" in prova.motivo


def test_a_posicao_boa_passa(motor):
    posicao = _posicao("7k/p7/8/8/8/2N5/P7/6K1 w - - 0 1", marcas={"espia": "c3"})
    prova = pv.provar(
        "xadrez_espia_comer", posicao, _chegada("xadrez_espia_comer", capturas=2, lances=8), motor=motor
    )
    assert prova.passou, prova.motivo


# ═══════════════════════════════════════════════════════════════════════════
# 2. Os problemas de mate
# ═══════════════════════════════════════════════════════════════════════════


def test_o_problema_cabe_na_janela_e_tem_o_formato_do_contrato():
    for lances in (2, 3, 5):
        escolhida = pv.sortear_problema_de_mate(random.Random(lances), lances=lances)
        posicao = escolhida.js_posicao_inicial
        assert list(posicao) == ["jogo", "modalidade", "fen", "cor_da_pessoa", "origem"]
        assert posicao["origem"] == pv.ORIGEM_PROBLEMAS_LICHESS and escolhida.pecas == {}
        problema = next(p for p in pv.carregar_problemas_de_mate() if p["fen"] == posicao["fen"])
        assert problema["mate_em"] <= lances
        assert posicao["cor_da_pessoa"] == problema["cor_da_pessoa"]


def test_o_mesmo_sorteio_da_o_mesmo_problema():
    a = pv.sortear_problema_de_mate(random.Random(99), lances=5)
    b = pv.sortear_problema_de_mate(random.Random(99), lances=5)
    assert a == b


def test_janela_sem_problema_e_recusada():
    with pytest.raises(SemPosicaoXadrez):
        pv.sortear_problema_de_mate(random.Random(1), lances=1)


def _mates_em_2(quantos: int) -> list[dict]:
    """Os primeiros [quantos] problemas de mate em 2 do acervo."""
    return [p for p in pv.carregar_problemas_de_mate() if p["mate_em"] == 2][:quantos]


def _calibracao(ids_por_adversario: dict, **outros) -> dict:
    """Uma calibracao do motor de hoje, com N = 2, para os testes."""
    from motores.xadrez import contrato_xadrez

    return {
        "versao_do_motor": contrato_xadrez.versao_do_motor(),
        "lances": 2,
        "execucoes": 20,
        "na_escada_contra": ids_por_adversario,
        **outros,
    }


def test_com_o_adversario_o_mate_sai_so_dos_problemas_calibrados_contra_ele(capsys):
    """21/11/2026: o sorteio escolhe entre os que cairam na escada contra o
    adversario do dia, e nao entre os da Pita quando o adversario e o Tex."""
    a, b, c = _mates_em_2(3)
    calibracao = _calibracao({"tex": [a["id"], b["id"]], "pita": [c["id"]]})
    sorteados = {
        pv.sortear_problema_de_mate(
            random.Random(semente), lances=2, co_personagem="tex", calibracao=calibracao
        ).js_posicao_inicial["fen"]
        for semente in range(40)
    }
    assert sorteados == {a["fen"], b["fen"]}
    # Calibracao que serve nao avisa nada.
    assert "[mate]" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "calibracao, motivo",
    [
        (None, "sem calibracao_do_mate.json"),
        ({"versao_do_motor": "rust_0.0.1", "lances": 2, "na_escada_contra": {}}, "motor rust_0.0.1"),
        ("outro N", "N=3"),
        ("sem o adversario", "nenhum problema calibrado contra tex"),
    ],
)
def test_calibracao_que_nao_serve_volta_ao_acervo_inteiro_e_avisa(capsys, calibracao, motivo):
    """Sem arquivo, de outro motor, de outro N ou sem o adversario: o desafio sai
    do acervo inteiro (o job nao para), e o log diz por que."""
    a = _mates_em_2(1)[0]
    if calibracao == "outro N":
        calibracao = _calibracao({"tex": [a["id"]]}, lances=3)
    elif calibracao == "sem o adversario":
        calibracao = _calibracao({"pita": [a["id"]]})
    cabem = _mates_em_2(50)
    escolhidos = pv.problemas_calibrados(
        cabem,
        lances=2,
        co_personagem="tex",
        calibracao=calibracao,
        versao_do_motor=_calibracao({})["versao_do_motor"],
    )
    assert escolhidos == cabem
    saida = capsys.readouterr().out
    assert "acervo inteiro" in saida and motivo in saida


def test_sem_adversario_o_acervo_e_inteiro_e_calado(capsys):
    """A medicao pareada e os testes antigos nao passam adversario: nada muda."""
    cabem = _mates_em_2(10)
    assert pv.problemas_calibrados(
        cabem, lances=2, co_personagem=None, calibracao=None, versao_do_motor="x"
    ) == cabem
    assert capsys.readouterr().out == ""


def test_sortear_posicao_leva_o_adversario_ao_mate(monkeypatch):
    a = _mates_em_2(1)[0]
    monkeypatch.setattr(pv, "carregar_calibracao_do_mate", lambda: _calibracao({"magno": [a["id"]]}))
    escolhida = pv.sortear_posicao(
        random.Random(5), co_tipo="xadrez_dar_mate", parametros={"lances": 2}, co_personagem="magno"
    )
    assert escolhida.js_posicao_inicial["fen"] == a["fen"]


def test_o_xadrez_pede_doze_candidatos_por_dia_e_os_outros_tres():
    """21/11/2026, depois da 4a, da 5a e da 6a reguas: a mesma funcao serve o
    job e a medicao."""
    assert gerador_mod.candidatos_por_dia("xadrez") == 12
    for jogo in ("pontinhos", "damas", "quatro"):
        assert gerador_mod.candidatos_por_dia(jogo) == gerador_mod.CANDIDATOS_POR_DIA_PADRAO == 3


def test_o_job_pede_ao_gerador_o_numero_do_jogo():
    """O job nao pode voltar a uma constante unica: o xadrez mediria 12 e publicaria de 3."""
    from pathlib import Path

    fonte = (Path(gerador_mod.__file__).parent / "__main__.py").read_text(encoding="utf-8")
    assert "quantos=gerador_mod.candidatos_por_dia(co_jogo)" in fonte
    assert "quantos=CANDIDATOS_POR_DIA," not in fonte


def test_o_mate_vem_dos_problemas_e_os_outros_da_base():
    mate = pv.sortear_posicao(random.Random(3), co_tipo="xadrez_dar_mate", parametros={"lances": 5})
    assert mate.js_posicao_inicial["origem"] == pv.ORIGEM_PROBLEMAS_LICHESS
    espia = pv.sortear_posicao(random.Random(3), co_tipo="xadrez_espia_comer", parametros={"capturas": 2, "lances": 8})
    assert espia.js_posicao_inicial["origem"] == "base_equilibrada" and "espia" in espia.pecas


# ═══════════════════════════════════════════════════════════════════════════
# 3. O jogador do desafio
# ═══════════════════════════════════════════════════════════════════════════


def test_o_jogador_aplica_com_o_fen_de_depois_e_a_vez_alterna(motor):
    jogador = pv.JogadorDoDesafioXadrez(motor)
    inicial = pv.estado_inicial(_posicao("7k/p7/8/8/8/2N5/P7/6K1 w - - 0 1"))
    assert inicial.fen == inicial.fen_inicial and jogador.arbitro.vez_de(inicial) == 1
    depois = jogador.aplicar(inicial, "c3d5")
    assert depois.lances == ("c3d5",) and depois.fen.startswith("7k/p7/8/3N4/")
    assert jogador.arbitro.vez_de(depois) == -1


def test_o_jogador_exige_a_semente_e_devolve_o_motivo(motor):
    jogador = pv.JogadorDoDesafioXadrez(motor)
    inicial = pv.estado_inicial(_posicao("7k/p7/8/8/8/2N5/P7/6K1 w - - 0 1"))
    with pytest.raises(ValueError, match="semente"):
        jogador.escolher_lance(inicial, NivelDeMotor.TEX)
    decisao = jogador.decidir(inicial, NivelDeMotor.TEX, semente=5)
    assert decisao.co_acao in {"busca_melhor", "erro_sorteado", "cegueira", "mate_em_um", "lance_unico"}
    assert jogador.escolher_lance(inicial, NivelDeMotor.TEX, semente=5) == decisao.lance


def test_cada_thread_fala_com_o_seu_processo(monkeypatch):
    """⛔ O cadeado do paralelo da regua: o jogador NAO guarda o processo de quem
    perguntou primeiro. Com a guarda, a 2a thread escreveria no `stdin` da 1a e
    leria as respostas trocadas, sem erro nenhum."""
    local = threading.local()
    abertos: list[object] = []

    def compartilhado():
        if not hasattr(local, "motor"):
            local.motor = object()
            abertos.append(local.motor)
        return local.motor

    monkeypatch.setattr(pv, "jogador_compartilhado", compartilhado)
    jogador = pv.JogadorDoDesafioXadrez()
    vistos: dict[str, object] = {}

    def pergunta(nome: str) -> None:
        vistos[nome] = jogador.motor

    pergunta("principal")
    outra = threading.Thread(target=pergunta, args=("outra",))
    outra.start()
    outra.join()
    assert vistos["principal"] is not vistos["outra"] and len(abertos) == 2
    # Na mesma thread, o mesmo processo de novo (sem abrir um terceiro).
    assert jogador.motor is vistos["principal"] and len(abertos) == 2


def test_a_pessoa_do_xadrez_e_mais_um_e_os_outros_leem_a_posicao():
    assert posicao_mod.vez_de_quem_resolve({"jogo": "xadrez", "cor_da_pessoa": "preta"}) == 1
    assert posicao_mod.vez_de_quem_resolve({"vez_de": -1}) == -1
    with pytest.raises(KeyError):
        posicao_mod.vez_de_quem_resolve({"co_jogo": "quatro"})


def test_o_xadrez_e_fen_tem_versao_de_motor_e_regua_paralela():
    assert posicao_mod.formato_do_jogo("xadrez") == posicao_mod.FORMATO_FEN
    assert gerador_mod.versao_do_motor_de("xadrez")
    assert regua_mod.PARALELISMO_POR_JOGO["xadrez"] == "maquina"
    assert gerador_mod.MODALIDADES_POR_JOGO["xadrez"] == ("tradicional",)


def test_os_tipos_ligados_ao_perseguidor_sao_os_dez_sem_vitoria():
    """⛔ `DECISOES-do-dono.md` §8zzzz57: o perseguidor entra tipo a tipo, so
    depois do controle e da medicao pareada. A T076a ligou nove; o
    `xadrez_espia_comer` entrou na 2a medicao (a espia que age nunca e peao).
    O `xadrez_dar_mate` nunca entra (vencer e o objetivo). Mudou a lista? Mude
    este teste junto, com o numero da medicao no `gerador.py`."""
    ligados = TIPOS_DO_XADREZ & set(gerador_mod.SOLUCIONADOR_POR_TIPO)
    assert ligados == TIPOS_DO_XADREZ - {"xadrez_dar_mate"}


def test_o_xadrez_aceita_o_erro_do_adversario():
    """`DECISOES-do-dono.md` §8zzzz59: sem recusa por erro, como damas e Quatro."""
    assert "xadrez" not in gerador_mod.RECUSA_POR_JOGO


# ═══════════════════════════════════════════════════════════════════════════
# 4. O gerador de ponta a ponta
# ═══════════════════════════════════════════════════════════════════════════


def _gerar(co_tipo: str, dia: date) -> gerador_mod.Candidato:
    """Um candidato de [co_tipo] (fora do ar: pela porta da medicao)."""
    publicacao = EDITORIAL_FORA_DO_AR[co_tipo][0]
    candidatos = gerador_mod.gerar_candidatos(
        dia,
        parametros=publicacao.parametros,
        quantos=1,
        tentativas_por_candidato=4,
        maximo_de_meios_lances=publicacao.nu_maximo_de_meios_lances,
        minimo_de_meios_lances=publicacao.nu_minimo_de_meios_lances,
        receita_em_avaliacao=RECEITAS_FORA_DO_AR[co_tipo],
    )
    assert candidatos, f"{co_tipo}: nenhum candidato em {dia}"
    return candidatos[0]


def _conferir_gabarito(candidato: gerador_mod.Candidato) -> None:
    """O juiz julga o gabarito cumprido, e cada passo traz o FEN de depois."""
    fita = candidato.js_solucao["lances"]
    julgamento = julgar_desafio(
        co_jogo="xadrez",
        js_posicao_inicial=candidato.js_posicao_inicial,
        js_chegada=candidato.js_chegada,
        fita=fita,
        jogador=1,
    )
    assert julgamento.cumpriu
    # A pessoa comeca, e a vez alterna.
    assert [l["jogador"] for l in fita] == [1 if i % 2 == 0 else -1 for i in range(len(fita))]
    assert len(candidato.js_solucao.get("posicoes", [])) == len(fita)


def test_o_gerador_tira_um_desafio_de_mate_do_banco_de_problemas(motor):
    candidato = _gerar("xadrez_dar_mate", date(2026, 12, 1))
    assert candidato.co_jogo == "xadrez" and candidato.co_formato_posicao == "fen"
    assert candidato.js_posicao_inicial["origem"] == pv.ORIGEM_PROBLEMAS_LICHESS
    assert candidato.co_variante == candidato.co_modalidade == "tradicional"
    _conferir_gabarito(candidato)


def test_o_gerador_tira_um_desafio_da_base_com_o_perseguidor(motor):
    """Com o perseguidor (ligado na T076a), o `xadrez_espia_proteger` sai com a
    espia e o gabarito cumprido, e a mesma data da o mesmo desafio."""
    assert "xadrez_espia_proteger" in gerador_mod.SOLUCIONADOR_POR_TIPO
    dia = date(2026, 12, 2)
    candidato = _gerar("xadrez_espia_proteger", dia)
    assert "espia" in candidato.js_posicao_inicial["marcas"]
    # A classe da espia entrou nos parametros e na frase.
    assert candidato.parametros["espia"] == candidato.js_objetivo["espia"]
    _conferir_gabarito(candidato)
    de_novo = _gerar("xadrez_espia_proteger", dia)
    assert de_novo.js_posicao_inicial == candidato.js_posicao_inicial
    assert de_novo.js_solucao == candidato.js_solucao


def test_o_gerador_leva_o_adversario_do_dia_ao_sorteio_do_mate(motor, monkeypatch):
    """Com uma calibracao de um problema so para cada adversario, o candidato do
    mate sai daquele problema: o gerador passou o personagem do dia adiante."""
    a = _mates_em_2(1)[0]
    todos = {p: [a["id"]] for p in ("cacau", "pita", "tex", "magno")}
    monkeypatch.setattr(pv, "carregar_calibracao_do_mate", lambda: _calibracao(todos))
    candidato = _gerar("xadrez_dar_mate", date(2026, 12, 3))
    assert candidato.js_posicao_inicial["fen"] == a["fen"]


def test_a_bancada_da_regua_mede_um_candidato_do_xadrez(motor):
    candidato = _gerar("xadrez_dar_mate", date(2026, 12, 1))
    bancada = gerador_mod.bancada(candidato)
    tentar = regua_mod.tentativa_com_motor(
        jogador=bancada.jogador,
        estado_inicial=bancada.estado_inicial,
        julgar=bancada.julgar,
        nu_semente=candidato.nu_semente,
        maximo_de_meios_lances=EDITORIAL_FORA_DO_AR["xadrez_dar_mate"][0].nu_maximo_de_meios_lances,
        co_personagem_do_dia=candidato.co_personagem,
        solucionador=bancada.solucionador,
    )
    # O Magno da o mate forcado do problema, com qualquer semente.
    assert tentar("magno", 1) is True
