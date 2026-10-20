"""O contrato do Quatro em Linha, LIDO DO ESPELHO em tempo de execução (T104).

═══════════════════════════════════════════════════════════════════════════
POR QUE LER, E NÃO REPETIR OS NÚMEROS AQUI
═══════════════════════════════════════════════════════════════════════════

O contrato (`ia/jogos/jogo_quatro/contrato/contrato_quatro.json`) é a única
declaração de cada modalidade - as dimensões do tabuleiro, os tipos de lance - e
dos números de cada personagem (teto de nós, ε, o que ele "percebe", a abertura
do Magno). O app lê a cópia dele dos assets; o executável do servidor de lances
o recebe por `--contrato`; e este módulo o lê do espelho.

Repetir `largura=7` ou `teto_de_nos=8170` aqui criaria uma quarta cópia dos
mesmos números, e a divergência não daria erro: o job calibraria o desafio contra
um adversário ligeiramente diferente do que a pessoa enfrenta.

⚠️ **Modalidade é DADO.** Este módulo não conhece nenhuma pelo nome: quem
escolhe a modalidade é quem chama, e o que o contrato não declara é recusado.
(O cadeado da T108 reprova o nome da modalidade de hoje escrito entre aspas em
`motores/quatro/`.)

═══════════════════════════════════════════════════════════════════════════
DE ONDE O CONTRATO É LIDO
═══════════════════════════════════════════════════════════════════════════

De dentro do espelho, e não de `../ia`: o Railway constrói a imagem a partir do
repositório do backend, e o que não estiver lá dentro não existe na nuvem.
"""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from motores.nucleo.papeis import NivelDeMotor

# `parents[2]` sobe de `motores/quatro/este_arquivo.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"

CAMINHO_DO_CONTRATO = (
    ESPELHO / "jogos" / "jogo_quatro" / "contrato" / "contrato_quatro.json"
)
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

#: Os arquivos do espelho que, mudando, mudam **como o motor joga**: o pacote
#: Dart inteiro (`lib/`, `bin/`, `pubspec.yaml`) e o contrato, que traz os
#: números de cada personagem. É deles que sai a versão carimbada.
PREFIXO_DO_MOTOR = "jogos/jogo_quatro/"

#: A chave do contrato para cada degrau do hub.
#:
#: ⚠️ O contrato do Quatro chama os níveis pelo **personagem** (é o que o app
#: mostra e o que a escada mediu), e o degrau do hub se chama pelo **nível**: o
#: 4º degrau é o Sagaz, e quem o joga é o Magno. A correspondência é do hub
#: inteiro (Cacau · Pita · Tex · Magno), e não deste jogo; ela mora aqui só
#: porque é aqui que as duas pontas se encontram.
PERSONAGEM_DO_NIVEL: Mapping[NivelDeMotor, str] = MappingProxyType(
    {
        NivelDeMotor.CACAU: "cacau",
        NivelDeMotor.PITA: "pita",
        NivelDeMotor.TEX: "tex",
        NivelDeMotor.SAGAZ: "magno",
    }
)

#: As três situações que um personagem pode perceber ou deixar passar
#: (`politica_dificuldade_quatro.dart`, `filtrosConhecidosQuatro`).
SITUACOES_DO_PERCEBE = ("vencer", "bloquear", "nao_jogar_sob_ameaca")


class ModalidadeDesconhecida(KeyError):
    """O contrato não declara a modalidade pedida.

    É `KeyError` porque é exatamente isso: uma chave que não existe no
    dicionário de modalidades. ⚠️ Falhar alto é o comportamento certo; cair numa
    modalidade padrão faria o job gerar o desafio de um tabuleiro que ninguém
    pediu.
    """


class ContratoQuatroInvalido(ValueError):
    """A modalidade existe, mas o conteúdo dela não serve para jogar.

    O caso que motivou a classe é o **marcador `teto_de_nos: 0`**: é como o
    contrato diz "este nível ainda não foi medido". Um nível sem medição não
    joga, nem no app (`carregarModalidade` recusa) nem aqui.
    """


@dataclass(frozen=True, slots=True)
class DimensoesQuatro:
    """O tamanho do tabuleiro e quantas peças em linha vencem.

    `frozen=True` deixa o objeto imutável, e `slots=True` o faz ocupar menos
    memória (sem o dicionário interno de atributos).
    """

    largura: int
    altura: int
    alinhar: int


