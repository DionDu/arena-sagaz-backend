"""🔒 A conferência de leitura do `scripts/consultar_des.py`.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026 a consulta que pesca lances do Pontinhos foi recusada pelo próprio
script, com esta mensagem:

    ⛔ isto nao e uma consulta de leitura: do.

⛔ **A palavra era `do`** — do comentário em português *"os lances **do** Jogo dos
Pontinhos"*. `DO` é palavra-chave do Postgres (`DO $$ ... $$`), e a conferência
varria o texto inteiro, comentários incluídos.

⚠️ **Todo comentário em português tem "do", "da" ou "com"**, e a diretriz do
projeto manda comentar tudo. O cadeado, como estava, recusava praticamente
qualquer SQL comentado — e cadeado que recusa o uso correto ensina a contorná-lo.

⚠️ **A conferência de palavra é a MAIS FRACA das três travas do script** (as que
de fato defendem são usar sempre `DATABASE_URL_DES` e a transação `READ ONLY`
imposta pelo banco). Ela existe para dar mensagem clara a quem escreveu a
consulta errada — e é justamente por isso que ela não pode dar mensagem errada a
quem escreveu a consulta certa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# O script mora em `scripts/`, que não é pacote instalado: entra no caminho aqui.
RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.consultar_des import conferir_leitura, sem_comentarios  # noqa: E402


class TestSemComentarios:
    """A remoção de comentários, que é o que separa código de prosa."""

    def test_tira_o_comentario_de_linha(self) -> None:
        """🔒 O caso exato que quebrou: prosa em português antes do `SELECT`."""
        sql = "-- os lances do Jogo dos Pontinhos, em ordem\nSELECT 1"
        assert "do" not in sem_comentarios(sql).lower().split()

    def test_tira_o_bloco(self) -> None:
        """🔒 `/* ... */`, inclusive atravessando linhas."""
        assert "update" not in sem_comentarios("/* update\nda tabela */ SELECT 1").lower()

    def test_o_traco_DENTRO_do_bloco_nao_confunde(self) -> None:
        """🔒 ⚠️ A ordem da remoção importa.

        Um `--` dentro de um bloco é comentário, e não início de linha de
        comentário. Se os `--` saíssem primeiro, o `*/` ficaria órfão e o resto do
        arquivo seria engolido — ou preservado — pelo motivo errado.
        """
        assert sem_comentarios("/* a -- b */ SELECT 1").split() == ["SELECT", "1"]

    def test_nao_mexe_no_codigo(self) -> None:
        """🔒 O controle: SQL sem comentário nenhum atravessa intacto."""
        sql = "SELECT co_fen_antes FROM jogo_damas.tb002_jogada"
        assert sem_comentarios(sql).strip() == sql


class TestConferirLeitura:
    """⛔ O que passa e o que não passa."""

    def test_a_consulta_do_pontinhos_passa(self) -> None:
        """🔒 O caso de produção, com o comentário que a derrubava."""
        conferir_leitura(
            "-- SOMENTE LEITURA: os lances do Jogo dos Pontinhos, em ordem.\n"
            "SELECT j.id_partida, g.co_aresta\n"
            "  FROM jogo_pontinhos.tb002_jogada g\n"
            "  JOIN partida.tb002_jogada j ON j.id_jogada = g.id_jogada\n"
            " ORDER BY j.id_partida, j.nu_ordem;"
        )

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM desafio.tb001_desafio",
            "UPDATE desafio.tb001_desafio SET co_status = 'x'",
            "SELECT 1; DROP TABLE conta.tb001_usuario",
        ],
    )
    def test_a_escrita_continua_recusada(self, sql: str) -> None:
        """🔒 ⛔ O conserto dos comentários não podia abrir a porta.

        ⚠️ O terceiro caso é o que importa: a escrita vem **depois** de um
        `SELECT` legítimo, que é como ela chegaria aqui por engano.
        """
        with pytest.raises(SystemExit):
            conferir_leitura(sql)

    def test_escrita_ESCONDIDA_num_comentario_nao_recusa(self) -> None:
        """🔒 ⚠️ E este é o preço, dito em voz alta.

        Tirar os comentários significa que `-- DELETE` deixa de ser recusado. Está
        certo: é comentário, o banco não o executa. ⛔ **Quem defende de verdade é
        a transação `READ ONLY`** — se um dia esta conferência for a única defesa,
        a defesa já terá acabado.
        """
        conferir_leitura("-- nao apagar nada: DELETE seria erro\nSELECT 1")
