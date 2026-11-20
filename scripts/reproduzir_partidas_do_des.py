"""Reproduz pelo MOTOR as partidas gravadas no log do `des` (spec 012, T114d).

═══════════════════════════════════════════════════════════════════════════
PARA QUE SERVE
═══════════════════════════════════════════════════════════════════════════

O log de partidas (`partida.tb002_jogada` + a tabela de cada jogo) é o que o
replay, o Raio-X e o juiz do Desafio do Dia leem. Com o poder "voltar jogada",
o log passou a guardar também as jogadas DESFEITAS (`ic_cancelada`), e a
numeração mudou (`nu_ordem` = o evento, `nu_lance` = o lance no tabuleiro;
`docs/DECISOES-do-dono.md` §8zzzz44 e §8zzzz45, no frontend). Um log que "subiu"
não prova nada sozinho: ele precisa **reproduzir a partida**.

Este script pega as partidas de um período e, para cada uma, confere:

1. **A numeração dos eventos**: `nu_ordem` de 1 ao total, sem buraco. Um buraco
   é um evento que o servidor descartou calado (o `ON CONFLICT DO NOTHING` do
   ingestor), que era o defeito do Quatro antes da T114a.
2. **As marcas do cancelamento**: toda jogada cancelada diz qual poder a
   cancelou (`co_poder`) e quando (`dh_cancelamento`); nenhuma viva tem isso.
3. **O `nu_lance` das vivas** (nos jogos que o mandam): 1, 2, 3... na ordem dos
   eventos, sem repetir.
4. **A reprodução**: as jogadas VIVAS, na ordem dos eventos, aplicadas pelo
   motor a partir do início gravado. Cada lance tem de ser legal; quem jogou
   (`nu_jogador`) tem de ser quem tinha a vez; e, nas damas e no xadrez, a
   posição de antes gravada (`co_fen_antes`) tem de ser a que o motor tem.
5. **O fim**: partida `concluida` tem de terminar no motor também, com o mesmo
   vencedor (`co_resultado`, ou o placar nas partidas antigas), o mesmo placar
   de caixas no Pontinhos e o mesmo motivo do fim no xadrez.

⚠️ As canceladas NÃO entram na reprodução: elas foram jogadas, mas a partida
seguiu de outro ponto. É isso que a reprodução prova: tirando as desfeitas, o
que sobra é exatamente a partida que terminou.

═══════════════════════════════════════════════════════════════════════════
COMO É LIDO, E POR QUE SÓ O `des`
═══════════════════════════════════════════════════════════════════════════

A conexão é a de `scripts/consultar_des.py` (a URL `DATABASE_URL_DES` do
catálogo do ecossistema), numa transação `READ ONLY`: o script não escreve
nada. Os motores são os da camada de motores (`motores/`): as damas, o
Pontinhos e o Quatro com o árbitro em Python, o xadrez pelo executável Rust
compilado do mesmo crate do aparelho (`motores/xadrez/jogador_xadrez.py`).

Uso:

    .venv\\Scripts\\python scripts\\reproduzir_partidas_do_des.py --desde 2026-11-19
    .venv\\Scripts\\python scripts\\reproduzir_partidas_do_des.py --desde 2026-11-20 --jogo quatro

Sai com código 0 só quando todas as partidas reproduzem.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# `parents[1]` sobe de arena-sagaz-backend/scripts/ até arena-sagaz-backend/,
# que entra no caminho de importação para `motores` e `scripts` serem achados.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows é cp1252; sem isto, um acento derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# A URL do `des` sai do mesmo lugar que a consulta de leitura usa: um só
# caminho para o banco, com a mesma recusa quando o catálogo falta.
from scripts.consultar_des import url_do_des  # noqa: E402

#: Os jogos que o script sabe reproduzir. A velha não tem poder (§8x.4) e
#: fica de fora.
JOGOS = ("damas", "pontinhos", "quatro", "xadrez")

#: Os jogos que mandam `nu_lance` (o lance no tabuleiro). O Pontinhos e a velha
#: não mandam: o campo é opcional, e o `nu_ordem` basta a eles.
JOGOS_COM_NU_LANCE = ("damas", "quatro", "xadrez")


# ──────────────────────────────────────────────────────────────────────────
# A leitura do banco
# ──────────────────────────────────────────────────────────────────────────

#: As partidas do período, com o que cada jogo grava do início dela. Os
#: `LEFT JOIN` trazem a tabela do jogo certo e deixam as outras nulas.
SQL_PARTIDAS = """
SELECT p.id_partida::text AS id_partida, p.co_jogo, p.co_variante, p.co_modo,
       p.co_dificuldade, p.co_status, p.co_resultado,
       p.nu_placar_j1, p.nu_placar_j2, p.qt_usos_poder,
       to_char(p.dh_inicio AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI') AS inicio,
       coalesce(xd.co_fen_inicial, dd.co_fen_inicial) AS fen_inicial,
       q.co_lances_iniciais,
       mf.co_motivo_fim
  FROM partida.tb001_partida p
  LEFT JOIN jogo_damas.tb001_partida dd ON dd.id_partida = p.id_partida
  LEFT JOIN jogo_quatro.tb001_partida q ON q.id_partida = p.id_partida
  LEFT JOIN jogo_xadrez.tb001_partida xd ON xd.id_partida = p.id_partida
  LEFT JOIN jogo_xadrez.tb905_motivo_fim mf ON mf.nu_motivo_fim = xd.nu_motivo_fim
 WHERE p.co_jogo = ANY(:jogos)
   AND p.dh_inicio >= :desde
 ORDER BY p.dh_inicio
"""

#: As jogadas dessas partidas, com o lance na forma de cada jogo. O Quatro
#: grava o tipo e a coluna separados; a letra do tipo vem da tabela de
#: domínio (`soltar` → `s`, pelo motor, mais abaixo).
SQL_JOGADAS = """
SELECT j.id_partida::text AS id_partida, j.nu_ordem, j.nu_jogador, j.nu_lance,
       j.ic_cancelada, j.co_poder, j.dh_cancelamento,
       d.co_lance AS lance_damas, d.co_fen_antes AS fen_damas,
       pt.co_aresta AS lance_pontinhos,
       tl.co_tipo_lance AS tipo_quatro, q.nu_coluna AS coluna_quatro,
       x.co_lance AS lance_xadrez, x.co_fen_antes AS fen_xadrez
  FROM partida.tb002_jogada j
  JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
  LEFT JOIN jogo_damas.tb002_jogada d ON d.id_jogada = j.id_jogada
  LEFT JOIN jogo_pontinhos.tb002_jogada pt ON pt.id_jogada = j.id_jogada
  LEFT JOIN jogo_quatro.tb002_jogada q ON q.id_jogada = j.id_jogada
  LEFT JOIN jogo_quatro.tb903_tipo_lance tl ON tl.nu_tipo_lance = q.nu_tipo_lance
  LEFT JOIN jogo_xadrez.tb002_jogada x ON x.id_jogada = j.id_jogada
 WHERE p.co_jogo = ANY(:jogos)
   AND p.dh_inicio >= :desde
 ORDER BY j.id_partida, j.nu_ordem
"""


async def ler_do_des(jogos: tuple[str, ...], desde: date) -> tuple[list[dict], list[dict]]:
    """Lê as partidas e as jogadas do período, numa transação só de leitura."""
    motor = create_async_engine(url_do_des(), echo=False, poolclass=NullPool)
    parametros = {"jogos": list(jogos), "desde": desde}
    try:
        async with motor.connect() as conexao:
            # ⛔ A trava que o banco impõe: nada aqui escreve.
            await conexao.execute(text("SET TRANSACTION READ ONLY"))
            partidas = (await conexao.execute(text(SQL_PARTIDAS), parametros)).mappings().all()
            jogadas = (await conexao.execute(text(SQL_JOGADAS), parametros)).mappings().all()
    finally:
        await motor.dispose()
    # `dict(...)`: cada linha vira um dicionário comum, que sobrevive à conexão.
    return [dict(p) for p in partidas], [dict(j) for j in jogadas]


# ──────────────────────────────────────────────────────────────────────────
# O resultado da conferência de UMA partida
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Conferencia:
    """O que se achou numa partida: as falhas (vazio = reproduz) e um resumo."""

    partida: dict
    falhas: list[str] = field(default_factory=list)
    vivas: int = 0
    canceladas: int = 0

    def falhou(self, motivo: str) -> None:
        """Anota uma falha; a partida passa a não reproduzir."""
        self.falhas.append(motivo)


def jogador_do_lado(lado: Any, lado_que_abriu: Any, jogador_que_abriu: int) -> int:
    """Traduz o LADO do motor (`+1`/`-1`, ou a cor no xadrez) no jogador do log.

    O motor fala em lados (brancas e pretas, ou quem abre e quem responde); o
    log fala em J1 e J2. A ponte é a 1ª jogada viva: o lado que a fez é o
    jogador que a fez. Daí em diante, o mesmo lado é o mesmo jogador.
    """
    return jogador_que_abriu if lado == lado_que_abriu else 3 - jogador_que_abriu


def vencedor_esperado(partida: dict) -> int | None:
    """O vencedor gravado: 1 ou 2 (o jogador), 0 no empate, `None` se não há.

    O `co_resultado` é o campo de agora; as partidas mais antigas não o têm, e
    aí quem diz é o placar (`nu_placar_j1` × `nu_placar_j2`).
    """
    resultado = partida["co_resultado"]
    if resultado == "venceu_j1":
        return 1
    if resultado == "venceu_j2":
        return 2
    if resultado == "empate":
        return 0
    p1, p2 = partida["nu_placar_j1"], partida["nu_placar_j2"]
    if p1 is None or p2 is None:
        return None
    return 1 if p1 > p2 else 2 if p2 > p1 else 0


# ──────────────────────────────────────────────────────────────────────────
# As conferências que não dependem do jogo (1 a 3 do cabeçalho)
# ──────────────────────────────────────────────────────────────────────────


def conferir_numeracao(c: Conferencia, jogadas: list[dict]) -> list[dict]:
    """Confere os eventos e as marcas, e devolve as vivas na ordem dos eventos."""
    ordens = [j["nu_ordem"] for j in jogadas]
    if ordens != list(range(1, len(ordens) + 1)):
        c.falhou(f"nu_ordem com buraco ou repetição: {ordens}")

    vivas = []
    for j in jogadas:
        if j["ic_cancelada"]:
            c.canceladas += 1
            if not j["co_poder"] or j["dh_cancelamento"] is None:
                c.falhou(f"evento {j['nu_ordem']}: cancelado sem co_poder ou sem dh_cancelamento")
        else:
            vivas.append(j)
            if j["co_poder"] or j["dh_cancelamento"] is not None:
                c.falhou(f"evento {j['nu_ordem']}: vivo com marca de cancelamento")
    c.vivas = len(vivas)

    if c.partida["co_jogo"] in JOGOS_COM_NU_LANCE:
        lances = [j["nu_lance"] for j in vivas]
        if lances != list(range(1, len(lances) + 1)):
            c.falhou(f"nu_lance das vivas fora de 1..{len(lances)}: {lances}")
    return vivas


# ──────────────────────────────────────────────────────────────────────────
# A reprodução, jogo a jogo (4 e 5 do cabeçalho)
# ──────────────────────────────────────────────────────────────────────────


def _conferir_fim(c: Conferencia, acabou: bool, vencedor_do_log: int | None) -> None:
    """Compara o fim do motor com o gravado (o vencedor já como jogador)."""
    concluida = c.partida["co_status"] == "concluida"
    if concluida and not acabou:
        c.falhou("a partida está 'concluida', mas no motor ela não acabou")
    if not concluida and acabou:
        c.falhou(f"no motor a partida acabou, mas o status é {c.partida['co_status']!r}")
    if concluida and acabou:
        esperado = vencedor_esperado(c.partida)
        if esperado is not None and esperado != vencedor_do_log:
            c.falhou(f"vencedor: o log diz {esperado}, o motor diz {vencedor_do_log}")


def reproduzir_damas(c: Conferencia, vivas: list[dict]) -> None:
    """Damas: o árbitro em Python, a partir do FEN inicial gravado."""
    from motores.damas.motor_damas import EstadoDamas, MotorDamas

    motor = MotorDamas(c.partida["co_variante"])
    estado = EstadoDamas(co_modalidade=c.partida["co_variante"], fen_inicial=c.partida["fen_inicial"])
    lado_que_abriu = estado.vez_de
    for j in vivas:
        if j["fen_damas"] != estado.fen:
            c.falhou(f"evento {j['nu_ordem']}: co_fen_antes {j['fen_damas']!r} ≠ motor {estado.fen!r}")
            return
        if jogador_do_lado(estado.vez_de, lado_que_abriu, vivas[0]["nu_jogador"]) != j["nu_jogador"]:
            c.falhou(f"evento {j['nu_ordem']}: jogou o J{j['nu_jogador']} fora da vez")
        try:
            estado = motor.aplicar(estado, j["lance_damas"])
        except ValueError as erro:
            c.falhou(f"evento {j['nu_ordem']}: lance {j['lance_damas']!r} recusado ({erro})")
            return
    veredito = motor.veredito(estado)
    vencedor = None
    if veredito.acabou:
        # O vencedor das damas vem como lado (`+1`/`-1`) ou 0 no empate.
        vencedor = 0 if veredito.vencedor == 0 else jogador_do_lado(
            veredito.vencedor, lado_que_abriu, vivas[0]["nu_jogador"]
        )
    _conferir_fim(c, veredito.acabou, vencedor)


def reproduzir_pontinhos(c: Conferencia, vivas: list[dict]) -> None:
    """Pontinhos: o árbitro em Python. Só o 4×3 (`pequeno`) joga contra a CPU."""
    from motores.pontinhos.motor_pontinhos import EstadoPontinhos, MotorPontinhos

    if c.partida["co_variante"] != "pequeno":
        c.falhou(f"variante {c.partida['co_variante']!r}: o árbitro conhece só o 4×3")
        return
    motor = MotorPontinhos()
    estado = EstadoPontinhos()
    lado_que_abriu = estado.vez_de
    for j in vivas:
        if jogador_do_lado(estado.vez_de, lado_que_abriu, vivas[0]["nu_jogador"]) != j["nu_jogador"]:
            c.falhou(f"evento {j['nu_ordem']}: jogou o J{j['nu_jogador']} fora da vez")
        try:
            estado = motor.aplicar(estado, j["lance_pontinhos"])
        except ValueError as erro:
            c.falhou(f"evento {j['nu_ordem']}: traço {j['lance_pontinhos']!r} recusado ({erro})")
            return
    veredito = motor.veredito(estado)
    # O placar de caixas, traduzido de lado para jogador.
    placar = {
        jogador_do_lado(lado, lado_que_abriu, vivas[0]["nu_jogador"]): caixas
        for lado, caixas in estado.placar.items()
    }
    if veredito.acabou and (placar[1], placar[2]) != (c.partida["nu_placar_j1"], c.partida["nu_placar_j2"]):
        c.falhou(
            f"placar: o log diz {c.partida['nu_placar_j1']} × {c.partida['nu_placar_j2']}, "
            f"o motor {placar[1]} × {placar[2]}"
        )
    vencedor = None
    if veredito.acabou:
        vencedor = 0 if veredito.vencedor == 0 else jogador_do_lado(
            veredito.vencedor, lado_que_abriu, vivas[0]["nu_jogador"]
        )
    _conferir_fim(c, veredito.acabou, vencedor)


def reproduzir_quatro(c: Conferencia, vivas: list[dict]) -> None:
    """Quatro em Linha: o árbitro em Python, depois dos lances iniciais gravados."""
    from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, ler_sequencia

    motor = MotorQuatro(c.partida["co_variante"])
    # A letra de cada tipo de lance (`soltar` → `s`), pelas regras da
    # modalidade, e não escrita aqui: `tipos_de_lance` é letra → tipo.
    letra_do_tipo = {tipo: letra for letra, tipo in dict(motor.regras.tipos_de_lance).items()}
    iniciais = ler_sequencia(c.partida["co_lances_iniciais"] or "")
    estado = EstadoQuatro(co_modalidade=c.partida["co_variante"], lances=iniciais)
    lado_que_abriu = motor.vez_de(estado)
    for j in vivas:
        if jogador_do_lado(motor.vez_de(estado), lado_que_abriu, vivas[0]["nu_jogador"]) != j["nu_jogador"]:
            c.falhou(f"evento {j['nu_ordem']}: jogou o J{j['nu_jogador']} fora da vez")
        letra = letra_do_tipo.get(j["tipo_quatro"])
        if letra is None:
            c.falhou(f"evento {j['nu_ordem']}: tipo de lance {j['tipo_quatro']!r} desconhecido")
            return
        lance = f"{letra}{j['coluna_quatro']}"
        estado = estado.com_lance(lance)
        try:
            # Pedir o tabuleiro reproduz a partida e recusa o lance ilegal.
            motor.tabuleiro(estado)
        except ValueError as erro:
            c.falhou(f"evento {j['nu_ordem']}: lance {lance!r} recusado ({erro})")
            return
    veredito = motor.veredito(estado)
    vencedor = None
    if veredito.acabou:
        vencedor = 0 if veredito.vencedor == 0 else jogador_do_lado(
            veredito.vencedor, lado_que_abriu, vivas[0]["nu_jogador"]
        )
    _conferir_fim(c, veredito.acabou, vencedor)


def reproduzir_xadrez(c: Conferencia, vivas: list[dict]) -> None:
    """Xadrez: o executável Rust, lance a lance, conferindo o FEN de antes."""
    from motores.xadrez.jogador_xadrez import MotorXadrezRecusou, jogador_compartilhado

    motor = jogador_compartilhado()
    modalidade = c.partida["co_variante"]
    fen_inicial = c.partida["fen_inicial"]
    estado = motor.estado(modalidade=modalidade, fen_inicial=fen_inicial, lances=[])
    lado_que_abriu = estado["vez"]
    fen_atual = fen_inicial
    jogados: list[str] = []
    fim = None
    for j in vivas:
        if j["fen_xadrez"] != fen_atual:
            c.falhou(f"evento {j['nu_ordem']}: co_fen_antes {j['fen_xadrez']!r} ≠ motor {fen_atual!r}")
            return
        if jogador_do_lado(estado["vez"], lado_que_abriu, vivas[0]["nu_jogador"]) != j["nu_jogador"]:
            c.falhou(f"evento {j['nu_ordem']}: jogou o J{j['nu_jogador']} fora da vez")
        try:
            resposta = motor.aplicar(
                modalidade=modalidade, fen_inicial=fen_inicial, lances=jogados, lance=j["lance_xadrez"]
            )
        except MotorXadrezRecusou as erro:
            c.falhou(f"evento {j['nu_ordem']}: lance {j['lance_xadrez']!r} recusado ({erro})")
            return
        jogados.append(j["lance_xadrez"])
        fen_atual = resposta["fen_depois"]
        estado = resposta["estado"]
        fim = estado["fim"]
    vencedor = None
    if fim is not None:
        vencedor = 0 if fim["vencedor"] is None else jogador_do_lado(
            fim["vencedor"], lado_que_abriu, vivas[0]["nu_jogador"]
        )
        # O motivo do fim gravado (`jogo_xadrez.tb001_partida.nu_motivo_fim`).
        if c.partida["co_motivo_fim"] not in (None, fim["motivo"]):
            c.falhou(f"motivo do fim: o log diz {c.partida['co_motivo_fim']!r}, o motor {fim['motivo']!r}")
    _conferir_fim(c, fim is not None, vencedor)


#: Quem reproduz cada jogo.
REPRODUTORES = {
    "damas": reproduzir_damas,
    "pontinhos": reproduzir_pontinhos,
    "quatro": reproduzir_quatro,
    "xadrez": reproduzir_xadrez,
}


# ──────────────────────────────────────────────────────────────────────────
# O relatório
# ──────────────────────────────────────────────────────────────────────────


def conferir(partidas: list[dict], jogadas: list[dict]) -> list[Conferencia]:
    """Confere cada partida e devolve o que se achou, na ordem do início."""
    por_partida: dict[str, list[dict]] = {}
    for j in jogadas:
        por_partida.setdefault(j["id_partida"], []).append(j)

    conferencias = []
    for p in partidas:
        c = Conferencia(partida=p)
        vivas = conferir_numeracao(c, por_partida.get(p["id_partida"], []))
        if vivas:
            REPRODUTORES[p["co_jogo"]](c, vivas)
        else:
            c.falhou("nenhuma jogada viva")
        conferencias.append(c)
    return conferencias


def main() -> int:
    """Lê os argumentos, confere e imprime uma linha por partida."""
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--desde", required=True, type=date.fromisoformat,
                        help="a data (AAAA-MM-DD) de onde as partidas começam a contar")
    leitor.add_argument("--jogo", choices=JOGOS, action="append",
                        help="só este jogo (pode repetir); sem ele, os quatro")
    argumentos = leitor.parse_args()
    jogos = tuple(argumentos.jogo or JOGOS)

    partidas, jogadas = asyncio.run(ler_do_des(jogos, argumentos.desde))
    if not partidas:
        print("(nenhuma partida no período)")
        return 0

    conferencias = conferir(partidas, jogadas)
    for c in conferencias:
        p = c.partida
        selo = "OK    " if not c.falhas else "FALHOU"
        print(
            f"{selo} {p['inicio']}  {p['co_jogo']:<9} {p['co_dificuldade'] or '-':<7} "
            f"{p['co_status']:<10} {p['co_resultado'] or '-':<10} "
            f"usos={p['qt_usos_poder'] or 0}  vivas={c.vivas}  canceladas={c.canceladas}  "
            f"{p['id_partida'][:8]}"
        )
        for falha in c.falhas:
            print(f"         ⚠️ {falha}")

    ruins = sum(1 for c in conferencias if c.falhas)
    print(f"\n{len(conferencias) - ruins} de {len(conferencias)} partida(s) reproduzem.")
    return 0 if ruins == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
