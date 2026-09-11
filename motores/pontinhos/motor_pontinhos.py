"""O motor do Pontinhos: a MESMA CNN do aplicativo, no servidor (RF-DES-018b).

═══════════════════════════════════════════════════════════════════════════
O PIPELINE, DE PONTA A PONTA
═══════════════════════════════════════════════════════════════════════════

    matriz da partida {-1, 0, 1, 8}
      → partida_para_dataset  → {0, 1, 8, 9}      (as regras do contrato)
      → extrair_canais        → (4, 3, 12) em {0, 1}   (o código do laboratório)
      → tensor (1, 4, 3, 12) float32
      → ai-edge-litert
      → 31 neurônios, um por traço possível

É exatamente o que `oraculo_cnn_io.dart` faz no aparelho, com a mesma `.tflite` e
o mesmo `mapeamento_pequeno.json` — que viajam no espelho justamente para isso.

⚠️ **RF-DES-018b não diz "um modelo equivalente": diz o mesmo.** Um `.tflite`
diferente, ainda que treinado igual, daria outro jogador — e o desafio calibrado
contra ele prometeria uma dificuldade que ninguém encontra.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO NÃO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Não escolhe nível.** Este é o motor cru: ele ranqueia os traços disponíveis
pela rede e devolve o de maior probabilidade. Quem transforma isso em Cacau, Pita,
Tex e Magno é `politica.py` — sem ela, os quatro níveis seriam o mesmo jogador.

⛔ **Não reimplementa a extração dos 12 canais.** Ela tem BFS no grafo dual das
caixas, e é o tipo de código que uma segunda escrita erraria em silêncio.

═══════════════════════════════════════════════════════════════════════════
O ESTADO É A SEQUÊNCIA DE LANCES
═══════════════════════════════════════════════════════════════════════════

Nas damas o estado se escreve em FEN; aqui, em **sequência de lances** — é o que
`co_formato_posicao` distingue no `data-model.md`. E é a forma natural: no
Pontinhos o tabuleiro começa sempre vazio, e o turno extra depois de fechar caixa
faz "de quem é a vez" depender da história, não da posição.
"""

from __future__ import annotations

import functools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from motores.nucleo.carimbo import Carimbo
from motores.nucleo.papeis import LimiteDeBusca, NivelDeMotor, Veredito

# `parents[2]` sobe de `motores/pontinhos/este_arquivo.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"

NOME_DO_MODELO = (
    "pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite"
)
CAMINHO_DO_MODELO = ESPELHO / "modelos" / NOME_DO_MODELO
CAMINHO_DO_MAPEAMENTO = ESPELHO / "ia_mappings" / "mapeamento_pequeno.json"
CAMINHO_DO_CONTRATO = ESPELHO / "contrato_codificacao_pontinhos.json"
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

# Só o tabuleiro pequeno existe como `.tflite` (RF-DES-018d). Os números saem do
# contrato de codificação, e são conferidos contra ele na carga.
TAMANHO = "pequeno"
LINHAS, COLUNAS = 4, 3
CANAIS = 12

# ── A ponte para o espelho ──────────────────────────────────────────────────
#
# Mesmo motivo do motor de damas: o código do laboratório se importa por caminho
# absoluto, e ⛔ editar esses imports quebraria a cópia byte-idêntica.
if str(ESPELHO) not in sys.path:
    sys.path.insert(0, str(ESPELHO))

from jogos.jogo_pontinhos.motor.analisador_estrutural_pontinhos import (  # noqa: E402
    extrair_canais,
)
from jogos.jogo_pontinhos.motor.tabuleiro_pontinhos import (  # noqa: E402
    EstadoTabuleiro,
)

MOTIVO_TABULEIRO_CHEIO = "tabuleiro_cheio"
"""O único fim de partida do Pontinhos: acabaram os traços.

⚠️ **Toda partida de Pontinhos chega a estado terminal**, e isso não é uma
promessa: é aritmética. Cada lance ocupa um traço, os traços são finitos, e
nenhum lance os devolve.
"""


