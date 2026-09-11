"""🔒 O diário que torna a pescaria interrompível e retomável.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

A pescaria de captura múltipla leva ~7 h. O dono pediu que ela *"permita
interromper e retomar, sem perder todo o trabalho"* — em sete horas acontece
queda de energia, atualização do Windows e arrependimento.

⛔ **Um defeito aqui não aparece na hora: aparece na retomada**, que é o momento
em que ninguém tem como conferir o que se perdeu. É por isso que a retomada leva
teste, e não apenas uma execução bem-sucedida.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.pescar_moldes_de_partidas import Diario, _distancias, _tempo  # noqa: E402

ASSINATURA = {"tipo": "damas_coroar", "arquivo": "lances.csv", "minimo_pecas": 8}


class TestGravarELer:
    """O ciclo básico: anotar, fechar, reabrir."""

    def test_o_que_foi_anotado_volta_na_retomada(self, tmp_path: Path) -> None:
        """🔒 É a razão de ser do arquivo."""
        caminho = tmp_path / "p.jsonl"
        diario = Diario(caminho, ASSINATURA)
        diario.anotar_peneira("W:W7:B2", 5, {"ok": 1})
        diario.anotar_medicao("W:W7:B2", [5, 6, None, 5])
        diario.fechar()

        retomado = Diario(caminho, ASSINATURA)
        assert retomado.peneira == {"W:W7:B2": 5}
        assert retomado.medicao == {"W:W7:B2": [5, 6, None, 5]}
        retomado.fechar()

    def test_a_retomada_ACRESCENTA_e_nao_sobrescreve(self, tmp_path: Path) -> None:
        """🔒 ⛔ Abrir em modo `w` apagaria as sete horas anteriores em silêncio."""
        caminho = tmp_path / "p.jsonl"
        primeiro = Diario(caminho, ASSINATURA)
        primeiro.anotar_peneira("A", 3, {})
        primeiro.fechar()

        segundo = Diario(caminho, ASSINATURA)
        segundo.anotar_peneira("B", 4, {})
        segundo.fechar()

        assert set(Diario(caminho, ASSINATURA).peneira) == {"A", "B"}

    def test_os_motivos_de_descarte_tambem_voltam(self, tmp_path: Path) -> None:
        """🔒 Sem isto, o relatório do fim mostraria só os motivos da última sessão."""
        caminho = tmp_path / "p.jsonl"
        diario = Diario(caminho, ASSINATURA)
        diario.anotar_peneira("A", None, {"nao_cumpriu_no_teto": 1})
        diario.fechar()
        assert Diario(caminho, ASSINATURA).motivos["nao_cumpriu_no_teto"] == 1

    def test_grava_na_hora_sem_esperar_o_fechamento(self, tmp_path: Path) -> None:
        """🔒 ⚠️ O `flush()` por linha.

        Sem ele o Python segura ~8 KB num buffer, e um `Ctrl+C` jogaria fora
        dezenas de posições já calculadas: o trabalho estaria feito, e o arquivo
        não saberia. Aqui o arquivo é lido com o diário **ainda aberto**.
        """
        caminho = tmp_path / "p.jsonl"
        diario = Diario(caminho, ASSINATURA)
        diario.anotar_peneira("A", 3, {})
        assert "A" in caminho.read_text(encoding="utf-8")  # sem fechar
        diario.fechar()


class TestAssinatura:
    """⛔ Retomar a pescaria errada é pior que recomeçar."""

    def test_recusa_diario_de_OUTRA_pescaria(self, tmp_path: Path) -> None:
        """🔒 ⛔ Filtro diferente = acervo misturado, com cara de normal.

        Metade das posições medidas com um critério e metade com outro produz um
        arquivo perfeitamente bem formado, e ninguém saberia dizer quais moldes
        vieram de onde.
        """
        caminho = tmp_path / "p.jsonl"
        Diario(caminho, ASSINATURA).fechar()
        with pytest.raises(SystemExit) as erro:
            Diario(caminho, {**ASSINATURA, "minimo_pecas": 12})
        assert "minimo_pecas" in str(erro.value)

    def test_aceita_o_diario_da_MESMA_pescaria(self, tmp_path: Path) -> None:
        """🔒 O controle: mesmos parâmetros, retomada normal."""
        caminho = tmp_path / "p.jsonl"
        Diario(caminho, ASSINATURA).fechar()
        Diario(caminho, dict(ASSINATURA)).fechar()  # não levanta


class TestLinhaQuebrada:
    """⚠️ A queda no meio da escrita — o caso para o qual o JSONL foi escolhido."""

    def test_a_ultima_linha_cortada_nao_derruba_a_retomada(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """🔒 ⛔ Perder a última posição é barato; refazer sete horas não é.

        Um JSON único teria de ser reescrito inteiro a cada posição, com janela de
        corrupção a cada gravação. No JSONL, uma queda perde **uma linha**.
        """
        caminho = tmp_path / "p.jsonl"
        diario = Diario(caminho, ASSINATURA)
        diario.anotar_peneira("A", 3, {})
        diario.fechar()
        # A energia cai no meio da segunda linha.
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write('{"tipo_de_linha": "peneira", "fen": "B", "lan')

        retomado = Diario(caminho, ASSINATURA)
        assert retomado.peneira == {"A": 3}
        assert "quebrada" in capsys.readouterr().out
        retomado.fechar()

    def test_a_linha_quebrada_nao_impede_novas_anotacoes(self, tmp_path: Path) -> None:
        """🔒 ⚠️ O arquivo continua sendo escrito DEPOIS do lixo.

        ⛔ **A linha cortada não termina em quebra de linha**, então, sem cuidado,
        a anotação seguinte grudaria nela — e o registro NOVO, que está perfeito,
        viraria lixo junto com o velho. Duas perdas onde devia haver uma.

        ⚠️ O conserto é uma quebra de linha ao reabrir, que isola o lixo numa
        linha só. Este teste nasceu de o defeito ter acontecido de verdade, em
        11/09/2026, ao escrever este arquivo.
        """
        caminho = tmp_path / "p.jsonl"
        primeiro = Diario(caminho, ASSINATURA)
        primeiro.anotar_peneira("ANTES", 9, {})
        primeiro.fechar()
        # A energia cai no meio da gravação seguinte.
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write('{"tipo_de_linha": "peneira", "fen": "CORT')

        diario = Diario(caminho, ASSINATURA)
        diario.anotar_peneira("DEPOIS", 3, {})
        diario.fechar()

        # A retomada seguinte enxerga o velho E o novo; só o cortado se perdeu.
        retomado = Diario(caminho, ASSINATURA)
        assert retomado.peneira == {"ANTES": 9, "DEPOIS": 3}
        retomado.fechar()


class TestIndicadores:
    """⚠️ O que o dono acompanha durante as sete horas."""

    def test_mostra_quantos_de_cada_tamanho(self) -> None:
        """🔒 *"quantas já são elegíveis para cada um dos desafios"*."""
        assert _distancias([3, 3, 7, 4]) == "3L:2 4L:1 7L:1"

    def test_diz_quando_ainda_nao_ha_nada(self) -> None:
        """🔒 ⚠️ Lista vazia não pode virar string vazia.

        Uma linha de progresso terminando em `|` parece defeito do script, e na
        primeira meia hora ela é o normal.
        """
        assert _distancias([]) == "nenhum ainda"

    @pytest.mark.parametrize(
        ("segundos", "esperado"),
        [(45, "45s"), (600, "10m"), (4530, "75m"), (5430, "1h30m"), (25200, "7h00m")],
    )
    def test_o_tempo_sai_legivel(self, segundos: float, esperado: str) -> None:
        """🔒 Sete horas em segundos não se lê: `25200` não diz nada a ninguém."""
        assert _tempo(segundos) == esperado
