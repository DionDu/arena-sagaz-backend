"""O contrato do Quatro em Linha, lido do espelho (spec 010, T104).

O que se confere:
  - o contrato do espelho carrega, com as dimensões e os quatro personagens, e
    os números saem IGUAIS aos do JSON (nada é reescrito no caminho);
  - a modalidade desconhecida e o marcador `teto_de_nos: 0` são recusados, e
    cada recusa diz o porquê;
  - a modalidade de três níveis recusa o Sagaz;
  - o pedido ao executável sai com os nomes do contrato §3;
  - o SHA-256 é o dos bytes, e a versão do motor tem a forma `quatro-dart-`.

Os casos de recusa usam um contrato escrito no `tmp_path`, com uma modalidade
de nome inventado: é o que mostra que o módulo não conhece modalidade pelo nome.
"""

import copy
import hashlib
import json
import re

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import contrato_quatro as cq


@pytest.fixture
def contrato_de_teste(tmp_path, monkeypatch):
    """Troca o contrato do espelho por um escrito pelo teste.

    Devolve uma função: ela recebe o dicionário, grava, aponta o módulo para o
    arquivo e limpa o cache (senão o módulo continuaria com o contrato que leu
    antes).
    """

    def _usar(dados: dict) -> None:
        caminho = tmp_path / "contrato_quatro.json"
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        monkeypatch.setattr(cq, "CAMINHO_DO_CONTRATO", caminho)
        cq._bytes_do_contrato.cache_clear()

    yield _usar
    # Depois do teste, o próximo volta a ler o contrato verdadeiro.
    cq._bytes_do_contrato.cache_clear()


def _contrato_real() -> dict:
    """O contrato do espelho, cru, para comparar e para derivar variantes."""
    return json.loads(cq.CAMINHO_DO_CONTRATO.read_text(encoding="utf-8"))


def _variante(**troca_no_nivel) -> dict:
    """Uma cópia do contrato real com a modalidade renomeada para `sonda_x`.

    `troca_no_nivel` muda campos do nível `tex`, para os casos de recusa.
    """
    real = _contrato_real()
    [entrada] = real["por_modalidade"].values()
    entrada = copy.deepcopy(entrada)
    entrada["niveis"]["tex"].update(troca_no_nivel)
    return {"versao": real["versao"], "por_modalidade": {"sonda_x": entrada}}


class TestOContratoDoEspelho:
    def test_declara_ao_menos_uma_modalidade_com_tabuleiro(self):
        modalidades = cq.modalidades_declaradas()
        assert modalidades, "o contrato do espelho veio sem modalidade"
        for modalidade in modalidades:
            d = cq.dimensoes(modalidade)
            # Cabe no bitboard do motor (63 bits, uma sentinela por coluna).
            assert d.largura * (d.altura + 1) <= 63
            assert 2 <= d.alinhar <= max(d.largura, d.altura)

    def test_os_numeros_saem_iguais_aos_do_json(self):
        real = _contrato_real()
        for modalidade, entrada in real["por_modalidade"].items():
            for nivel, personagem in cq.PERSONAGEM_DO_NIVEL.items():
                if personagem not in entrada["niveis_disponiveis"]:
                    continue
                p = cq.parametros_do_personagem(modalidade, nivel)
                bruto = entrada["niveis"][personagem]
                assert p.personagem == personagem
                assert p.teto_de_nos == bruto["teto_de_nos"]
                assert p.epsilon == bruto["epsilon"]
                assert dict(p.percebe) == bruto["percebe"]

    def test_so_o_magno_leva_a_abertura(self):
        [modalidade, *_] = cq.modalidades_declaradas()
        magno = cq.parametros_do_personagem(modalidade, NivelDeMotor.SAGAZ)
        assert magno.personagem == "magno"
        assert magno.abertura_do_magno is not None
        # A coluna é inteiro de 1 à largura, e as chances somam 1.
        largura = cq.dimensoes(modalidade).largura
        assert set(magno.abertura_do_magno) <= set(range(1, largura + 1))
        assert sum(magno.abertura_do_magno.values()) == pytest.approx(1)
        for nivel in (NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX):
            assert cq.parametros_do_personagem(modalidade, nivel).abertura_do_magno is None

    def test_o_pedido_sai_com_os_nomes_do_contrato_do_motor(self):
        [modalidade, *_] = cq.modalidades_declaradas()
        pedido = cq.parametros_do_personagem(modalidade, NivelDeMotor.SAGAZ).para_pedido()
        assert set(pedido) == {"tetoDeNos", "epsilon", "percebe", "aberturaDoMagno"}
        # Em JSON a chave é texto: a coluna 4 vai como "4".
        assert all(isinstance(c, str) for c in pedido["aberturaDoMagno"])
        assert cq.parametros_do_personagem(
            modalidade, NivelDeMotor.CACAU
        ).para_pedido()["aberturaDoMagno"] is None

    def test_os_parametros_nao_se_alteram_por_fora(self):
        [modalidade, *_] = cq.modalidades_declaradas()
        p = cq.parametros_do_personagem(modalidade, NivelDeMotor.TEX)
        with pytest.raises(TypeError):
            p.percebe["vencer"] = 0  # type: ignore[index]

    def test_o_sha256_e_o_dos_bytes_do_arquivo(self):
        esperado = hashlib.sha256(cq.CAMINHO_DO_CONTRATO.read_bytes()).hexdigest()
        assert cq.sha256_do_contrato() == esperado

    def test_a_versao_do_motor_tem_a_forma_do_carimbo(self):
        assert re.fullmatch(r"quatro-dart-[0-9a-f]{8}", cq.versao_do_motor())
        caminhos = [a["caminho"] for a in cq.arquivos_do_motor()]
        # O pacote inteiro e o contrato, e nada de outro jogo.
        assert all(c.startswith("jogos/jogo_quatro/") for c in caminhos)
        assert any(c.endswith("/contrato_quatro.json") for c in caminhos)
        assert any(c.endswith("/busca_quatro.dart") for c in caminhos)
        assert caminhos == sorted(caminhos)


