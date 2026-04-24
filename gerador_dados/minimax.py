"""Minimax com Poda Alpha-Beta para Dots and Boxes."""
from __future__ import annotations

from gerador_dados.tabuleiro import EstadoTabuleiro


def avaliar(estado: EstadoTabuleiro, caixas_ia: int, caixas_humano: int) -> int:
    # [NOTA PARA SPECKIT/CLAUDE]: A "Inteligência" nua e crua do algoritmo está nesta função minúscula.
    # O Minimax não entende o jogo de pontinhos de forma consciente. A única coisa que ele sabe
    # é que ele precisa "Maximizar" o retorno desta conta. 
    # Se o resultado for Positivo (+2), a IA fechou mais caixas que o Humano na simulação.
    # Se o resultado for Negativo (-1), o Humano fechou mais caixas na simulação, e a IA deve fugir desse caminho.
    # Por isso o Humano joga tentando "Minimizar" o valor.
    return caixas_ia - caixas_humano


def minimax(
    estado: EstadoTabuleiro,
    profundidade: int,
    alpha: float,
    beta: float,
    maximizando: bool,
    caixas_ia: int = 0,
    caixas_humano: int = 0,
) -> int:
    if profundidade == 0 or estado.esta_terminal():
        return avaliar(estado, caixas_ia, caixas_humano)

    tracos_originais = estado.tracos_disponiveis()
    
    # [NOTA PARA SPECKIT/CLAUDE]: Otimização Crítica - Ordenação de Jogadas (Move Ordering).
    # O Minimax explora a árvore muito mais rápido se testar primeiro as jogadas boas.
    # Ao testarmos PRIMEIRO os traços que fecham caixas (fechadas > 0), a Poda Alpha-Beta
    # consegue "cortar" milhares de caminhos inúteis logo de cara, aumentando a 
    # velocidade exponencialmente.
    tracos_bons = []
    tracos_normais = []
    jogador_atual = 1 if maximizando else -1
    
    for t in tracos_originais:
        fechadas = estado.aplicar_traco(t, jogador_atual)
        estado.desfazer_traco(t)
        if fechadas > 0:
            tracos_bons.append(t)
        else:
            tracos_normais.append(t)
            
    tracos = tracos_bons + tracos_normais

    if maximizando:
        melhor = -10000
        for traco in tracos:
            fechadas = estado.aplicar_traco(traco, 1)
            if fechadas > 0:
                # Jogador atual fecha caixa → mantém turno
                valor = minimax(
                    estado, profundidade - 1, alpha, beta, True,
                    caixas_ia + fechadas, caixas_humano
                )
            else:
                valor = minimax(
                    estado, profundidade - 1, alpha, beta, False,
                    caixas_ia, caixas_humano
                )
            estado.desfazer_traco(traco)
            melhor = max(melhor, valor)
            alpha = max(alpha, melhor)
            if beta <= alpha:
                break
        return melhor
    else:
        melhor = 10000
        for traco in tracos:
            fechadas = estado.aplicar_traco(traco, -1)
            if fechadas > 0:
                # Adversário fecha caixa → mantém turno
                valor = minimax(
                    estado, profundidade - 1, alpha, beta, False,
                    caixas_ia, caixas_humano + fechadas
                )
            else:
                valor = minimax(
                    estado, profundidade - 1, alpha, beta, True,
                    caixas_ia, caixas_humano
                )
            estado.desfazer_traco(traco)
            melhor = min(melhor, valor)
            beta = min(beta, melhor)
            if beta <= alpha:
                break
        return melhor


def _scores_de_todas_jogadas(estado: EstadoTabuleiro, profundidade: int) -> dict[str, int]:
    # Calcula o score Minimax para CADA traço disponível (não só o argmax).
    # Esta é a base do treino com soft targets (KLDivergence) — em vez de jogar
    # fora a informação dos empates e quase-empates, o gerador grava o vetor
    # inteiro de Q-values e a CNN aprende a distribuição.
    tracos = estado.tracos_disponiveis()
    scores: dict[str, int] = {}
    for traco in tracos:
        fechadas = estado.aplicar_traco(traco, 1)
        if fechadas > 0:
            valor = minimax(estado, profundidade - 1, -10001, 10001, True, fechadas, 0)
        else:
            valor = minimax(estado, profundidade - 1, -10001, 10001, False, 0, 0)
        estado.desfazer_traco(traco)
        scores[traco] = valor
    return scores


def melhor_jogada(estado: EstadoTabuleiro, profundidade: int = 7) -> str:
    """Retorna o label do traço ótimo para o jogador maximizador."""
    import random
    if not estado.tracos_disponiveis():
        raise ValueError("Nenhum traço disponível.")
    scores = _scores_de_todas_jogadas(estado, profundidade)
    melhor_valor = max(scores.values())
    melhores = [t for t, v in scores.items() if v == melhor_valor]
    return random.choice(melhores)


def melhor_jogada_com_scores(
    estado: EstadoTabuleiro, profundidade: int = 7
) -> tuple[str, dict[str, int]]:
    """Igual a `melhor_jogada`, mas devolve também o dicionário {label: score}
    com o Q-value de TODAS as jogadas disponíveis. Custo idêntico ao argmax."""
    import random
    if not estado.tracos_disponiveis():
        raise ValueError("Nenhum traço disponível.")
    scores = _scores_de_todas_jogadas(estado, profundidade)
    melhor_valor = max(scores.values())
    melhores = [t for t, v in scores.items() if v == melhor_valor]
    return random.choice(melhores), scores
