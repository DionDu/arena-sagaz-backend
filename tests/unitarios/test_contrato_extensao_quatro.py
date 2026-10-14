"""O CONTRATO DA EXTENSAO DO QUATRO EM LINHA, do lado do servidor (T077).

O app manda a partida pela sincronizacao de sempre, e o jogo entra como a chave
`quatro`, na partida e em cada jogada
(`arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/contracts/extensao-log-quatro.md`).
Este arquivo confere o que o SERVIDOR faz com ela.

AS TRAVESSIAS
-------------
- **Q-1, app ANTIGO x backend NOVO.** O app publicado nao tem o jogo e nunca
  manda `quatro`. Tem de continuar valendo exatamente como antes.
- **Q-2, a chave e CONHECIDA.** O ingestor existe: `quatro` nao gera o aviso de
  "extensao desconhecida", nem na partida nem na jogada.
- **Q-3, as dimensoes sao DO QUATRO.** Procurar a acao dele na tabela da velha
  mandaria tudo ao sentinela, e a telemetria nasceria cega sem erro nenhum.
- **Q-4, o que o ingestor grava**, com uma sessao que anota cada comando: a
  extensao de partida e a de jogada, o lance do humano sem telemetria (I-4), o
  da CPU com a semente (I-5), o codigo desconhecido no 9999 com a string crua
  guardada, e o reenvio da fita (a jogada ja gravada nao regrava a extensao).
- **Q-5, os codigos do MOTOR cabem na dimensao.** Toda acao e todo motivo de
  parada que o motor do app emite tem linha na 0033. Um codigo que faltasse
  iria ao 9999 em toda partida, sem ninguem perceber.

Estes testes sao de UNIDADE: nao ha Postgres. O banco de verdade e conferido na
T084, com uma partida jogada no `des`.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest

from api.sincronizacao import dimensoes
from api.sincronizacao import repositorio as modulo_repositorio
from api.sincronizacao.repositorio import (
    _EXTENSOES_CONHECIDAS,
    RepositorioSincronizacao,
    _avisar_extensao_de_partida_desconhecida,
    _avisar_extensao_desconhecida,
)
from api.sincronizacao.validacao import validar_evento

RAIZ = Path(__file__).resolve().parents[2]

# ── Amostras fieis ao contrato do log (contracts/extensao-log-quatro.md §1-§2) ─

EXTENSAO_PARTIDA_QUATRO: dict[str, Any] = {
    "co_versao_motor": "dart_1.0.0",
    "co_versao_contrato": "1.0.0",
    "co_lances_iniciais": "",
    "nu_jogador_abertura": -1,
    "co_preferencia_abertura": "alternado",
    "nu_semente_partida": 81234567,
    "js_extra": None,
}

#: Um lance da CPU: telemetria inteira, com a semente.
EXTENSAO_JOGADA_CPU: dict[str, Any] = {
    "co_jogador": -1,
    "co_tipo_lance": "soltar",
    "nu_coluna": 4,
    "co_acao": "abertura_sorteada",
    "qt_nos_visitados": 1,
    "nu_profundidade_atingida": 0,
    "co_motivo_parada_busca": "lance_unico",
    "nu_tempo_busca_ms": 0,
    "nu_avaliacao_j1": 0,
    "nu_semente": 4410293847,
    "co_motor_busca": "dart",
    "js_extra": None,
}

#: Um lance do humano: so o lance, a telemetria toda `None` (I-4).
EXTENSAO_JOGADA_HUMANO: dict[str, Any] = {
    "co_jogador": 1,
    "co_tipo_lance": "soltar",
    "nu_coluna": 3,
    "co_acao": None,
    "qt_nos_visitados": None,
    "nu_profundidade_atingida": None,
    "co_motivo_parada_busca": None,
    "nu_tempo_busca_ms": None,
    "nu_avaliacao_j1": None,
    "nu_semente": None,
    "co_motor_busca": None,
    "js_extra": None,
}


def _jogada(**extras: Any) -> dict[str, Any]:
    """Uma jogada generica valida, com o que os extras acrescentarem."""
    base = {
        "id_jogada": "22222222-2222-2222-2222-222222222222",
        "nu_ordem": 1,
        "nu_jogador": 1,
        "dh_jogada": "2026-10-14T10:00:00.000",
        "nu_tempo_decisao_ms": 900,
        "co_origem_decisao": "humano",
    }
    base.update(extras)
    return base


def _partida(**extras: Any) -> dict[str, Any]:
    base = {
        "co_jogo": "quatro",
        "co_variante": "tradicional",
        "nu_placar_j1": 1,
        "nu_placar_j2": 0,
    }
    base.update(extras)
    return base


def _evento(jogadas: list[dict[str, Any]], partida: dict[str, Any]) -> dict[str, Any]:
    return {
        "co_evento": "ev-quatro",
        "co_tipo": "partida",
        "payload": {
            "partida": partida,
            "jogadas": jogadas,
            "xp": [{"co_tipo_xp": "resultado", "nu_xp": 40}],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Q-1 e Q-2: o evento e as chaves
# ═══════════════════════════════════════════════════════════════════════════


class TestQ1AppAntigoBackendNovo:
    def test_partida_sem_quatro_continua_valida(self):
        """O payload de quem nao atualizou o app, como ele e hoje."""
        evento = _evento(
            [_jogada()],
            partida=_partida(co_jogo="pontinhos", co_variante="5x5"),
        )
        assert validar_evento(evento) is None

    def test_partida_do_quatro_com_as_extensoes_e_valida(self):
        evento = _evento(
            [_jogada(quatro=EXTENSAO_JOGADA_HUMANO)],
            partida=_partida(quatro=EXTENSAO_PARTIDA_QUATRO),
        )
        assert validar_evento(evento) is None


class TestQ2AChaveEConhecida:
    def test_quatro_esta_entre_as_extensoes_conhecidas(self):
        assert "quatro" in _EXTENSOES_CONHECIDAS

    def test_nem_a_partida_nem_a_jogada_geram_aviso(self, caplog):
        with caplog.at_level(logging.WARNING):
            _avisar_extensao_de_partida_desconhecida(
                _partida(quatro=EXTENSAO_PARTIDA_QUATRO)
            )
            _avisar_extensao_desconhecida(_jogada(quatro=EXTENSAO_JOGADA_CPU))
        assert caplog.records == []


# ═══════════════════════════════════════════════════════════════════════════
# Q-3: as dimensoes
# ═══════════════════════════════════════════════════════════════════════════


DIMENSOES_DO_QUATRO = ("acao_quatro", "motivo_parada_quatro", "tipo_lance_quatro")


class TestQ3AsDimensoesDoQuatro:
    @pytest.mark.parametrize("dimensao", DIMENSOES_DO_QUATRO)
    def test_leem_pela_VIEW_do_schema_do_quatro(self, dimensao: str):
        view, _, _ = dimensoes._DIMENSOES[dimensao]
        assert view.startswith("jogo_quatro.vw"), view

    def test_nao_colidem_com_as_dos_outros_jogos(self):
        do_quatro = {dimensoes._DIMENSOES[d][0] for d in DIMENSOES_DO_QUATRO}
        dos_outros = {
            v[0]
            for nome, v in dimensoes._DIMENSOES.items()
            if nome not in DIMENSOES_DO_QUATRO
        }
        assert do_quatro.isdisjoint(dos_outros)


# ═══════════════════════════════════════════════════════════════════════════
# Q-4: o que o ingestor grava
# ═══════════════════════════════════════════════════════════════════════════


class _Resultado:
    """O resultado de um `execute`: `first()` devolve [linha]."""

    def __init__(self, linha: Any) -> None:
        self._linha = linha

    def first(self) -> Any:
        return self._linha


class _SessaoQueAnota:
    """Anota cada comando. O INSERT da jogada generica responde com [jogada_nova]:
    uma linha no `RETURNING` (gravou) ou `None` (ja estava gravada)."""

    def __init__(self, *, jogada_nova: bool = True) -> None:
        self.jogada_nova = jogada_nova
        self.comandos: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, comando: Any, parametros: dict[str, Any] | None = None):
        sql = str(comando)
        self.comandos.append((sql, parametros or {}))
        if "INSERT INTO partida.tb002_jogada" in sql:
            return _Resultado(("id",) if self.jogada_nova else None)
        return _Resultado(None)

    def parametros_de(self, tabela: str) -> list[dict[str, Any]]:
        """Os parametros de cada INSERT em [tabela], na ordem."""
        return [p for sql, p in self.comandos if f"INSERT INTO {tabela}" in sql]


#: O que a dimensao do banco responderia (as linhas da 0033).
_LINHAS_DA_0033 = {
    "tipo_lance_quatro": {"soltar": 1},
    "acao_quatro": {"busca_melhor": 1, "abertura_sorteada": 3},
    "motivo_parada_quatro": {"nos": 2, "lance_unico": 5},
    "origem_decisao": {"humano": 1, "cpu": 2},
}


@pytest.fixture
def dimensoes_da_0033(monkeypatch):
    """Troca a leitura do banco pelas linhas da 0033: o codigo conhecido vira o
    numero dele, o desconhecido vira 9999, e o vazio vira `None`."""

    async def resolver(_sessao, dimensao: str, valor: Any):
        if valor is None or valor == "":
            return None, False
        numero = _LINHAS_DA_0033.get(dimensao, {}).get(str(valor))
        if numero is None:
            return dimensoes.NU_DESCONHECIDO, True
        return numero, False

    monkeypatch.setattr(modulo_repositorio.dimensoes, "resolver", resolver)


@pytest.mark.asyncio
async def test_a_extensao_de_partida_vai_inteira(dimensoes_da_0033):
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_partida_quatro("p1", EXTENSAO_PARTIDA_QUATRO)
    [p] = sessao.parametros_de("jogo_quatro.tb001_partida")
    assert p == {
        "id_partida": "p1",
        "co_versao_motor": "dart_1.0.0",
        "co_versao_contrato": "1.0.0",
        "co_lances_iniciais": "",
        "nu_jogador_abertura": -1,
        "co_preferencia_abertura": "alternado",
        "nu_semente_partida": 81234567,
        "js_extra": None,
    }


@pytest.mark.asyncio
async def test_lances_iniciais_None_vira_vazio_e_nao_estoura_o_NOT_NULL(
    dimensoes_da_0033,
):
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_partida_quatro(
        "p1", {**EXTENSAO_PARTIDA_QUATRO, "co_lances_iniciais": None}
    )
    assert sessao.parametros_de("jogo_quatro.tb001_partida")[0][
        "co_lances_iniciais"
    ] == ""


@pytest.mark.asyncio
async def test_o_lance_da_CPU_vai_com_a_telemetria_traduzida(dimensoes_da_0033):
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_jogada(
        "p1",
        _jogada(nu_jogador=2, co_origem_decisao="cpu", quatro=EXTENSAO_JOGADA_CPU),
    )
    [p] = sessao.parametros_de("jogo_quatro.tb002_jogada")
    # I-3: o sinal -1 e o do J2 (nu_jogador = 2).
    assert p["co_jogador"] == -1
    assert p["nu_tipo_lance"] == 1
    # I-2: a coluna 1-based, como veio.
    assert p["nu_coluna"] == 4
    assert p["nu_acao"] == 3
    assert p["nu_motivo_parada_busca"] == 5
    # I-5: o lance da CPU leva a semente.
    assert p["nu_semente"] == 4410293847
    assert p["co_motor_busca"] == "dart"
    assert p["js_extra"] is None


@pytest.mark.asyncio
async def test_o_lance_do_humano_vai_sem_telemetria(dimensoes_da_0033):
    """I-4: nada inventado no lance de quem joga; `NULL` e a verdade."""
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_jogada("p1", _jogada(quatro=EXTENSAO_JOGADA_HUMANO))
    [p] = sessao.parametros_de("jogo_quatro.tb002_jogada")
    for campo in (
        "nu_acao",
        "qt_nos_visitados",
        "nu_profundidade_atingida",
        "nu_motivo_parada_busca",
        "nu_tempo_busca_ms",
        "nu_avaliacao_j1",
        "nu_semente",
        "co_motor_busca",
    ):
        assert p[campo] is None, campo
    assert p["nu_tipo_lance"] == 1
    assert p["nu_coluna"] == 3


@pytest.mark.asyncio
async def test_codigo_desconhecido_vai_ao_9999_com_a_string_crua_guardada(
    dimensoes_da_0033,
):
    """Um app mais novo, com uma acao e um tipo que este banco nao conhece."""
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_jogada(
        "p1",
        _jogada(
            nu_jogador=2,
            co_origem_decisao="cpu",
            quatro={
                **EXTENSAO_JOGADA_CPU,
                "co_tipo_lance": "retirar",
                "co_acao": "acao_do_futuro",
            },
        ),
    )
    [p] = sessao.parametros_de("jogo_quatro.tb002_jogada")
    assert p["nu_tipo_lance"] == dimensoes.NU_DESCONHECIDO
    assert p["nu_acao"] == dimensoes.NU_DESCONHECIDO
    extra = json.loads(p["js_extra"])
    assert extra == {
        "co_tipo_lance_desconhecido": "retirar",
        "co_acao_desconhecido": "acao_do_futuro",
    }


@pytest.mark.asyncio
async def test_tipo_ausente_vai_ao_9999_e_nao_estoura_o_NOT_NULL(
    dimensoes_da_0033,
):
    sessao = _SessaoQueAnota()
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    sem_tipo = {k: v for k, v in EXTENSAO_JOGADA_HUMANO.items() if k != "co_tipo_lance"}
    await repo._gravar_jogada("p1", _jogada(quatro=sem_tipo))
    [p] = sessao.parametros_de("jogo_quatro.tb002_jogada")
    assert p["nu_tipo_lance"] == dimensoes.NU_DESCONHECIDO


@pytest.mark.asyncio
async def test_a_jogada_ja_gravada_nao_regrava_a_extensao(dimensoes_da_0033):
    """O reenvio da fita (a partida de desafio que se completa): a extensao ja
    esta la, e grava-la de novo estouraria a PK da 1:1."""
    sessao = _SessaoQueAnota(jogada_nova=False)
    repo = RepositorioSincronizacao(sessao)  # type: ignore[arg-type]
    await repo._gravar_jogada("p1", _jogada(quatro=EXTENSAO_JOGADA_HUMANO))
    assert sessao.parametros_de("jogo_quatro.tb002_jogada") == []


# ═══════════════════════════════════════════════════════════════════════════
# Q-5: os codigos do motor cabem na dimensao
# ═══════════════════════════════════════════════════════════════════════════

MOTOR_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "lib"
    / "modulos"
    / "jogos"
    / "quatro"
    / "motor"
)
MIGRACAO = RAIZ / "migrations" / "versions" / "0033_schema_jogo_quatro.py"
#: As migracoes que acrescentam linhas as dimensoes depois da 0033 (a 0034
#: traz os descuidos do personagem, §8zzzf).
MIGRACOES_DE_LINHAS = (
    RAIZ / "migrations" / "versions" / "0034_acoes_de_descuido_quatro.py",
)


def _codigos_da_migracao(tabela: str) -> set[str]:
    """Os codigos de [tabela] em TODAS as migracoes que a povoam."""
    codigos: set[str] = set()
    for migracao in (MIGRACAO, *MIGRACOES_DE_LINHAS):
        texto = migracao.read_text(encoding="utf-8")
        marca = f"INSERT INTO jogo_quatro.{tabela}"
        if marca not in texto:
            continue
        inicio = texto.index(marca)
        fim = texto.index('"""', inicio)
        codigos |= set(re.findall(r"\(\s*\d+\s*,\s*'([a-z_]+)'", texto[inicio:fim]))
    return codigos


