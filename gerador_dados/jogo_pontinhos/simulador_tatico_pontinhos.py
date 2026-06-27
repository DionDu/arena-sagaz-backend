"""Simulador tático Pygame: Humano vs CNN, CNN vs CNN, CNN vs Minimax, vs Oráculo.

Modos:
  humano_vs_cnn     — você joga contra uma CNN
  humano_vs_oraculo — você joga contra o oráculo (tablebase exata)
  cnn_vs_cnn        — duas CNNs disputam com delay e pausa configuráveis
  cnn_vs_minimax    — CNN disputa contra Minimax(profundidade=p)
  cnn_vs_oraculo    — CNN disputa contra o oráculo (tablebase exata)

Suporte automático a modelos 1-canal (encoding crua 9×7×1) e
12-canais (canais estruturais 4×3×12) via detecção do shape de entrada.

O oráculo só funciona para tamanho='pequeno' (tablebase 4×3 pré-calculada).
"""
from __future__ import annotations

import argparse
import random
import sys
import threading
import time
from pathlib import Path
from typing import Literal

import numpy as np

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    TAMANHOS,
    todos_labels_canonicos,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada as minimax_melhor
from gerador_dados.jogo_pontinhos.oraculo_tablebase_pontinhos import (
    carregar as oraculo_carregar,
    construir_mapeamento as oraculo_construir_mapeamento,
    matriz_para_bitmask,
    scores_de_todas_jogadas_exato,
)
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
    CONTEXTO_PARTIDA,
    normalizar_para_cnn,
)
from api.nucleo.log import obter_logger

log = obter_logger("gerador_dados.simulador")

# ── Layout ────────────────────────────────────────────────────────────────────
_LARGURA_TAB = 500
_LARGURA_PAINEL = 370
_LARGURA = _LARGURA_TAB + _LARGURA_PAINEL
_ALTURA = 740
_MARGEM = 52
_AREA_HUD = 110
_BOARD_H = _ALTURA - _AREA_HUD  # 630

# ── Cores ─────────────────────────────────────────────────────────────────────
_C_FUNDO = (16, 16, 28)
_C_PAINEL = (22, 22, 40)
_C_SEP = (55, 55, 85)
_C_GRADE = (155, 155, 180)
_C_J1 = (90, 190, 255)
_C_J2 = (255, 100, 100)
_C_TEXTO = (215, 215, 232)
_C_SUB = (130, 130, 160)
_C_HOVER = (235, 195, 40)
_C_GHOST = (38, 38, 60)
_C_T_OK = (75, 210, 85)
_C_T_WARN = (210, 165, 40)
_C_T_CRIT = (210, 55, 55)
_C_BAR_PROB = (70, 145, 210)
_C_BAR_ESC = (65, 205, 85)
_C_VENC = (255, 220, 40)
_C_PAUSE = (180, 120, 30)
_ESP_TRACO = 8
_ESP_GHOST = 4


# ── Helpers CNN ───────────────────────────────────────────────────────────────

def _carregar_modelo(caminho: str):
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite  # type: ignore
    interp = tflite.Interpreter(model_path=caminho)
    interp.allocate_tensors()
    return interp


def _tipo_modelo(interp) -> Literal["1ch", "12ch"]:
    shape = interp.get_input_details()[0]["shape"]
    return "12ch" if len(shape) == 4 and shape[3] == 12 else "1ch"


def _partida_para_dataset(m: np.ndarray) -> np.ndarray:
    """Converte {-1, 0, 1, 8} da partida → {0, 1, 8, 9} do dataset para extrair_canais."""
    out = np.zeros_like(m, dtype=np.int8)
    h, w = m.shape
    for r in range(h):
        for c in range(w):
            if r % 2 == 0 and c % 2 == 0:
                out[r, c] = 8
            elif r % 2 == 1 and c % 2 == 1:
                out[r, c] = 1 if m[r, c] != 0 else 0
            else:
                out[r, c] = 9 if m[r, c] != 0 else 0
    return out


def _jogada_cnn(
    estado: EstadoTabuleiro,
    interp,
    tipo: Literal["1ch", "12ch"],
) -> tuple[str | None, dict[str, float]]:
    det_ent = interp.get_input_details()
    det_sai = interp.get_output_details()

    if tipo == "12ch":
        from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais
        m_ds = _partida_para_dataset(estado.matriz)
        entrada = extrair_canais(m_ds).astype(np.float32)[np.newaxis, ...]  # (1,4,3,12)
    else:
        entrada = normalizar_para_cnn(estado.matriz, CONTEXTO_PARTIDA)[np.newaxis, ..., np.newaxis]

    interp.set_tensor(det_ent[0]["index"], entrada)
    interp.invoke()
    saida = interp.get_tensor(det_sai[0]["index"])[0]

    todos = todos_labels_canonicos(estado.linhas, estado.colunas)
    idx = {l: i for i, l in enumerate(todos)}

    disponiveis = estado.tracos_disponiveis()
    if not disponiveis:
        return None, {}

    probs = {t: float(saida[idx[t]]) for t in disponiveis}
    return max(disponiveis, key=lambda t: probs[t]), probs