class TestAsRecusas:
    def test_a_modalidade_que_o_contrato_nao_declara(self):
        with pytest.raises(cq.ModalidadeDesconhecida, match="não declara"):
            cq.dimensoes("pop_out_que_nao_existe")
        with pytest.raises(cq.ModalidadeDesconhecida):
            cq.parametros_do_personagem("pop_out_que_nao_existe", NivelDeMotor.TEX)

    def test_o_modulo_le_qualquer_modalidade_que_o_contrato_traga(self, contrato_de_teste):
        contrato_de_teste(_variante())
        assert cq.modalidades_declaradas() == ("sonda_x",)
        assert cq.parametros_do_personagem("sonda_x", NivelDeMotor.TEX).personagem == "tex"

    def test_o_teto_zero_e_o_marcador_de_nao_medido(self, contrato_de_teste):
        contrato_de_teste(_variante(teto_de_nos=0))
        with pytest.raises(cq.ContratoQuatroInvalido, match="não medido"):
            cq.parametros_do_personagem("sonda_x", NivelDeMotor.TEX)
        # Os outros níveis da mesma modalidade continuam jogando.
        assert cq.parametros_do_personagem("sonda_x", NivelDeMotor.PITA).teto_de_nos > 0

    @pytest.mark.parametrize("teto", [-5, 1.5, "100", True, None])
    def test_o_teto_que_nao_e_inteiro_positivo(self, contrato_de_teste, teto):
        contrato_de_teste(_variante(teto_de_nos=teto))
        with pytest.raises(cq.ContratoQuatroInvalido, match="teto_de_nos"):
            cq.parametros_do_personagem("sonda_x", NivelDeMotor.TEX)

    def test_o_percebe_sem_uma_situacao(self, contrato_de_teste):
        contrato_de_teste(_variante(percebe={"vencer": 1, "bloquear": 0.5}))
        with pytest.raises(cq.ContratoQuatroInvalido, match="percebe"):
            cq.parametros_do_personagem("sonda_x", NivelDeMotor.TEX)

    def test_o_epsilon_fora_de_0_a_1(self, contrato_de_teste):
        contrato_de_teste(_variante(epsilon=1.5))
        with pytest.raises(cq.ContratoQuatroInvalido, match="epsilon"):
            cq.parametros_do_personagem("sonda_x", NivelDeMotor.TEX)

    def test_a_modalidade_de_tres_niveis_recusa_o_sagaz(self, contrato_de_teste):
        dados = _variante()
        entrada = dados["por_modalidade"]["sonda_x"]
        entrada["niveis_disponiveis"] = ["cacau", "pita", "tex"]
        del entrada["niveis"]["magno"]
        contrato_de_teste(dados)
        with pytest.raises(cq.ContratoQuatroInvalido, match="não oferece"):
            cq.parametros_do_personagem("sonda_x", NivelDeMotor.SAGAZ)
        assert cq.niveis_disponiveis("sonda_x") == ("cacau", "pita", "tex")

    def test_a_dimensao_que_nao_e_inteiro_positivo(self, contrato_de_teste):
        dados = _variante()
        dados["por_modalidade"]["sonda_x"]["altura"] = 0
        contrato_de_teste(dados)
        with pytest.raises(cq.ContratoQuatroInvalido, match="altura"):
            cq.dimensoes("sonda_x")

    def test_o_contrato_ausente_diz_como_reespelhar(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cq, "CAMINHO_DO_CONTRATO", tmp_path / "nao_existe.json")
        cq._bytes_do_contrato.cache_clear()
        try:
            with pytest.raises(FileNotFoundError, match="espelhar_laboratorio"):
                cq.modalidades_declaradas()
        finally:
            cq._bytes_do_contrato.cache_clear()