def test_toda_acao_que_a_politica_devolve_esta_na_dimensao():
    """A politica escreve a acao como o ULTIMO argumento de `com(lance, '...')`
    ou de `escolhido(lance, '...')` (as vezes na linha seguinte, e com o lance
    sendo ele mesmo uma chamada), e o bloqueio pelo ternario `bloqueou ? '...'`
    (conferido em 14/10/2026, versao 1.1.0 do motor)."""
    fonte = (MOTOR_DO_APP / "politica_dificuldade_quatro.dart").read_text(
        encoding="utf-8"
    )
    # Um literal so de letras minusculas e `_` que FECHA uma chamada, depois
    # de uma virgula: e assim que os codigos aparecem, e nenhum outro texto
    # do arquivo tem essa forma (as mensagens de erro tem espaco).
    acoes = set(re.findall(r",\s*'([a-z_]+)'\)", fonte))
    acoes |= set(re.findall(r"bloqueou \? '([a-z_]+)'", fonte))
    # As nove de hoje tem de estar entre as achadas (a leitura nao pode falhar
    # em silencio).
    assert {
        "busca_melhor",
        "epsilon_aleatorio",
        "abertura_sorteada",
        "vitoria_imediata",
        "bloqueio_imediato",
        "empate_sorteado",
        "vitoria_perdida",
        "bloqueio_perdido",
        "jogou_sob_ameaca",
    } <= acoes
    assert acoes <= _codigos_da_migracao("tb901_jogada_acao")


def test_todo_motivo_de_parada_da_busca_esta_na_dimensao():
    """A busca escreve o motivo de TRES jeitos (conferido em 14/10/2026): a
    variavel `motivo = '...'`, a interrupcao `_BuscaInterrompida('...')` e o
    ultimo argumento de `responder(...)` nas saidas antecipadas."""
    fonte = (MOTOR_DO_APP / "busca_quatro.dart").read_text(encoding="utf-8")
    motivos = set(re.findall(r"motivo\s*=\s*'([a-z_]+)'", fonte))
    motivos |= set(re.findall(r"_BuscaInterrompida\('([a-z_]+)'\)", fonte))
    motivos |= set(re.findall(r"responder\([^;]*?'([a-z_]+)'\)", fonte, re.S))
    # Os cinco de hoje tem de estar entre os achados: se a leitura falhar em
    # silencio (o motor escrevendo de um quarto jeito), o caso nao confere nada.
    assert {"profundidade", "nos", "tempo", "decidido", "lance_unico"} <= motivos
    assert motivos <= _codigos_da_migracao("tb902_motivo_parada_busca")