def partida_para_dataset(matriz: np.ndarray) -> np.ndarray:
    """Converte a matriz da PARTIDA `{-1,0,1,8}` para a do DATASET `{0,1,8,9}`.

    ⚠️ **Por que esta função existe aqui, se nada mais é reimplementado.** Ela
    aplica as três regras que o próprio `contrato_codificacao_pontinhos.json`
    declara em `contexto_3_partidas_ao_vivo` — ponto fixo vira 8, caixa fechada
    vira 1, traço ocupado vira 9 — e são doze linhas sem ramificação. A peça que
    ⛔ **não** se reescreve é `extrair_canais`, com a BFS no grafo dual.

    As outras duas cópias destas mesmas regras são
    `partidaParaDataset` em `encoding_cnn.dart` (o aplicativo) e
    `_partida_para_dataset` no simulador do laboratório. As três citam o
    contrato, e `test_motor_pontinhos.py` compara esta com a do laboratório
    quando ele está no disco.

    ⚠️ **A matriz recebida NUNCA é alterada.** Normalizar por cima da matriz da
    partida corromperia o estado do jogo — o marcador do jogador 2 viraria do
    jogador 1, e a próxima jogada sairia inválida. O contrato traz esse aviso em
    caixa alta, e ele veio de um defeito real.
    """
    saida = np.zeros_like(matriz, dtype=np.int8)
    altura, largura = matriz.shape
    for r in range(altura):
        for c in range(largura):
            if r % 2 == 0 and c % 2 == 0:
                saida[r, c] = 8  # ponto fixo da grade
            elif r % 2 == 1 and c % 2 == 1:
                saida[r, c] = 1 if matriz[r, c] != 0 else 0  # caixa fechada
            else:
                saida[r, c] = 9 if matriz[r, c] != 0 else 0  # traço ocupado
    return saida


@dataclass(frozen=True)
class EstadoPontinhos:
    """Uma partida de Pontinhos como **valor**: a sequência de traços marcados.

    Atributos:
        lances: os rótulos dos traços, na ordem em que foram marcados
            (`H_0_1`, `V_1_0`, …). O tabuleiro começa vazio, então a sequência
            descreve a partida inteira.

    ⚠️ **De quem é a vez não é um campo**, é derivado: quem fecha caixa joga de
    novo. Guardar a vez ao lado da sequência criaria duas fontes para o mesmo
    fato, e a que estivesse errada mandaria.
    """

    lances: tuple[str, ...] = ()

    # ⚠️ Congelado com cache: `frozen` proíbe trocar o campo, não mexer no
    # dicionário que ele aponta. `compare=False` mantém dois estados iguais
    # comparando iguais mesmo que só um já tenha reproduzido a partida.
    _cache: dict = field(
        default_factory=dict, compare=False, repr=False, hash=False
    )

    @property
    def _partida(self) -> tuple[EstadoTabuleiro, int, dict[int, int]]:
        """Reproduz a partida e devolve `(tabuleiro, vez_de, caixas por jogador)`.

        ⚠️ **O turno extra é a regra que torna isto necessário.** Quem fecha uma
        caixa joga de novo; então, para saber de quem é a vez no lance N, é
        preciso ter passado pelos N-1 anteriores. Não há atalho a partir da
        posição — e é por isso que o estado é a sequência.

        Raises:
            ValueError: se algum lance repetir um traço já ocupado. Um estado
                impossível não se constrói em silêncio.
        """
        if "partida" in self._cache:
            return self._cache["partida"]

        tabuleiro = EstadoTabuleiro(LINHAS, COLUNAS)
        vez = 1  # o jogador 1 abre, como no aplicativo
        placar = {1: 0, -1: 0}

        for ordem, lance in enumerate(self.lances, start=1):
            if lance not in tabuleiro.tracos_disponiveis():
                raise ValueError(
                    f"lance {ordem} da sequência ({lance!r}) não está disponível. "
                    f"Disponíveis: {', '.join(tabuleiro.tracos_disponiveis())}"
                )
            fechadas = tabuleiro.aplicar_traco(lance, jogador=vez)
            placar[vez] += fechadas
            # Fechou caixa, joga de novo. É a regra que faz o placar e a vez
            # dependerem da ordem, e não só do desenho final do tabuleiro.
            if fechadas == 0:
                vez = -vez

        self._cache["partida"] = (tabuleiro, vez, placar)
        return self._cache["partida"]

    @property
    def tabuleiro(self) -> EstadoTabuleiro:
        """O tabuleiro atual. ⚠️ É o objeto interno — não o altere."""
        return self._partida[0]

    @property
    def vez_de(self) -> int:
        """`+1` ou `-1`, na convenção do log de partidas."""
        return self._partida[1]

    @property
    def placar(self) -> dict[int, int]:
        """Quantas caixas cada jogador fechou."""
        return dict(self._partida[2])

    def com_lance(self, lance: str) -> "EstadoPontinhos":
        """O estado NOVO depois deste traço. O de origem fica intacto."""
        return EstadoPontinhos(lances=self.lances + (lance,))


