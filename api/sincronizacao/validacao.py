"""Validação e **limites anti-fraude / anti-abuso** do lote de sincronização.

Motivação (SEG-05/06/07): o servidor recebia o lote como ``dict`` cru e gravava
o que o cliente mandasse — XP/placar/progressão sem teto (fraude trivial no
ranking público) e payloads malformados viravam **500** que travavam a fila do
app para sempre. Aqui centralizamos:

- **Validação estrutural** (tipos/tamanhos) para NENHUM payload malformado chegar
  ao SQL e estourar 500.
- **Tetos de plausibilidade** (XP por partida, placar, tamanho do lote, merge)
  para impedir injeção de valores absurdos.

A política é **rejeitar por evento** (o serviço devolve ``rejeitados: [...]`` com
200) em vez de derrubar o lote inteiro — assim um evento ruim não trava os bons
nem faz o app reenviar para sempre. Estes tetos são **generosos de propósito**
(barram abuso óbvio sem arriscar rejeitar jogo legítimo) e devem ser ajustados à
economia real do jogo quando ela estabilizar.
"""
from __future__ import annotations

from typing import Any, Optional

# ── Limites do LOTE e de cada evento ─────────────────────────────────────────
MAX_EVENTOS_POR_LOTE = 100        # partidas por sincronização
MAX_JOGADAS_POR_EVENTO = 400      # jogadas de uma partida (folga sobre o real)
MAX_PARCELAS_XP_POR_EVENTO = 20   # parcelas de XP de uma partida
MAX_TAMANHO_CO_EVENTO = 64        # UUID/identificador do evento
XP_MAX_POR_PARTIDA = 1000         # teto do XP TOTAL de uma partida (ajustar depois)
PLACAR_MIN, PLACAR_MAX = 0, 100   # placar plausível

# ── Limites do MERGE convidado→conta (acumula muitas partidas) ────────────────
MAX_PARTIDAS_MERGE = 100_000
MAX_XP_MERGE = XP_MAX_POR_PARTIDA * MAX_PARTIDAS_MERGE
MAX_SEQUENCIA_MERGE = 100_000
MAX_CONQUISTAS_MERGE = 1_000


def _inteiro_nao_negativo(valor: Any) -> bool:
    """`True` se [valor] é um inteiro >= 0. Recusa ``bool`` (que em Python é int),
    strings e floats — o cliente deve mandar inteiros de verdade."""
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def validar_evento(evento: Any) -> Optional[str]:
    """Valida UM evento de partida. Devolve ``None`` se OK, ou um **código** de
    rejeição (string) — nunca lança. O serviço usa o código para montar a lista
    ``rejeitados`` (o app então DESCARTA o evento em vez de reenviá-lo)."""
    if not isinstance(evento, dict):
        return "evento_malformado"

    co_evento = evento.get("co_evento")
    if (
        not isinstance(co_evento, str)
        or not co_evento
        or len(co_evento) > MAX_TAMANHO_CO_EVENTO
    ):
        return "evento_sem_id"

    payload = evento.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return "payload_malformado"

    partida = payload.get("partida") or {}
    if not isinstance(partida, dict):
        return "partida_malformada"

    # Placares: inteiros dentro de uma faixa plausível.
    for chave in ("nu_placar_j1", "nu_placar_j2"):
        v = partida.get(chave, 0)
        if not _inteiro_nao_negativo(v) or v > PLACAR_MAX:
            return "placar_invalido"

    # Jogadas: lista limitada (evita lote gigante de INSERTs — SEG-07).
    jogadas = payload.get("jogadas", [])
    if not isinstance(jogadas, list) or len(jogadas) > MAX_JOGADAS_POR_EVENTO:
        return "jogadas_invalidas"

    # XP: lista limitada, cada parcela inteira >= 0, soma dentro do teto (SEG-05).
    xp = payload.get("xp", [])
    if not isinstance(xp, list) or len(xp) > MAX_PARCELAS_XP_POR_EVENTO:
        return "xp_invalido"
    total_xp = 0
    for parcela in xp:
        if not isinstance(parcela, dict):
            return "xp_invalido"
        v = parcela.get("nu_xp", 0)
        if not _inteiro_nao_negativo(v):
            return "xp_invalido"
        total_xp += v
    if total_xp > XP_MAX_POR_PARTIDA:
        return "xp_excede_teto"

    return None


def validar_progressao_convidado(resumo: Any) -> Optional[str]:
    """Valida a progressão do convidado no merge (SEG-05). Devolve ``None`` se OK
    ou um **código** de rejeição. Aqui o abuso é mais perigoso: sem teto, 1 request
    injeta XP infinito na conta. Checa tipos, tetos e consistência dos contadores."""
    if not isinstance(resumo, dict):
        return "progressao_invalida"

    campos = (
        "nu_xp_total",
        "nu_partidas",
        "nu_vitorias",
        "nu_derrotas",
        "nu_empates",
        "nu_sequencia_atual",
    )
    valores: dict[str, int] = {}
    for c in campos:
        v = resumo.get(c, 0)
        if not _inteiro_nao_negativo(v):
            return "progressao_invalida"
        valores[c] = v

    if valores["nu_partidas"] > MAX_PARTIDAS_MERGE:
        return "progressao_excede_teto"
    if valores["nu_xp_total"] > MAX_XP_MERGE:
        return "progressao_excede_teto"
    if valores["nu_sequencia_atual"] > MAX_SEQUENCIA_MERGE:
        return "progressao_excede_teto"

    # Consistência: vitórias + derrotas + empates não podem passar do total de
    # partidas (senão os contadores foram forjados).
    if (
        valores["nu_vitorias"] + valores["nu_derrotas"] + valores["nu_empates"]
        > valores["nu_partidas"]
    ):
        return "progressao_inconsistente"

    # XP total não pode exceder o teto por partida vezes o nº de partidas.
    if valores["nu_xp_total"] > XP_MAX_POR_PARTIDA * max(valores["nu_partidas"], 1):
        return "progressao_excede_teto"

    conquistas = resumo.get("conquistas", []) or []
    if not isinstance(conquistas, list) or len(conquistas) > MAX_CONQUISTAS_MERGE:
        return "conquistas_invalidas"

    return None