# ── Helpers Oráculo ───────────────────────────────────────────────────────────

def _carregar_oraculo(caminho: str, tamanho: str) -> dict:
    if tamanho != "pequeno":
        print(f"Erro: oráculo só disponível para tamanho 'pequeno' (recebido: {tamanho!r}).")
        sys.exit(1)
    if not Path(caminho).exists():
        print(f"Erro: tablebase não encontrada: {caminho}")
        sys.exit(1)
    linhas, colunas = TAMANHOS[tamanho]
    labels, edge_rc, n_edges, ebm, ebc, _ = oraculo_construir_mapeamento(linhas, colunas)
    label_to_idx = {l: i for i, l in enumerate(labels)}
    print("Carregando tablebase para RAM (~2 GiB)... ", end="", flush=True)
    val = oraculo_carregar(caminho, mmap=False)
    print("pronto.")
    return {
        "tipo": "oraculo",
        "val": val,
        "label_to_idx": label_to_idx,
        "n_edges": n_edges,
        "ebm": ebm,
        "ebc": ebc,
        "edge_rc": edge_rc,
        "linhas": linhas,
        "colunas": colunas,
    }


def _jogada_oraculo(
    estado: EstadoTabuleiro, agente: dict
) -> tuple[str | None, dict[str, int]]:
    s = matriz_para_bitmask(estado.matriz, agente["linhas"], agente["colunas"], agente["edge_rc"])
    scores = scores_de_todas_jogadas_exato(
        agente["val"], s, agente["n_edges"], agente["ebm"], agente["ebc"]
    )
    disponiveis = estado.tracos_disponiveis()
    if not disponiveis:
        return None, {}
    l2i = agente["label_to_idx"]
    best = max(disponiveis, key=lambda t: scores.get(l2i[t], -999))
    scores_disp = {t: scores.get(l2i[t], -999) for t in disponiveis}
    return best, scores_disp


# ── Classe principal ──────────────────────────────────────────────────────────