@functools.lru_cache(maxsize=1)
def _interpretador():
    """Abre o `.tflite` do espelho uma vez por processo.

    `lru_cache` porque abrir e alocar tensores custa dezenas de milissegundos, e
    o job faz milhares de consultas por calibração.

    ⚠️ **Confere a forma do modelo na abertura.** Sem isso, um modelo trocado por
    engano — o médio, o grande — rodaria e devolveria números plausíveis, e o
    desafio sairia calibrado contra um adversário de outro tabuleiro.
    """
    from ai_edge_litert.interpreter import Interpreter  # type: ignore

    if not CAMINHO_DO_MODELO.exists():
        raise FileNotFoundError(
            f"a CNN do Pontinhos não está no espelho ({CAMINHO_DO_MODELO}).\n"
            "Rode, na máquina do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )

    interp = Interpreter(model_path=str(CAMINHO_DO_MODELO))
    interp.allocate_tensors()

    entrada = interp.get_input_details()[0]
    forma = tuple(int(x) for x in entrada["shape"])
    esperada = (1, LINHAS, COLUNAS, CANAIS)
    if forma != esperada:
        raise RuntimeError(
            f"a CNN do espelho pede entrada {forma}, e o tabuleiro "
            f"{TAMANHO} monta {esperada}. Modelo trocado?"
        )
    return interp


@functools.lru_cache(maxsize=1)
def _rotulos() -> dict[str, int]:
    """Rótulo do traço → índice do neurônio de saída.

    ⚠️ **A ordem do mapeamento é a varredura canônica da matriz**, que intercala
    `H_` e `V_`. A ordem alfabética agruparia todos os `H_` antes dos `V_` e
    inutilizaria 28 das 31 predições no tabuleiro pequeno — já aconteceu, e está
    registrado no contrato como erro histórico evitado.
    """
    bruto = json.loads(CAMINHO_DO_MAPEAMENTO.read_text(encoding="utf-8"))
    return {rotulo: int(indice) for indice, rotulo in bruto.items()}


@functools.lru_cache(maxsize=1)
def contrato_de_codificacao() -> dict:
    """O contrato de codificação, lido do espelho."""
    return json.loads(CAMINHO_DO_CONTRATO.read_text(encoding="utf-8"))


#: Os prefixos do manifesto que definem o jogador do Pontinhos.
#:
#: ⚠️ **São TRÊS porque o jogador é três coisas**: o código que codifica o
#: tabuleiro (`jogos/jogo_pontinhos/`), o modelo que decide (`modelos/`) e o
#: mapeamento que traduz o neurônio de saída em traço (`ia_mappings/`). Trocar
#: qualquer um dos três muda o lance escolhido — e é por isso que os três entram
#: no resumo.
#:
#: ⛔ **Era uma variável local dentro de `versao_do_motor`**, e subiu para cá em
#: 11/09/2026 (T049e): `desafio.tb904_motor` precisa listar exatamente estes
#: arquivos, e um segundo filtro escrito lá divergiria deste no dia em que um
#: quarto prefixo entrasse.
PREFIXOS_DO_MOTOR = ("jogos/jogo_pontinhos/", "modelos/", "ia_mappings/")


def arquivos_do_motor() -> tuple[dict[str, str], ...]:
    """Os arquivos do espelho que DEFINEM este jogador, com o SHA-256 de cada um.

    Returns:
        Uma tupla de `{"caminho", "sha256"}`, **ordenada pelo caminho**.

    Ver a gêmea em `motores/damas/contrato_damas.py`: as duas existem para que a
    lista que vai a `desafio.tb904_motor` seja a **mesma** que o resumo de 8
    dígitos resumiu, e não uma cópia que se parece com ela.
    """
    manifesto = json.loads(CAMINHO_DO_MANIFESTO.read_text(encoding="utf-8"))
    return tuple(
        {"caminho": item["caminho"], "sha256": item["sha256"]}
        for item in sorted(
            (
                item
                for item in manifesto["arquivos"]
                if item["caminho"].startswith(PREFIXOS_DO_MOTOR)
            ),
            key=lambda item: item["caminho"],
        )
    )


@functools.lru_cache(maxsize=1)
def versao_do_motor() -> str:
    """Identificador do motor do Pontinhos, para o carimbo (RF-DES-164).

    ⚠️ Como no motor de damas, sai dos **hashes do espelho** e não de um número
    escrito à mão: o que define este jogador é a `.tflite` mais o código de
    codificação, e os dois estão no manifesto. Trocar o modelo e esquecer de
    subir a versão deixaria medições novas indistinguíveis das velhas no banco.
    """
    import hashlib

    # ⚠️ **A ordem é a dos HASHES, e não a dos caminhos** — ver a nota gêmea em
    # `contrato_damas.versao_do_motor`: mudá-la daria outro resumo sem que o
    # motor tivesse mudado.
    hashes = sorted(arquivo["sha256"] for arquivo in arquivos_do_motor())
    digesto = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return f"pontinhos-py-{digesto[:8]}"


class MotorPontinhos:
    """Veste a CNN com os papéis da camada.

    ⚠️ **Este é o motor cru.** `escolher_lance` devolve o traço de maior
    probabilidade entre os disponíveis — o comportamento do Magno. Os outros três
    níveis passam pela política (`politica.py`), que é o que os distingue.
    """

    co_jogo = "pontinhos"

    # ── Papel ÁRBITRO ───────────────────────────────────────────────────────

    def lances_legais(self, estado: EstadoPontinhos) -> list[str]:
        """Os traços ainda livres, na ordem canônica da varredura da matriz.

        A ordem é a mesma do mapeamento de rótulos, e importa: é ela que o
        gerador usa como desempate reprodutível.
        """
        return estado.tabuleiro.tracos_disponiveis()

    def aplicar(self, estado: EstadoPontinhos, lance: str) -> EstadoPontinhos:
        """Marca o traço e devolve o estado NOVO.

        Raises:
            ValueError: se o traço já estiver ocupado ou não existir.
        """
        novo = estado.com_lance(lance)
        # Forçar a reconstrução aqui faz a recusa acontecer agora, com a mensagem
        # que nomeia o lance, e não três chamadas adiante.
        _ = novo.tabuleiro
        return novo

    def veredito(self, estado: EstadoPontinhos) -> Veredito:
        """Acabou quando não há mais traço livre. Vence quem fechou mais caixas.

        ⚠️ Não há empate por histórico aqui — nem histórico. O Pontinhos empata
        por **placar igual**, e só quando o tabuleiro enche.
        """
        tabuleiro, _, placar = estado._partida
        if tabuleiro.tracos_disponiveis():
            return Veredito(acabou=False)

        if placar[1] > placar[-1]:
            vencedor = 1
        elif placar[-1] > placar[1]:
            vencedor = -1
        else:
            vencedor = 0
        return Veredito(
            acabou=True, co_motivo=MOTIVO_TABULEIRO_CHEIO, vencedor=vencedor
        )

    # ── A rede ──────────────────────────────────────────────────────────────

    def ranquear(self, estado: EstadoPontinhos) -> list[tuple[str, float]]:
        """Os traços disponíveis com a probabilidade da rede, do maior ao menor.

        As probabilidades são **renormalizadas sobre os disponíveis**, para que
        somem 1 — é sobre essa distribuição que a política de cada nível decide,
        e é o que `oraculo_cnn_io.dart` faz no aparelho.

        Raises:
            ValueError: se a partida já acabou.
        """
        disponiveis = self.lances_legais(estado)
        if not disponiveis:
            raise ValueError("a partida já acabou: não há traço a ranquear.")

        probabilidades = self._inferir(estado)
        rotulos = _rotulos()

        def prob_de(rotulo: str) -> float:
            indice = rotulos.get(rotulo)
            if indice is None or indice >= len(probabilidades):
                return 0.0
            return float(probabilidades[indice])

        soma = sum(prob_de(r) for r in disponiveis)
        if soma > 0:
            ranqueados = [(r, prob_de(r) / soma) for r in disponiveis]
        else:
            # A rede não pôs peso em nenhum traço livre. Distribuir igualmente é
            # o que o aplicativo faz, e mantém a soma em 1 — devolver zeros faria
            # a política sortear sobre uma distribuição vazia.
            uniforme = 1.0 / len(disponiveis)
            ranqueados = [(r, uniforme) for r in disponiveis]

        # Ordem estável: pela probabilidade, e pelo rótulo em caso de empate. Sem
        # o segundo critério, dois traços com a mesma nota trocariam de lugar
        # entre execuções, e a calibração deixaria de ser reprodutível.
        ranqueados.sort(key=lambda par: (-par[1], par[0]))
        return ranqueados

    def _inferir(self, estado: EstadoPontinhos) -> np.ndarray:
        """Roda a CNN e devolve os 31 neurônios crus (a softmax do modelo)."""
        matriz_dataset = partida_para_dataset(estado.tabuleiro.matriz)
        canais = extrair_canais(matriz_dataset)  # (4, 3, 12) em {0, 1}

        # `[None]` acrescenta a dimensão de lote: (4,3,12) → (1,4,3,12).
        tensor = np.asarray(canais, dtype=np.float32)[None]

        interp = _interpretador()
        interp.set_tensor(interp.get_input_details()[0]["index"], tensor)
        interp.invoke()
        return interp.get_tensor(interp.get_output_details()[0]["index"])[0]

    # ── Papel JOGADOR ───────────────────────────────────────────────────────

    def escolher_lance(
        self,
        estado: EstadoPontinhos,
        nivel: NivelDeMotor = NivelDeMotor.SAGAZ,
        limite: LimiteDeBusca | None = None,
    ) -> str:
        """O traço de maior probabilidade entre os disponíveis.

        ⚠️ **Ignora o nível de propósito, e isto é temporário.** Este é o motor
        cru: a rede não tem degraus. Quem os produz é `politica.py` (T016), que
        entra por cima desta chamada. Enquanto ela não existir, todo nível joga
        como o Magno — e é melhor que isso seja óbvio no código do que disfarçado
        por um parâmetro que não faz nada.

        ⚠️ O `limite` é anotado, não imposto: a CNN é uma única inferência de
        custo fixo, sem árvore a podar. Contar o nó existe para que o resumo
        gravado no banco distinga "jogou mal" de "não teve tempo".
        """
        ranqueados = self.ranquear(estado)
        if limite is not None and hasattr(limite, "contar_no"):
            limite.contar_no(1)
        return ranqueados[0][0]

    # ── Papel TRADUTOR DE ESTADO ────────────────────────────────────────────

    def para_dado(self, estado: EstadoPontinhos) -> dict[str, Any]:
        """O estado na forma que o `data-model.md` grava.

        `co_formato_posicao` é **`sequencia_lances`** aqui — as damas usam `fen`.
        """
        return {
            "co_jogo": self.co_jogo,
            "co_modalidade": None,  # o Pontinhos não tem modalidade
            "co_formato_posicao": "sequencia_lances",
            "co_tamanho_tabuleiro": TAMANHO,
            "sequencia_lances": list(estado.lances),
            "vez_de": estado.vez_de,
            "placar": {"1": estado.placar[1], "-1": estado.placar[-1]},
        }

    def de_dado(self, dado: dict[str, Any]) -> EstadoPontinhos:
        """Reconstrói o estado a partir de uma linha do banco.

        ⚠️ Recusa o formato das damas: um FEN chegando aqui não produziria uma
        partida de Pontinhos plausível, produziria um erro obscuro lá dentro.
        """
        formato = dado.get("co_formato_posicao")
        if formato != "sequencia_lances":
            raise ValueError(
                f"o Pontinhos grava a posição em 'sequencia_lances', veio "
                f"{formato!r}. O 'fen' é o formato das damas."
            )
        return EstadoPontinhos(lances=tuple(dado.get("sequencia_lances", ())))

    # ── O carimbo ───────────────────────────────────────────────────────────

    def carimbo(self, nivel: NivelDeMotor, co_versao_perfil: str) -> Carimbo:
        """Quem produziu, com que régua, em que nível (RF-DES-164/146).

        ⚠️ `co_modalidade` fica **nulo**: o Pontinhos não tem regulamento
        alternativo, e nulo é diferente de string vazia — "não se aplica" não é
        "não informado".
        """
        return Carimbo(
            co_jogo=self.co_jogo,
            co_nivel=nivel,
            co_versao_motor=versao_do_motor(),
            co_versao_perfil=co_versao_perfil,
        )


def estado_inicial() -> EstadoPontinhos:
    """O tabuleiro vazio. No Pontinhos toda partida começa daqui."""
    return EstadoPontinhos()
