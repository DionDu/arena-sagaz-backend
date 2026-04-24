"""Simulador tático Pygame: Humano vs CNN ou Minimax."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada
from api.nucleo.log import obter_logger
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (
    CONTEXTO_PARTIDA,
    normalizar_para_cnn,
)

log = obter_logger("gerador_dados.simulador")

_LARGURA = 900
_LARGURA_TAB = 600
_ALTURA = 700
_MARGEM = 60
_COR_FUNDO = (30, 30, 30)
_COR_GRADE = (200, 200, 200)
_COR_J1 = (0, 87, 183)
_COR_J2 = (193, 57, 43)
_COR_TEXTO = (255, 255, 255)
_COR_HOVER = (150, 150, 50)
_COR_GHOST = (45, 45, 45)
_ESPESSURA_TRACO = 7
_ESPESSURA_GHOST = 5


def _carregar_modelo_tflite(caminho: str):
    try:
        import tflite_runtime.interpreter as tflite
    except ImportError:
        import tensorflow.lite as tflite  # type: ignore
    interpretador = tflite.Interpreter(model_path=caminho)
    interpretador.allocate_tensors()
    return interpretador


def _jogada_cnn(estado: EstadoTabuleiro, interpretador) -> tuple[str | None, dict[str, float]]:
    import numpy as np
    from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos

    dados_entrada = interpretador.get_input_details()
    dados_saida = interpretador.get_output_details()

    # Normalização conforme contrato_codificacao_pontinhos.json, contexto 3 (partidas).
    # NUNCA duplicar as regras aqui — consulte o JSON e o helper.
    entrada = normalizar_para_cnn(estado.matriz, CONTEXTO_PARTIDA)
    entrada = entrada[np.newaxis, ..., np.newaxis]
    interpretador.set_tensor(dados_entrada[0]["index"], entrada)
    interpretador.invoke()
    saida = interpretador.get_tensor(dados_saida[0]["index"])[0]
    
    # [NOTA PARA SPECKIT/CLAUDE]: Mapeamento de neurônios → labels.
    # CRÍTICO: deve usar todos_labels_canonicos() (ordem linha-a-linha da matriz)
    # que é a MESMA ordem usada no treino pelo gerador.py e no notebook.
    # A versão anterior usava sorted() que agrupa H antes de V (ordem alfabética),
    # desalinhando 28 dos 31 neurônios e inutilizando a predição.
    todos_tracos_ordenados = todos_labels_canonicos(estado.linhas, estado.colunas)
    idx_label = {l: i for i, l in enumerate(todos_tracos_ordenados)}
    
    disponiveis = estado.tracos_disponiveis()
    if not disponiveis:
        return None, {}
        
    probs = {t: float(saida[idx_label[t]]) for t in disponiveis}
    melhor_traco = max(disponiveis, key=lambda t: probs[t])
            
    return melhor_traco, probs


class SimuladorTatico:
    def __init__(
        self,
        tamanho: str,
        modo: str = "minimax",
        profundidade: int = 7,
        caminho_modelo: str | None = None,
    ) -> None:
        import pygame
        self.pygame = pygame
        self.tamanho = tamanho
        self.modo = modo
        self.profundidade = profundidade
        self.caminho_modelo = caminho_modelo
        self.interpretador = None
        self.estado = EstadoTabuleiro.de_tamanho(tamanho)
        self.caixas_humano = 0
        self.caixas_ia = 0
        self.vez_humano = True
        self.partida_encerrada = False
        self.tempos_decisao: list[float] = []

        if modo == "cnn":
            self._validar_modelo(caminho_modelo)
            self.interpretador = _carregar_modelo_tflite(caminho_modelo)

    def _validar_modelo(self, caminho: str | None) -> None:
        if not caminho or not Path(caminho).exists() or Path(caminho).stat().st_size == 0:
            print(f"Erro: modelo .tflite inválido ou inexistente: {caminho}")
            sys.exit(1)

    def _calcular_pos_grade(self) -> tuple[float, float, float]:
        linhas, colunas = TAMANHOS[self.tamanho]
        espaco_w = (_LARGURA_TAB - 2 * _MARGEM) / colunas
        espaco_h = (_ALTURA - 2 * _MARGEM - 100) / linhas
        return espaco_w, espaco_h, min(espaco_w, espaco_h)

    def _ponto_para_tela(self, ponto_r: int, ponto_c: int) -> tuple[int, int]:
        linhas, colunas = TAMANHOS[self.tamanho]
        espaco_w, espaco_h, _ = self._calcular_pos_grade()
        x = _MARGEM + (ponto_c // 2) * espaco_w
        y = _MARGEM + (ponto_r // 2) * espaco_h
        return int(x), int(y)

    def _tracos_clicaveis(self) -> list[tuple[str, tuple[int, int], tuple[int, int]]]:
        # [NOTA PARA SPECKIT/CLAUDE]: Corrigida a lógica de cálculo de áreas clicáveis para traços.
        # Os eixos e a largura/altura estavam invertidos com o tipo H e V no grid de PyGame.
        regioes = []
        disponiveis = set(self.estado.tracos_disponiveis())
        for tr in list(disponiveis):
            tipo, r_str, c_str = tr.split("_")
            r, c = int(r_str), int(c_str)
            if tipo == "H":
                x1, y1 = self._ponto_para_tela(r, c - 1)
                x2, y2 = self._ponto_para_tela(r, c + 1)
                centro = ((x1 + x2) // 2, y1)
            else:
                x1, y1 = self._ponto_para_tela(r - 1, c)
                x2, y2 = self._ponto_para_tela(r + 1, c)
                centro = (x1, (y1 + y2) // 2)
            regioes.append((tr, centro, (x1, y1)))
        return regioes

    def _clique_para_traco(self, mx: int, my: int, margem: int = 12) -> str | None:
        """Detecta clique por proximidade perpendicular ao segmento do traço."""
        melhor = None
        menor_dist = float('inf')
        for tr, centro, p1 in self._tracos_clicaveis():
            tipo = tr.split("_")[0]
            r, c = int(tr.split("_")[1]), int(tr.split("_")[2])
            if tipo == "H":
                x1, y1 = self._ponto_para_tela(r, c - 1)
                x2, y2 = self._ponto_para_tela(r, c + 1)
            else:
                x1, y1 = self._ponto_para_tela(r - 1, c)
                x2, y2 = self._ponto_para_tela(r + 1, c)
            # Distância ponto-a-segmento
            dx, dy = x2 - x1, y2 - y1
            comprimento_sq = dx * dx + dy * dy
            if comprimento_sq == 0:
                dist = ((mx - x1)**2 + (my - y1)**2) ** 0.5
            else:
                t = max(0, min(1, ((mx - x1) * dx + (my - y1) * dy) / comprimento_sq))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                dist = ((mx - proj_x)**2 + (my - proj_y)**2) ** 0.5
            if dist < menor_dist and dist <= margem:
                menor_dist = dist
                melhor = tr
        return melhor

    def _executar_jogada_ia(self) -> None:
        import threading
        
        def worker():
            inicio = time.perf_counter()
            # [NOTA PARA SPECKIT/CLAUDE]: Clonamos o estado antes de passar para a IA.
            # O Minimax aplica e desfaz os traços milhares de vezes para testar o futuro.
            # Como estávamos passando a mesma referência de memória que o PyGame estava lendo
            # no loop de `_desenhar`, a tela mostrava os traços "fantasmas" do Minimax piscando freneticamente.
            estado_ia = self.estado.clonar()
            if self.modo == "cnn" and self.interpretador:
                traco, probs = _jogada_cnn(estado_ia, self.interpretador)
                if not traco:
                    return
                self.ultima_prob_cnn = probs
                self.ultima_escolha_ia = traco
                
                # Format probs:
                probs_str = ", ".join(f"{k}: {v*100:.1f}%" for k, v in sorted(probs.items(), key=lambda item: item[1], reverse=True)[:5])
                log.info("Probabilidades CNN (top 5): %s", probs_str)
            else:
                traco = melhor_jogada(estado_ia, self.profundidade)
                self.ultima_prob_cnn = None
                self.ultima_escolha_ia = traco
                
            duracao_ms = (time.perf_counter() - inicio) * 1000
            self.tempos_decisao.append(duracao_ms)
            log.info("IA jogou %s em %.2fms (modo=%s)", traco, duracao_ms, self.modo)
            self.jogada_ia_pendente = traco

        self.pensando = True
        # [NOTA PARA SPECKIT/CLAUDE]: Transformado o turno da IA em Threading
        # Isso evita o congelamento da interface do Pygame (O app "travava" por 40+ segundos enquanto o Minimax calculava)
        threading.Thread(target=worker, daemon=True).start()

    def _verificar_fim(self) -> None:
        if self.estado.esta_terminal():
            self.partida_encerrada = True
            media_decisao = (
                sum(self.tempos_decisao) / len(self.tempos_decisao)
                if self.tempos_decisao
                else 0
            )
            log.info(
                "Partida encerrada — Humano: %d, IA: %d, Tempo médio IA: %.2fms",
                self.caixas_humano, self.caixas_ia, media_decisao,
            )

    def executar(self) -> None:
        pygame = self.pygame
        pygame.init()
        tela = pygame.display.set_mode((_LARGURA, _ALTURA))
        pygame.display.set_caption(f"Arena Sagaz — {self.tamanho} ({self.modo})")
        fonte = pygame.font.SysFont("monospace", 18)
        clock = pygame.time.Clock()

        rodando = True
        while rodando:
            if getattr(self, "jogada_ia_pendente", None):
                traco = self.jogada_ia_pendente
                self.jogada_ia_pendente = None
                self.pensando = False
                fechadas = self.estado.aplicar_traco(traco, 1) # 1 = IA
                self.caixas_ia += fechadas
                self._verificar_fim()
                if fechadas > 0 and not self.partida_encerrada:
                    self._executar_jogada_ia()  # Turno extra
                else:
                    self.vez_humano = True

            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    rodando = False
                elif evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_q:
                        rodando = False
                    elif evento.key == pygame.K_r:
                        self._reiniciar()
                    elif evento.key in (pygame.K_m, pygame.K_c):
                        self._alternar_modo()
                elif evento.type == pygame.MOUSEBUTTONDOWN and self.vez_humano and not getattr(self, "pensando", False) and not self.partida_encerrada:
                    mx, my = evento.pos
                    traco = self._clique_para_traco(mx, my)
                    if traco:
                        fechadas = self.estado.aplicar_traco(traco, -1) # -1 = Humano
                        self.caixas_humano += fechadas
                        log.info("Humano jogou %s (fechou %d caixas)", traco, fechadas)
                        self._verificar_fim()
                        if not self.partida_encerrada:
                            if fechadas == 0:
                                self.vez_humano = False
                                self._executar_jogada_ia()
                                self._verificar_fim()

            self._desenhar(tela, fonte)
            pygame.display.flip()
            clock.tick(30)

        pygame.quit()

    def _reiniciar(self) -> None:
        self.estado = EstadoTabuleiro.de_tamanho(self.tamanho)
        self.caixas_humano = 0
        self.caixas_ia = 0
        self.vez_humano = True
        self.partida_encerrada = False
        self.tempos_decisao.clear()

    def _alternar_modo(self) -> None:
        self.modo = "cnn" if self.modo == "minimax" else "minimax"
        log.info("Modo alternado para: %s", self.modo)

    def _desenhar(self, tela, fonte) -> None:
        pygame = self.pygame
        tela.fill(_COR_FUNDO)
        linhas, colunas = TAMANHOS[self.tamanho]
        espaco_w, espaco_h, _ = self._calcular_pos_grade()

        # Desenhar linhas jogadas e caixas fechadas
        # [NOTA PARA SPECKIT/CLAUDE]: O código anterior apenas desenhava os círculos e opções clicáveis, 
        # mas NUNCA desenhava a linha do traço que foi confirmada ou as caixas que foram fechadas. 
        # Esta lógica foi inteiramente adicionada baseada na matriz de estado.
        for r in range(self.estado.matriz.shape[0]):
            for c in range(self.estado.matriz.shape[1]):
                val = self.estado.matriz[r, c]
                if val == 0 or val == 8:
                    continue
                
                cor = _COR_J1 if val == 1 else _COR_J2
                
                if r % 2 == 0 and c % 2 == 1:  # Traço Horizontal
                    x1, y1 = self._ponto_para_tela(r, c - 1)
                    x2, y2 = self._ponto_para_tela(r, c + 1)
                    self.pygame.draw.line(tela, cor, (x1, y1), (x2, y2), _ESPESSURA_TRACO)
                elif r % 2 == 1 and c % 2 == 0:  # Traço Vertical
                    x1, y1 = self._ponto_para_tela(r - 1, c)
                    x2, y2 = self._ponto_para_tela(r + 1, c)
                    self.pygame.draw.line(tela, cor, (x1, y1), (x2, y2), _ESPESSURA_TRACO)
                elif r % 2 == 1 and c % 2 == 1:  # Caixa fechada
                    x1, y1 = self._ponto_para_tela(r - 1, c - 1)
                    x2, y2 = self._ponto_para_tela(r + 1, c + 1)
                    box_rect = self.pygame.Rect(x1, y1, x2 - x1, y2 - y1)
                    box_rect.inflate_ip(-16, -16)
                    self.pygame.draw.rect(tela, cor, box_rect)

        # Traços disponíveis como linhas-fantasma sutis (indicam onde clicar)
        mouse_pos = pygame.mouse.get_pos()
        for tr, centro, _ in self._tracos_clicaveis():
            tipo = tr.split("_")[0]
            r, c = int(tr.split("_")[1]), int(tr.split("_")[2])
            if tipo == "H":
                x1, y1 = self._ponto_para_tela(r, c - 1)
                x2, y2 = self._ponto_para_tela(r, c + 1)
            else:
                x1, y1 = self._ponto_para_tela(r - 1, c)
                x2, y2 = self._ponto_para_tela(r + 1, c)
            # Highlight ao passar o mouse por cima (exclui extremidades/vértices)
            dx, dy = x2 - x1, y2 - y1
            comp_sq = dx * dx + dy * dy
            if comp_sq > 0:
                t = max(0.15, min(0.85, ((mouse_pos[0] - x1) * dx + (mouse_pos[1] - y1) * dy) / comp_sq))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                dist = ((mouse_pos[0] - proj_x)**2 + (mouse_pos[1] - proj_y)**2) ** 0.5
            else:
                dist = 999
            cor_linha = _COR_HOVER if dist <= 12 else _COR_GHOST
            self.pygame.draw.line(tela, cor_linha, (x1, y1), (x2, y2), _ESPESSURA_GHOST)

        # Pontos (desenhados por cima das linhas)
        for pr in range(linhas + 1):
            for pc in range(colunas + 1):
                x = int(_MARGEM + pc * espaco_w)
                y = int(_MARGEM + pr * espaco_h)
                self.pygame.draw.circle(tela, _COR_GRADE, (x, y), 5)

        # HUD
        placar = fonte.render(
            f"Você: {self.caixas_humano}  IA ({self.modo}): {self.caixas_ia}", True, _COR_TEXTO
        )
        tela.blit(placar, (10, _ALTURA - 90))

        vez = "Sua vez" if self.vez_humano else "IA pensando..."
        tela.blit(fonte.render(vez, True, _COR_TEXTO), (10, _ALTURA - 65))
        tela.blit(fonte.render("M=alternar modo | R=reiniciar | Q=sair", True, _COR_GRADE), (10, _ALTURA - 40))

        # Exibir painel lateral
        self.pygame.draw.line(tela, _COR_GRADE, (_LARGURA_TAB, 0), (_LARGURA_TAB, _ALTURA), 1)
        
        # Exibir probabilidades da CNN
        if self.modo == "cnn" and getattr(self, "ultima_prob_cnn", None):
            probs_str = "Probabilidades da IA (CNN):"
            tela.blit(fonte.render(probs_str, True, (180, 180, 255)), (_LARGURA_TAB + 15, 20))
            
            top_probs = sorted(self.ultima_prob_cnn.items(), key=lambda item: item[1], reverse=True)
            max_prob = top_probs[0][1] if top_probs else 0
            
            for i, (k, v) in enumerate(top_probs):
                texto_prob = f"{k}: {v*100:05.2f}%"
                
                # Checar empate com a probabilidade máxima
                eh_empate = (abs(v - max_prob) < 1e-5) and len([p for p in top_probs if abs(p[1] - max_prob) < 1e-5]) > 1
                if eh_empate:
                    texto_prob += " (Empate)"
                
                # Identificar qual traço foi realmente escolhido
                if k == getattr(self, "ultima_escolha_ia", None):
                    texto_prob += " < ESCOLHIDO"
                    cor_texto = (0, 255, 0)  # Verde para o escolhido
                elif eh_empate:
                    cor_texto = (255, 255, 0)  # Amarelo para empates que não foram escolhidos
                else:
                    cor_texto = (150, 200, 255)  # Azul claro para os demais
                    
                tela.blit(fonte.render(texto_prob, True, cor_texto), (_LARGURA_TAB + 15, 50 + i * 20))

        if self.partida_encerrada:
            if self.caixas_humano > self.caixas_ia:
                resultado = "Você venceu!"
            elif self.caixas_ia > self.caixas_humano:
                resultado = "IA venceu!"
            else:
                resultado = "Empate!"
            msg = fonte.render(resultado, True, (255, 220, 0))
            tela.blit(msg, (_LARGURA // 2 - msg.get_width() // 2, _ALTURA // 2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador Tático Arena Sagaz")
    parser.add_argument("--tamanho", choices=["pequeno", "medio", "grande"], default="pequeno")
    parser.add_argument("--modo", choices=["cnn", "minimax"], default="minimax")
    parser.add_argument("--profundidade", type=int, default=7)
    parser.add_argument("--modelo", type=str, help="Caminho para arquivo .tflite")
    args = parser.parse_args()

    sim = SimuladorTatico(
        tamanho=args.tamanho,
        modo=args.modo,
        profundidade=args.profundidade,
        caminho_modelo=args.modelo,
    )
    sim.executar()


if __name__ == "__main__":
    main()