class SimuladorTatico:
    """Simulador tático com suporte a múltiplos modos de jogo."""

    def __init__(
        self,
        tamanho: str,
        modo: str,
        profundidade: int,
        modelo1: str | None,
        modelo2: str | None,
        timer_ms: int,
        delay_cpu_ms: int,
        oraculo: str | None = None,
        autostart_delay_ms: int = 0,
    ) -> None:
        import pygame
        self.pg = pygame
        self.tamanho = tamanho
        self.modo = modo
        self.profundidade = profundidade
        self.timer_ms = timer_ms
        self.delay_cpu_ms = delay_cpu_ms
        self.autostart_delay_ms = autostart_delay_ms

        # Agentes
        self.agente_j1 = self._criar_agente_j1(modo, modelo1, oraculo, tamanho)
        self.agente_j2 = self._criar_agente_j2(modo, modelo1, modelo2, profundidade, oraculo, tamanho)
        self.nome_j1, self.nome_j2 = self._nomes(modo, profundidade, modelo1, modelo2)

        # Placar acumulado
        self.acum = {"j1": 0, "j2": 0, "empates": 0}
        self.num_partidas = 0
        self._j1_comeca_agora = True

        # Estado de jogo (populado por _iniciar_partida)
        self.estado: EstadoTabuleiro = None  # type: ignore
        self.vez_j1 = True
        self.caixas_j1 = 0
        self.caixas_j2 = 0
        self.partida_encerrada = False
        self.pensando = False
        self.jogada_pendente: str | None = None
        self.jogada_pendente_jog: int = 1
        self.delay_start: float | None = None
        self.pausado = False
        self.timer_inicio = 0.0
        self._fim_at: float | None = None
        self.tempos_decisao: list[float] = []
        self.ultima_probs_j1: dict | None = None
        self.ultima_escolha_j1: str | None = None
        self.ultima_probs_j2: dict | None = None
        self.ultima_escolha_j2: str | None = None

        self._iniciar_partida(j1_comeca=True)

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _criar_agente_j1(self, modo, modelo1, oraculo, tamanho):
        if modo in ("humano_vs_cnn", "humano_vs_oraculo"):
            return {"tipo": "humano"}
        # cnn_vs_cnn, cnn_vs_minimax, cnn_vs_oraculo
        interp = self._validar_e_carregar(modelo1, tamanho)
        return {"tipo": "cnn", "interp": interp, "tipo_modelo": _tipo_modelo(interp)}

    def _criar_agente_j2(self, modo, modelo1, modelo2, prof, oraculo, tamanho):
        if modo == "humano_vs_cnn":
            interp = self._validar_e_carregar(modelo1, tamanho)
            return {"tipo": "cnn", "interp": interp, "tipo_modelo": _tipo_modelo(interp)}
        if modo == "cnn_vs_minimax":
            return {"tipo": "minimax", "prof": prof}
        if modo in ("humano_vs_oraculo", "cnn_vs_oraculo"):
            return _carregar_oraculo(oraculo, tamanho)
        # cnn_vs_cnn
        interp = self._validar_e_carregar(modelo2, tamanho)
        return {"tipo": "cnn", "interp": interp, "tipo_modelo": _tipo_modelo(interp)}

    def _validar_e_carregar(self, caminho: str | None, tamanho: str):
        if not caminho or not Path(caminho).exists():
            print(f"Erro: modelo .tflite inválido ou inexistente: {caminho}")
            sys.exit(1)
        interp = _carregar_modelo(caminho)
        # Aviso se 12ch em tabuleiro não-pequeno
        tp = _tipo_modelo(interp)
        if tp == "12ch" and tamanho != "pequeno":
            print(f"Aviso: modelo 12ch só suporta tabuleiro 'pequeno'. Usando tamanho={tamanho}.")
        return interp

    def _nomes(self, modo, prof, m1, m2):
        if modo == "humano_vs_cnn":
            label = "CNN" if m1 and "12ch" not in str(m1) else "CNN-12ch"
            return "Você", label
        if modo == "humano_vs_oraculo":
            return "Você", "Oráculo"
        if modo == "cnn_vs_minimax":
            return "CNN", f"Minimax(p={prof})"
        if modo == "cnn_vs_oraculo":
            n1 = Path(m1).stem[:14] if m1 else "CNN"
            return n1, "Oráculo"
        n1 = Path(m1).stem if m1 else "CNN1"
        n2 = Path(m2).stem if m2 else "CNN2"
        return n1[:14], n2[:14]

    # ── Controle de partida ───────────────────────────────────────────────────

    def _iniciar_partida(self, j1_comeca: bool) -> None:
        self.estado = EstadoTabuleiro.de_tamanho(self.tamanho)
        self.vez_j1 = j1_comeca
        self.caixas_j1 = 0
        self.caixas_j2 = 0
        self.partida_encerrada = False
        self.pensando = False
        self.jogada_pendente = None
        self.jogada_pendente_jog = 1
        self.delay_start = None
        self._cancelado = False
        self._fim_at = None
        self.timer_inicio = time.time()
        self.tempos_decisao.clear()
        self.ultima_probs_j1 = None
        self.ultima_escolha_j1 = None
        self.ultima_probs_j2 = None
        self.ultima_escolha_j2 = None

    def _nova_partida(self) -> None:
        self._j1_comeca_agora = not self._j1_comeca_agora
        self._iniciar_partida(j1_comeca=self._j1_comeca_agora)

    def _zerar_placar(self) -> None:
        self.acum = {"j1": 0, "j2": 0, "empates": 0}
        self.num_partidas = 0
        self._j1_comeca_agora = True
        self._iniciar_partida(j1_comeca=True)

    def _verificar_fim(self) -> None:
        if not self.estado.esta_terminal():
            return
        self.partida_encerrada = True
        self._fim_at = time.time()
        self.num_partidas += 1
        if self.caixas_j1 > self.caixas_j2:
            self.acum["j1"] += 1
        elif self.caixas_j2 > self.caixas_j1:
            self.acum["j2"] += 1
        else:
            self.acum["empates"] += 1
        media = sum(self.tempos_decisao) / max(1, len(self.tempos_decisao))
        log.info(
            "Partida %d encerrada — %s: %d, %s: %d | tempo médio CPU: %.1fms",
            self.num_partidas, self.nome_j1, self.caixas_j1,
            self.nome_j2, self.caixas_j2, media,
        )

    # ── Turno / agentes ───────────────────────────────────────────────────────

    def _e_turno_humano(self) -> bool:
        agente = self.agente_j1 if self.vez_j1 else self.agente_j2
        return agente["tipo"] == "humano"

    def _agente_atual(self) -> dict:
        return self.agente_j1 if self.vez_j1 else self.agente_j2

    def _precisa_cpu_pensar(self) -> bool:
        return (
            not self.partida_encerrada
            and not self.pensando
            and self.jogada_pendente is None
            and not self.pausado
            and self._agente_atual()["tipo"] in ("cnn", "minimax", "oraculo")
        )

    def _disparar_cpu(self) -> None:
        agente = self.agente_j1 if self.vez_j1 else self.agente_j2
        jogador = 1 if self.vez_j1 else -1
        self.pensando = True

        self._cancelado = False

        def worker():
            inicio = time.perf_counter()
            estado_c = self.estado.clonar()
            traco = None
            probs: dict[str, float] = {}

            disponiveis = estado_c.tracos_disponiveis()
            n_total = len(todos_labels_canonicos(estado_c.linhas, estado_c.colunas))
            is_abertura = len(disponiveis) == n_total

            if is_abertura:
                traco = random.choice(disponiveis)
                log.info("CPU (j%d) abertura aleatória: %s", jogador, traco)
            elif agente["tipo"] == "cnn":
                traco, probs = _jogada_cnn(estado_c, agente["interp"], agente["tipo_modelo"])
                top5 = ", ".join(
                    f"{k}: {v*100:.1f}%"
                    for k, v in sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
                )
                log.info("CNN (j%d) top5: %s", jogador, top5)
            elif agente["tipo"] == "minimax":
                traco = minimax_melhor(estado_c, agente["prof"])
            elif agente["tipo"] == "oraculo":
                traco, probs = _jogada_oraculo(estado_c, agente)
                top5 = ", ".join(
                    f"{k}: {v:+d}"
                    for k, v in sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
                )
                log.info("Oráculo (j%d) top5: %s", jogador, top5)

            dur = (time.perf_counter() - inicio) * 1000
            self.tempos_decisao.append(dur)
            log.info("CPU (j%d) jogou %s em %.2fms", jogador, traco, dur)

            if self._cancelado:
                self.pensando = False
                return

            if jogador == 1:
                self.ultima_probs_j1 = probs or None
                self.ultima_escolha_j1 = traco
            else:
                self.ultima_probs_j2 = probs or None
                self.ultima_escolha_j2 = traco

            self.jogada_pendente = traco
            self.jogada_pendente_jog = jogador
            self.pensando = False

        threading.Thread(target=worker, daemon=True).start()

    def _aplicar_jogada(self, traco: str, jogador: int) -> int:
        fechadas = self.estado.aplicar_traco(traco, jogador)
        if jogador == 1:
            self.caixas_j1 += fechadas
        else:
            self.caixas_j2 += fechadas
        self._verificar_fim()
        if not self.partida_encerrada and fechadas == 0:
            self.vez_j1 = not self.vez_j1
        self.timer_inicio = time.time()
        return fechadas

    def _aplicar_jogada_cpu(self) -> None:
        traco = self.jogada_pendente
        jog = self.jogada_pendente_jog
        self.jogada_pendente = None
        self.delay_start = None
        if traco:
            self._aplicar_jogada(traco, jog)

    def _processar_clique_humano(self, mx: int, my: int) -> None:
        traco = self._clique_para_traco(mx, my)
        if not traco:
            return
        jog = 1 if self.vez_j1 else -1
        fechadas = self._aplicar_jogada(traco, jog)
        log.info("Humano jogou %s (fechou %d)", traco, fechadas)

    def _jogada_timer_humano(self) -> None:
        disponiveis = self.estado.tracos_disponiveis()
        if disponiveis:
            jog = 1 if self.vez_j1 else -1
            self._aplicar_jogada(random.choice(disponiveis), jog)
            log.info("Timer esgotado — jogada aleatória para humano")

    def _forcar_aleatoria_cpu(self) -> None:
        """Cancela o pensamento da CPU e joga aleatoriamente quando o timer expira."""
        self._cancelado = True
        self.pensando = False
        self.jogada_pendente = None
        self.delay_start = None
        disponiveis = self.estado.tracos_disponiveis()
        if disponiveis:
            jog = 1 if self.vez_j1 else -1
            self._aplicar_jogada(random.choice(disponiveis), jog)
            log.info("Timer CPU esgotado — jogada aleatória (jog=%d)", jog)

    # ── Loop principal ────────────────────────────────────────────────────────

    def executar(self) -> None:
        pg = self.pg
        pg.init()
        tela = pg.display.set_mode((_LARGURA, _ALTURA))
        pg.display.set_caption(f"Arena Sagaz — {self.tamanho} — {self.modo}")

        def _fonte(candidatos, tamanho, bold=False):
            for nome in candidatos:
                p = pg.font.match_font(nome, bold=bold)
                if p:
                    return pg.font.Font(p, tamanho)
            return pg.font.SysFont(None, tamanho, bold=bold)

        # Impact/Bahnschrift para títulos e HUD — visual de jogo
        fonte_g = _fonte(["impact", "bahnschrift", "arialblack", "arial"], 17, bold=False)
        # Consolas/Segoe UI para linhas de dados — legível e limpo
        fonte_p = _fonte(["consolas", "segoeui", "verdana", "arial"], 15, bold=False)
        clock = pg.time.Clock()

        rodando = True
        while rodando:
            # 1. Trigger CPU
            if self._precisa_cpu_pensar():
                self._disparar_cpu()

            # 2. Aplicar jogada CPU (com delay opcional)
            if self.jogada_pendente is not None and not self.pausado:
                if self.delay_cpu_ms > 0:
                    if self.delay_start is None:
                        self.delay_start = time.time()
                    elif time.time() - self.delay_start >= self.delay_cpu_ms / 1000:
                        self._aplicar_jogada_cpu()
                else:
                    self._aplicar_jogada_cpu()

            # 3. Timer humano
            if (
                self._e_turno_humano()
                and not self.partida_encerrada
                and self.timer_ms > 0
                and time.time() - self.timer_inicio > self.timer_ms / 1000
            ):
                self._jogada_timer_humano()

            # 3b. Timer CPU (cancela Minimax/CNN que demore demais calculando)
            if (
                not self._e_turno_humano()
                and not self.partida_encerrada
                and self.timer_ms > 0
                and self.pensando  # só enquanto calcula; delay visual não conta
                and not self._cancelado
                and time.time() - self.timer_inicio > self.timer_ms / 1000
            ):
                self._forcar_aleatoria_cpu()

            # 3c. Autostart
            if (
                self.autostart_delay_ms > 0
                and self.partida_encerrada
                and self._fim_at is not None
                and not self.pausado
                and time.time() - self._fim_at >= self.autostart_delay_ms / 1000
            ):
                self._nova_partida()

            # 4. Eventos
            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    rodando = False
                elif ev.type == pg.KEYDOWN:
                    if ev.key == pg.K_q:
                        rodando = False
                    elif ev.key == pg.K_r:
                        self._nova_partida()
                    elif ev.key == pg.K_z:
                        self._zerar_placar()
                    elif ev.key == pg.K_p and self.modo != "humano_vs_cnn":
                        self.pausado = not self.pausado
                elif (
                    ev.type == pg.MOUSEBUTTONDOWN
                    and ev.button == 1
                    and self._e_turno_humano()
                    and not self.partida_encerrada
                    and not self.pensando
                ):
                    self._processar_clique_humano(*ev.pos)

            # 5. Desenhar
            self._desenhar(tela, fonte_g, fonte_p)
            pg.display.flip()
            clock.tick(30)

        pg.quit()

    # ── Geometria do tabuleiro ────────────────────────────────────────────────

    def _espaco_grade(self) -> tuple[float, float]:
        linhas, colunas = TAMANHOS[self.tamanho]
        sw = (_LARGURA_TAB - 2 * _MARGEM) / colunas
        sh = (_BOARD_H - 2 * _MARGEM) / linhas
        return sw, sh

    def _ponto_tela(self, pr: int, pc: int) -> tuple[int, int]:
        sw, sh = self._espaco_grade()
        return int(_MARGEM + pc * sw), int(_MARGEM + pr * sh)

    def _tracos_clicaveis(self):
        sw, sh = self._espaco_grade()
        result = []
        for tr in self.estado.tracos_disponiveis():
            tipo, r_s, c_s = tr.split("_")
            r, c = int(r_s), int(c_s)
            if tipo == "H":
                x1, y1 = self._ponto_tela(r // 2, (c - 1) // 2)
                x2, y2 = self._ponto_tela(r // 2, (c + 1) // 2)
            else:
                x1, y1 = self._ponto_tela((r - 1) // 2, c // 2)
                x2, y2 = self._ponto_tela((r + 1) // 2, c // 2)
            result.append((tr, x1, y1, x2, y2))
        return result

    def _clique_para_traco(self, mx: int, my: int, margem: int = 14) -> str | None:
        melhor, menor_d = None, float("inf")
        for tr, x1, y1, x2, y2 in self._tracos_clicaveis():
            dx, dy = x2 - x1, y2 - y1
            sq = dx * dx + dy * dy
            if sq == 0:
                d = ((mx - x1) ** 2 + (my - y1) ** 2) ** 0.5
            else:
                t = max(0.0, min(1.0, ((mx - x1) * dx + (my - y1) * dy) / sq))
                px, py = x1 + t * dx, y1 + t * dy
                d = ((mx - px) ** 2 + (my - py) ** 2) ** 0.5
            if d < menor_d and d <= margem:
                menor_d = d
                melhor = tr
        return melhor

    # ── Desenho ───────────────────────────────────────────────────────────────

    def _desenhar(self, tela, fonte_g, fonte_p) -> None:
        pg = self.pg
        tela.fill(_C_FUNDO)

        # Painel lateral
        pg.draw.rect(tela, _C_PAINEL, (_LARGURA_TAB, 0, _LARGURA_PAINEL, _ALTURA))
        pg.draw.line(tela, _C_SEP, (_LARGURA_TAB, 0), (_LARGURA_TAB, _ALTURA), 1)

        self._desenhar_tabuleiro(tela)
        self._desenhar_hud(tela, fonte_g, fonte_p)
        self._desenhar_painel(tela, fonte_g, fonte_p)

    def _desenhar_tabuleiro(self, tela) -> None:
        pg = self.pg
        linhas, colunas = TAMANHOS[self.tamanho]
        sw, sh = self._espaco_grade()

        # Traços jogados e caixas fechadas
        for r in range(self.estado.matriz.shape[0]):
            for c in range(self.estado.matriz.shape[1]):
                val = self.estado.matriz[r, c]
                if val == 0 or val == 8:
                    continue
                cor = _C_J1 if val == 1 else _C_J2
                if r % 2 == 0 and c % 2 == 1:  # H
                    p1 = self._ponto_tela(r // 2, (c - 1) // 2)
                    p2 = self._ponto_tela(r // 2, (c + 1) // 2)
                    pg.draw.line(tela, cor, p1, p2, _ESP_TRACO)
                elif r % 2 == 1 and c % 2 == 0:  # V
                    p1 = self._ponto_tela((r - 1) // 2, c // 2)
                    p2 = self._ponto_tela((r + 1) // 2, c // 2)
                    pg.draw.line(tela, cor, p1, p2, _ESP_TRACO)
                elif r % 2 == 1 and c % 2 == 1:  # caixa
                    bx1, by1 = self._ponto_tela((r - 1) // 2, (c - 1) // 2)
                    bx2, by2 = self._ponto_tela((r + 1) // 2, (c + 1) // 2)
                    rect = pg.Rect(bx1, by1, bx2 - bx1, by2 - by1)
                    rect.inflate_ip(-18, -18)
                    s = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
                    s.fill((*cor, 90))
                    tela.blit(s, rect.topleft)

        # Fantasmas clicáveis
        mouse = pg.mouse.get_pos()
        for tr, x1, y1, x2, y2 in self._tracos_clicaveis():
            dx, dy = x2 - x1, y2 - y1
            sq = dx * dx + dy * dy
            if sq > 0:
                t = max(0.1, min(0.9, ((mouse[0] - x1) * dx + (mouse[1] - y1) * dy) / sq))
                px, py = x1 + t * dx, y1 + t * dy
                dist = ((mouse[0] - px) ** 2 + (mouse[1] - py) ** 2) ** 0.5
            else:
                dist = 999
            cor_f = _C_HOVER if dist <= 14 and self._e_turno_humano() else _C_GHOST
            pg.draw.line(tela, cor_f, (x1, y1), (x2, y2), _ESP_GHOST)

        # Pontos
        for pr in range(linhas + 1):
            for pc in range(colunas + 1):
                x, y = self._ponto_tela(pr, pc)
                pg.draw.circle(tela, _C_GRADE, (x, y), 5)

        # Fim de partida
        if self.partida_encerrada:
            if self.caixas_j1 > self.caixas_j2:
                msg = f"{self.nome_j1} venceu!"
            elif self.caixas_j2 > self.caixas_j1:
                msg = f"{self.nome_j2} venceu!"
            else:
                msg = "Empate!"
            fonte_big = self.pg.font.SysFont("monospace", 28, bold=True)
            txt = fonte_big.render(msg, True, _C_VENC)
            bx = _LARGURA_TAB // 2 - txt.get_width() // 2
            by = _BOARD_H // 2 - txt.get_height() // 2
            sombra = fonte_big.render(msg, True, (0, 0, 0))
            tela.blit(sombra, (bx + 2, by + 2))
            tela.blit(txt, (bx, by))

    def _desenhar_hud(self, tela, fonte_g, fonte_p) -> None:
        pg = self.pg
        hud_y = _BOARD_H + 8
        cor_j1_nome = _C_J1
        cor_j2_nome = _C_J2

        # Linha placar atual
        placar = f"{self.nome_j1}: {self.caixas_j1}  vs  {self.nome_j2}: {self.caixas_j2}"
        tela.blit(fonte_g.render(placar, True, _C_TEXTO), (10, hud_y))

        # Timer
        if self.timer_ms > 0 and not self.partida_encerrada:
            elapsed = time.time() - self.timer_inicio
            restante = max(0.0, self.timer_ms / 1000 - elapsed)
            pct = restante / (self.timer_ms / 1000)
            cor_t = _C_T_OK if pct > 0.5 else (_C_T_WARN if pct > 0.2 else _C_T_CRIT)
            bar_w = int((_LARGURA_TAB - 20) * pct)
            pg.draw.rect(tela, (40, 40, 60), (10, hud_y + 26, _LARGURA_TAB - 20, 8), border_radius=4)
            if bar_w > 0:
                pg.draw.rect(tela, cor_t, (10, hud_y + 26, bar_w, 8), border_radius=4)
            t_txt = f"⏱ {restante:.1f}s"
            tela.blit(fonte_p.render(t_txt, True, cor_t), (10, hud_y + 38))

        # Status
        if self.pausado:
            status = "⏸ PAUSADO — P para resumir"
            cor_s = _C_PAUSE
        elif self.partida_encerrada:
            status = "R=nova partida | Z=zerar placar"
            cor_s = _C_VENC
        elif self.pensando or self.jogada_pendente is not None:
            agente = self._agente_atual()
            nome_ag = self.nome_j1 if self.vez_j1 else self.nome_j2
            status = f"{nome_ag} pensando..."
            cor_s = _C_SUB
        elif self._e_turno_humano():
            status = "Sua vez — clique um traço"
            cor_s = _C_T_OK
        else:
            status = "CPU jogando..."
            cor_s = _C_SUB

        tela.blit(fonte_p.render(status, True, cor_s), (10, hud_y + 58))

        # Atalhos
        atalhos = "R=nova partida  Z=zerar placar"
        if self.modo != "humano_vs_cnn":
            atalhos += "  P=pausar"
        atalhos += "  Q=sair"
        tela.blit(fonte_p.render(atalhos, True, _C_SUB), (10, hud_y + 80))

    def _desenhar_painel(self, tela, fonte_g, fonte_p) -> None:
        pg = self.pg
        px = _LARGURA_TAB + 12
        py = 14

        # ── Placar acumulado
        tela.blit(fonte_g.render("PLACAR ACUMULADO", True, _C_GRADE), (px, py))
        py += 26
        tela.blit(fonte_p.render(f"Partida #{self.num_partidas}", True, _C_SUB), (px, py))
        py += 20

        def linha_placar(nome, wins, cor):
            nonlocal py
            s = f"{nome}: {wins} {'vitória' if wins == 1 else 'vitórias'}"
            tela.blit(fonte_p.render(s, True, cor), (px, py))
            py += 18

        linha_placar(self.nome_j1, self.acum["j1"], _C_J1)
        linha_placar(self.nome_j2, self.acum["j2"], _C_J2)
        tela.blit(
            fonte_p.render(f"Empates: {self.acum['empates']}", True, _C_SUB), (px, py)
        )
        py += 22

        # Quem começa
        prox = self.nome_j2 if self._j1_comeca_agora else self.nome_j1
        tela.blit(
            fonte_p.render(f"Próxima partida inicia: {prox}", True, _C_SUB), (px, py)
        )
        py += 22

        # Separador
        pg.draw.line(tela, _C_SEP, (px, py), (px + _LARGURA_PAINEL - 24, py), 1)
        py += 10

        # largura máxima das barras: reserva 28px extras para seta "◄" + margem direita
        _bar_max = _LARGURA - 8 - px - 130 - 28

        # ── Probabilidades CNN
        def _desenhar_probs(titulo, probs, escolha, cor_tit):
            nonlocal py
            if not probs:
                return
            tela.blit(fonte_g.render(titulo, True, cor_tit), (px, py))
            py += 24
            top = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:10]
            max_v = top[0][1] if top else 1.0
            bar_max = _bar_max
            for k, v in top:
                eh_esc = k == escolha
                cor_nome = _C_BAR_ESC if eh_esc else _C_TEXTO
                nome_r = fonte_p.render(k, True, cor_nome)
                tela.blit(nome_r, (px, py))
                pct_txt = f"{v*100:5.1f}%"
                pct_r = fonte_p.render(pct_txt, True, cor_nome)
                tela.blit(pct_r, (px + 75, py))
                bar_w = int(bar_max * (v / max(max_v, 1e-9)))
                cor_bar = _C_BAR_ESC if eh_esc else _C_BAR_PROB
                if bar_w > 0:
                    pg.draw.rect(tela, cor_bar, (px + 130, py + 2, bar_w, 11), border_radius=3)
                if eh_esc:
                    arr = fonte_p.render("◄", True, _C_BAR_ESC)
                    tela.blit(arr, (px + 133 + bar_w, py))
                py += 20
            py += 4

        def _desenhar_scores_oraculo(titulo, scores, escolha, cor_tit):
            nonlocal py
            if not scores:
                return
            tela.blit(fonte_g.render(titulo, True, cor_tit), (px, py))
            py += 24
            top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
            max_abs = max((abs(v) for _, v in top), default=1) or 1
            bar_max = _bar_max
            for k, v in top:
                eh_esc = k == escolha
                cor = _C_BAR_ESC if eh_esc else _C_TEXTO
                tela.blit(fonte_p.render(k, True, cor), (px, py))
                tela.blit(fonte_p.render(f"{v:+4d}", True, cor), (px + 75, py))
                bar_w = int(bar_max * abs(v) / max_abs)
                cor_bar = _C_BAR_ESC if eh_esc else _C_BAR_PROB
                if bar_w > 0:
                    pg.draw.rect(tela, cor_bar, (px + 130, py + 2, bar_w, 11), border_radius=3)
                if eh_esc:
                    tela.blit(fonte_p.render("◄", True, _C_BAR_ESC), (px + 133 + bar_w, py))
                py += 18
            py += 4

        # CNN J1 (se aplicável)
        if self.agente_j1["tipo"] == "cnn":
            _desenhar_probs(
                f"CNN ({self.nome_j1}) — probs:",
                self.ultima_probs_j1,
                self.ultima_escolha_j1,
                _C_J1,
            )

        # Oráculo J1 (improvável, mas suportado)
        if self.agente_j1["tipo"] == "oraculo":
            _desenhar_scores_oraculo(
                f"Oráculo ({self.nome_j1}) — scores:",
                self.ultima_probs_j1,
                self.ultima_escolha_j1,
                _C_J1,
            )

        # CNN J2 (se aplicável)
        if self.agente_j2["tipo"] == "cnn":
            _desenhar_probs(
                f"CNN ({self.nome_j2}) — probs:",
                self.ultima_probs_j2,
                self.ultima_escolha_j2,
                _C_J2,
            )

        # Oráculo J2
        if self.agente_j2["tipo"] == "oraculo":
            _desenhar_scores_oraculo(
                f"Oráculo ({self.nome_j2}) — scores:",
                self.ultima_probs_j2,
                self.ultima_escolha_j2,
                _C_J2,
            )

        # Tempo médio
        if self.tempos_decisao:
            media = sum(self.tempos_decisao) / len(self.tempos_decisao)
            tela.blit(
                fonte_p.render(f"Tempo médio CPU: {media:.1f}ms", True, _C_SUB),
                (px, _ALTURA - 24),
            )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador Tático Arena Sagaz")
    parser.add_argument(
        "--tamanho", choices=["pequeno", "medio", "grande"], default="pequeno"
    )
    parser.add_argument(
        "--modo",
        choices=[
            "humano_vs_cnn",
            "humano_vs_oraculo",
            "cnn_vs_cnn",
            "cnn_vs_minimax",
            "cnn_vs_oraculo",
        ],
        default="humano_vs_cnn",
    )
    parser.add_argument("--profundidade", type=int, default=7)
    parser.add_argument("--modelo", type=str, help="Caminho para .tflite (CNN principal)")
    parser.add_argument(
        "--modelo2", type=str, help="Caminho para .tflite da CNN2 (modo cnn_vs_cnn)"
    )
    parser.add_argument(
        "--oraculo",
        type=str,
        default="dados/oraculo_pontinhos/tablebase_pequeno_4x3.npy",
        help="Caminho para a tablebase .npy do oráculo (padrão: dados/oraculo_pontinhos/tablebase_pequeno_4x3.npy)",
    )
    parser.add_argument(
        "--timer",
        type=int,
        default=0,
        help="Tempo limite por jogada em segundos (0=sem limite)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Delay visual entre jogadas CPU em ms (padrão: 0; use ~1200 para assistir cnn_vs_cnn)",
    )
    parser.add_argument(
        "--autostart",
        type=int,
        default=0,
        metavar="MS",
        help="Inicia nova partida automaticamente N ms após o fim (0=desativado)",
    )
    args = parser.parse_args()

    if args.modo == "cnn_vs_cnn" and not args.modelo2:
        parser.error("--modo cnn_vs_cnn requer --modelo e --modelo2")
    if args.modo in ("humano_vs_cnn", "cnn_vs_minimax", "cnn_vs_oraculo") and not args.modelo:
        parser.error(f"--modo {args.modo} requer --modelo")
    if args.modo in ("humano_vs_oraculo", "cnn_vs_oraculo") and args.tamanho != "pequeno":
        parser.error("Oráculo só disponível para --tamanho pequeno")

    sim = SimuladorTatico(
        tamanho=args.tamanho,
        modo=args.modo,
        profundidade=args.profundidade,
        modelo1=args.modelo,
        modelo2=args.modelo2,
        timer_ms=args.timer * 1000,
        delay_cpu_ms=args.delay,
        oraculo=args.oraculo,
        autostart_delay_ms=args.autostart,
    )
    sim.executar()


if __name__ == "__main__":
    main()
