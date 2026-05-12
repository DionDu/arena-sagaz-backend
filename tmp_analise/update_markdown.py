import json
import re

nb_path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Arena_Sagaz_V7.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Cell 0: Introduction Markdown
if nb['cells'][0]['cell_type'] == 'markdown':
    new_intro = """# Arena Sagaz — Treinamento CNN (V7 Adaptativo & HighPerf)

Este notebook processa o revolucionário dataset **V7**, gerado sob o algoritmo **DAC (Diversidade Adaptativa em Cascata)** e *Scorado* com a engine de **Alta Performance (Bitboard 64-bits)**.

### O que mudou em relação às versões antigas (V4/V5/V6):
- **Adeus ao `generation_mode`:** A V7 não usa mais cotas artificiais nem modos de geração separados. A distribuição do dataset é uma curva de sino natural (emergente) extraída de 30 snapshots por partida.
- **Campos de Alta Fidelidade:** Os rótulos de treinamento agora usam `melhor_jogada` e os Q-values usam `score_melhor_jogada`, todos rigorosamente testados e livres de ruído (bugs de offset Alpha-Beta ou caixas pré-fechadas foram dizimados pela engine Bitboard do Databricks).
- **Novas Faixas de Jogo (0-11, 12-17, 18-23, 24-28, 29-31):** A avaliação do modelo agora estratifica e exibe métricas (Top-1, 3 e 5) respeitando as densidades reais de Abertura, 1ª/2ª Metade, Fase Quente e Final.
- **Filtro de Matrizes Duplicadas:** O parâmetro `UTILIZACAO_MATRIZES` garante que a rede treine sem o viés do estrangulamento.
- **Análise de Viés de Borda:** Relatório exclusivo para auditar se a CNN vicia em jogar nas quinas/bordas em comparação com o mestre Minimax.

> **Contrato de Codificação:** A normalização para o treinamento (`8` -> `0`, `9` -> `1`) segue invicta como dita o `contrato_codificacao_pontinhos.json`.
"""
    nb['cells'][0]['source'] = [line + '\n' for line in new_intro.splitlines()]

# Locate and update other markdown/comments
for cell in nb['cells']:
    if cell['cell_type'] == 'markdown':
        src = "".join(cell['source'])
        if "BoxNet V3-AutoPlay" in src:
            # Update the history table
            src = src.replace("| **BoxNet V3-AutoPlay** | **Auto-play** | **7** | **300k** | **?** | **?** | **?** | **?** | KLD | **Esta rodada** — dataset auto-play, estimativa: MM(p=3)~75-85% |",
                              "| **BoxNet V3-AutoPlay** | **Auto-play** | **7** | **300k** | **?** | **?** | **?** | **?** | KLD | Dataset antigo de auto-play. |\n| **BoxNet V3-DAC (V7)** | **DAC / Bitboard** | **7** | **500k** | **?** | **?** | **?** | **?** | KLD | **Esta rodada** — dataset imaculado emergente, sem viés de duplicatas. |")
            
            lines = [line if line.endswith('\n') else line + '\n' for line in src.splitlines()]
            if src and not src.endswith('\n'):
                lines[-1] = lines[-1].rstrip('\n')
            cell['source'] = lines

    elif cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        
        # Section 1.3b comments
        if "# Cada amostra recebe duas características intrínsecas ao estado do tabuleiro,\n# independentes do generation_mode:" in src:
            src = src.replace("# Cada amostra recebe duas características intrínsecas ao estado do tabuleiro,\n# independentes do generation_mode:",
                              "# Cada amostra recebe duas características intrínsecas ao estado do tabuleiro:")
        
        # Section 1.4 comments
        if "# O dataset foi gerado interrompendo partidas em momentos aleatórios entre\n# 15% e 85% de preenchimento." in src:
            new_comment = """# O dataset V7 foi gerado tirando 30 snapshots de cada partida completa (t=1..30).
# Estratificando pela fase do jogo, garantimos que treino, validação e teste preservem 
# a mesma curva de sino natural emergente de aberturas, meios e finais — o que casa com
# a forma como as métricas são reportadas depois e torna a avaliação honesta."""
            src = re.sub(r"# O dataset foi gerado interrompendo partidas em momentos aleatórios entre\n# 15% e 85% de preenchimento\..*?torna a avaliação mais honesta\.", new_comment, src, flags=re.DOTALL)
        
        if src != "".join(cell['source']):
            lines = [line if line.endswith('\n') else line + '\n' for line in src.splitlines()]
            if src and not src.endswith('\n'):
                lines[-1] = lines[-1].rstrip('\n')
            cell['source'] = lines

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("Textos Markdown atualizados com sucesso.")