@dataclass(frozen=True, slots=True)
class ParametrosDoPersonagemQuatro:
    """Os números de um personagem numa modalidade, como o contrato os declara.

    São exatamente os campos do `PedidoDeLanceQuatro` que o executável recebe
    (`contracts/motor-quatro.md` §3), e por isso `para_pedido` os entrega com os
    nomes de lá.

    Atributos:
        personagem: `cacau` · `pita` · `tex` · `magno`.
        teto_de_nos: o orçamento da busca. ⚠️ É ele, e não o tempo, que define o
            nível: o mesmo teto joga igual em qualquer máquina.
        epsilon: a chance de o personagem jogar um lance qualquer de propósito.
        percebe: a chance (0 a 1) de perceber cada situação.
        abertura_do_magno: as chances de cada coluna (1-based) no 1º lance, só
            para o Magno; `None` para os outros.
    """

    personagem: str
    teto_de_nos: int
    epsilon: float
    percebe: Mapping[str, float]
    abertura_do_magno: Mapping[int, float] | None

    def para_pedido(self) -> dict:
        """Os campos do pedido ao executável, com os nomes do contrato §3.

        ⚠️ A abertura vai com a coluna como TEXTO (`"4"`), porque em JSON a
        chave de objeto é sempre texto; o executável a devolve a inteiro.
        """
        return {
            "tetoDeNos": self.teto_de_nos,
            "epsilon": self.epsilon,
            "percebe": dict(self.percebe),
            "aberturaDoMagno": (
                None
                if self.abertura_do_magno is None
                else {str(c): p for c, p in self.abertura_do_magno.items()}
            ),
        }


