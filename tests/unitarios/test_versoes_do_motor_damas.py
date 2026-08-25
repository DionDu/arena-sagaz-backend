"""`co_versao_motor` chega sempre na forma composta `dart_X[|rust_Y]`.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Desde 26/08/2026 um lance de damas pode ser escolhido por dois motores: o Dart,
que roda em qualquer aparelho, e o Rust nativo, que roda onde o binario existe.
`jogo_damas.tb002_jogada.co_motor_busca` diz QUAL motor escolheu cada lance; o
que faltava era a VERSAO do nativo.

A migracao `0014` compos as duas na mesma coluna. A normalizacao do ingestor
existe para que a invariante *"toda linha e `dart_X` ou `dart_X|rust_Y`"* nao
dependa de qual build sincronizou: uma anterior a 27/08 manda `1.1.0` sem
prefixo, e deixar passar daria duas formas na mesma coluna — com todo
`split_part` tendo de adivinhar qual esta lendo.
"""

from __future__ import annotations

import pytest

from api.sincronizacao.repositorio import _versoes_do_motor


class TestNormalizacaoDaVersao:
    """O que entra, e o que sai."""

    @pytest.mark.parametrize(
        "entrada, esperado",
        [
            # O app novo, com o binario nativo presente. Passa intacto.
            ("dart_1.1.0|rust_0.2.0", "dart_1.1.0|rust_0.2.0"),
            # O app novo, sem binario nativo. Tambem passa intacto.
            ("dart_1.1.0", "dart_1.1.0"),
            # (!) O app ANTERIOR a 27/08, que so conhecia o motor Dart.
            ("1.1.0", "dart_1.1.0"),
            ("1.0.0", "dart_1.0.0"),
        ],
    )
    def test_a_saida_esta_sempre_composta(self, entrada: str, esperado: str):
        assert _versoes_do_motor(entrada) == esperado

    def test_normalizar_duas_vezes_nao_muda_nada(self):
        """Idempotente — porque um dia alguem vai chamar isto duas vezes."""
        uma = _versoes_do_motor("1.1.0")
        assert _versoes_do_motor(uma) == uma

    @pytest.mark.parametrize("entrada", [None, "", 42, [], {}])
    def test_o_que_nao_e_texto_passa_intacto(self, entrada):
        """Nao inventa valor: quem valida o tipo e o schema, nao esta funcao.

        (!) Prefixar um `None` com `dart_` gravaria a string `"dart_None"` numa
        coluna que deveria ficar nula — e um `NOT NULL` violado e um erro alto,
        que e o que se quer, enquanto `"dart_None"` e um dado errado silencioso.
        """
        assert _versoes_do_motor(entrada) == entrada

    def test_o_resultado_cabe_na_coluna(self):
        """`VARCHAR(60)` depois da 0014, e a conta tem folga.

        A migracao anterior dava 20, e `dart_1.1.0|rust_0.2.0` tem 21 — falhou
        por um, como o texto de 41 caracteres da 0013 falhou por um. Aqui a
        conta fica escrita.
        """
        # Duas versoes de dois digitos em cada posicao, que e o pior caso
        # realista.
        pior = _versoes_do_motor("10.10.10")
        pior = f"{pior}|rust_10.10.10"
        assert len(pior) <= 60, f"{pior!r} tem {len(pior)} caracteres"