@functools.lru_cache(maxsize=1)
def _bytes_do_contrato() -> bytes:
    """Os bytes do contrato, lidos uma vez.

    ⚠️ O cache torna o contrato **imutável durante a execução**: um job que o
    relesse no meio poderia medir metade dos candidatos com uma régua e metade
    com outra.
    """
    if not CAMINHO_DO_CONTRATO.exists():
        raise FileNotFoundError(
            f"contrato do Quatro em Linha ausente em {CAMINHO_DO_CONTRATO}.\n"
            "Ele viaja dentro do espelho do laboratório. Rode, na máquina do "
            "dono:\n  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    return CAMINHO_DO_CONTRATO.read_bytes()


def carregar_contrato() -> dict:
    """O contrato decodificado. Um dicionário novo a cada chamada.

    ⛔ Não devolve um objeto compartilhado: quem o recebe poderia alterá-lo, e a
    alteração apareceria para todo mundo que perguntasse depois.
    """
    return json.loads(_bytes_do_contrato().decode("utf-8"))


def sha256_do_contrato() -> str:
    """O SHA-256 dos BYTES do contrato do espelho.

    É o número que o executável anuncia na abertura (`sha256_do_contrato`), e o
    jogador recusa a conversa se os dois divergirem: um executável apontado para
    um contrato de outra versão jogaria outro tabuleiro.
    """
    return hashlib.sha256(_bytes_do_contrato()).hexdigest()


def modalidades_declaradas() -> tuple[str, ...]:
    """As modalidades que o contrato declara, na ordem em que ele as lista."""
    return tuple(carregar_contrato()["por_modalidade"])


def _entrada(modalidade: str) -> dict:
    """A entrada da [modalidade] no contrato, ou a recusa."""
    por_modalidade = carregar_contrato()["por_modalidade"]
    if modalidade not in por_modalidade:
        raise ModalidadeDesconhecida(
            f"o contrato do Quatro em Linha não declara a modalidade "
            f"{modalidade!r}. Declara: {', '.join(por_modalidade)}."
        )
    return por_modalidade[modalidade]


def dimensoes(modalidade: str) -> DimensoesQuatro:
    """As dimensões do tabuleiro da [modalidade].

    Raises:
        ModalidadeDesconhecida: o contrato não a declara.
        ContratoQuatroInvalido: alguma dimensão não é um inteiro positivo.
    """
    entrada = _entrada(modalidade)
    valores = {}
    for campo in ("largura", "altura", "alinhar"):
        valor = entrada.get(campo)
        # `bool` é subclasse de `int` em Python: `True` passaria por inteiro.
        if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
            raise ContratoQuatroInvalido(
                f"por_modalidade.{modalidade}.{campo} tem de ser inteiro "
                f"positivo (veio {valor!r})."
            )
        valores[campo] = valor
    return DimensoesQuatro(**valores)


def tipos_de_lance(modalidade: str) -> Mapping[str, str]:
    """As letras de lance da [modalidade] (`{"s": "soltar"}`), só para leitura."""
    return MappingProxyType(dict(_entrada(modalidade)["tipos_de_lance"]))


def niveis_disponiveis(modalidade: str) -> tuple[str, ...]:
    """Os personagens que a [modalidade] oferece, do mais fraco ao mais forte.

    ⚠️ Uma modalidade sem a garantia de quase perfeição sai com três (sem o
    Magno): o nível Sagaz é reservado ao jogo medido.
    """
    return tuple(_entrada(modalidade)["niveis_disponiveis"])


def parametros_do_personagem(
    modalidade: str, nivel: NivelDeMotor
) -> ParametrosDoPersonagemQuatro:
    """Os números com que o personagem do [nivel] joga a [modalidade].

    Raises:
        ModalidadeDesconhecida: o contrato não declara a modalidade.
        ContratoQuatroInvalido: a modalidade não oferece esse nível, o nível
            traz o marcador `teto_de_nos: 0` (ainda não medido), ou um número
            está fora do lugar. ⚠️ Falhar alto é o comportamento certo: cair num
            padrão faria o job calibrar o Magno com o orçamento da Cacau e
            gravar "sagaz" no banco.
    """
    entrada = _entrada(modalidade)
    personagem = PERSONAGEM_DO_NIVEL[nivel]
    caminho = f"por_modalidade.{modalidade}.niveis.{personagem}"
    if personagem not in entrada["niveis_disponiveis"]:
        raise ContratoQuatroInvalido(
            f"a modalidade {modalidade!r} não oferece o nível {nivel.value!r} "
            f"({personagem}). Oferece: {', '.join(entrada['niveis_disponiveis'])}."
        )
    bruto = entrada["niveis"].get(personagem)
    if bruto is None:
        raise ContratoQuatroInvalido(f"falta {caminho}.")

    teto = bruto.get("teto_de_nos")
    if not isinstance(teto, int) or isinstance(teto, bool) or teto <= 0:
        raise ContratoQuatroInvalido(
            f"{caminho}.teto_de_nos = {teto!r}: o zero é o marcador de "
            "\"ainda não medido\", e um nível sem medição não joga."
        )

    epsilon = float(bruto["epsilon"])
    if not 0 <= epsilon <= 1:
        raise ContratoQuatroInvalido(f"{caminho}.epsilon fora de 0 a 1.")

    percebe = {chave: float(valor) for chave, valor in bruto["percebe"].items()}
    if set(percebe) != set(SITUACOES_DO_PERCEBE):
        raise ContratoQuatroInvalido(
            f"{caminho}.percebe tem de trazer exatamente "
            f"{', '.join(SITUACOES_DO_PERCEBE)} (traz {', '.join(percebe)})."
        )
    if any(not 0 <= p <= 1 for p in percebe.values()):
        raise ContratoQuatroInvalido(f"{caminho}.percebe com chance fora de 0 a 1.")

    abertura = None
    if nivel is NivelDeMotor.SAGAZ:
        # As chaves vêm como texto ("4"); a coluna é inteiro, de 1 à largura.
        abertura = {
            int(coluna): float(p)
            for coluna, p in entrada["abertura_do_magno"].items()
        }

    return ParametrosDoPersonagemQuatro(
        personagem=personagem,
        teto_de_nos=teto,
        epsilon=epsilon,
        percebe=MappingProxyType(percebe),
        abertura_do_magno=(
            None if abertura is None else MappingProxyType(abertura)
        ),
    )


def arquivos_do_motor() -> tuple[dict[str, str], ...]:
    """Os arquivos do espelho que DEFINEM este motor, com o SHA-256 de cada um.

    Ordenada pelo caminho, como a das damas (`contrato_damas.arquivos_do_motor`),
    para a dimensão `desafio.tb904_motor` tornar o resumo decifrável com a
    MESMA lista de que ele saiu.
    """
    manifesto = json.loads(CAMINHO_DO_MANIFESTO.read_text(encoding="utf-8"))
    return tuple(
        {"caminho": item["caminho"], "sha256": item["sha256"]}
        for item in sorted(
            (
                item
                for item in manifesto["arquivos"]
                if item["caminho"].startswith(PREFIXO_DO_MOTOR)
            ),
            key=lambda item: item["caminho"],
        )
    )


def versao_do_motor() -> str:
    """O identificador do motor que jogou: `quatro-dart-<8 hex>`.

    Sai dos hashes do espelho, e não de um número escrito à mão, que envelhece
    calado. ⚠️ A conta é a das damas e a do Pontinhos (os hashes **ordenados
    entre si**, concatenados), para os três carimbos se lerem do mesmo jeito.
    """
    hashes = sorted(arquivo["sha256"] for arquivo in arquivos_do_motor())
    digesto = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return f"quatro-dart-{digesto[:8]}"


def versao_do_contrato() -> str:
    """A versão declarada dentro do contrato - sobe quando a FORMA dele muda."""
    return carregar_contrato()["versao"]
