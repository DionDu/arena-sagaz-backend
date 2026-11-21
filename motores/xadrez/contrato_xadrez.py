"""O contrato do xadrez, LIDO DO ESPELHO em tempo de execução (spec 012, T062).

═══════════════════════════════════════════════════════════════════════════
POR QUE LER, E NÃO REPETIR OS NÚMEROS AQUI
═══════════════════════════════════════════════════════════════════════════

O contrato (`ia/jogos/jogo_xadrez/contrato/contrato_xadrez.json`) é a única
declaração de cada modalidade (a posição inicial, os fins, os relógios de
empate) e dos números de cada personagem (profundidade, teto de nós, o ruído, a
rede de tempo, o relógio), além de `magno_no_build`. O app lê a cópia dele dos
assets; o executável do servidor o recebe por `--contrato`; e este módulo o lê
do espelho. É o molde de `motores/quatro/contrato_quatro.py`.

⚠️ **O backend não passa estes números ao executável**: ele mesmo lê o contrato
que recebeu. Este módulo existe para o job SABER o que o executável sabe (que
níveis o build oferece, se o Magno existe, que relógio cada um tem) e para a
conferência da abertura (o SHA-256 que o executável anuncia).

⚠️ **Modalidade é DADO.** Este módulo não conhece nenhuma pelo nome: quem escolhe
a modalidade é quem chama, e o que o contrato não declara é recusado.

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
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from motores.nucleo.papeis import NivelDeMotor

# `parents[2]` sobe de `motores/xadrez/este_arquivo.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"
CAMINHO_DO_CONTRATO = (
    ESPELHO / "jogos" / "jogo_xadrez" / "contrato" / "contrato_xadrez.json"
)
#: O `Cargo.toml` do crate espelhado: é dele que sai a versão do motor, a mesma
#: que o executável anuncia na abertura (`versao`, `env!("CARGO_PKG_VERSION")`).
CAMINHO_DO_CARGO = ESPELHO / "jogos" / "jogo_xadrez" / "motor_rust" / "Cargo.toml"
#: O manifesto do espelho, com o SHA-256 de cada arquivo (o mesmo dos outros
#: jogos, `MANIFESTO_HASHES.json`).
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

#: Os arquivos do espelho que, mudando, mudam **o desafio que o job gera**: o
#: crate inteiro (os fontes, o `Cargo.toml`, o `Cargo.lock`, o `rust-toolchain`),
#: o contrato, com os números de cada personagem, e a base de posições de onde
#: o job sorteia. É deles que sai o carimbo do desafio (`versao_do_motor_no_espelho`),
#: com o prefixo da pasta do jogo, como no Quatro (`contrato_quatro.PREFIXO_DO_MOTOR`).
PREFIXO_DO_MOTOR = "jogos/jogo_xadrez/"

#: A chave do contrato para cada degrau do hub.
#:
#: ⚠️ O contrato chama os níveis pelo **personagem** (é o que o app mostra), e o
#: degrau do hub se chama pelo **nível**: o 4º degrau é o Sagaz, e quem o joga é
#: o Magno. É a mesma tabela de `contrato_quatro.PERSONAGEM_DO_NIVEL`; ela não
#: sobe para o núcleo porque o núcleo não sabe que o contrato de um jogo nomeia
#: os níveis assim.
PERSONAGEM_DO_NIVEL: Mapping[NivelDeMotor, str] = MappingProxyType(
    {
        NivelDeMotor.CACAU: "cacau",
        NivelDeMotor.PITA: "pita",
        NivelDeMotor.TEX: "tex",
        NivelDeMotor.SAGAZ: "magno",
    }
)

#: Os campos que todo nível do contrato traz (`contracts/motor-xadrez.md` §4).
CAMPOS_DO_NIVEL = (
    "profundidade_maxima",
    "teto_de_nos",
    "quiescencia",
    "margem_do_erro_cp",
    "chance_do_erro_milesimos",
    "chance_da_cegueira_milesimos",
    "rede_de_tempo_s",
    "relogio_s",
)


class ModalidadeDesconhecida(KeyError):
    """O contrato não declara a modalidade pedida.

    ⚠️ Falhar alto é o comportamento certo: cair numa modalidade padrão faria o
    job gerar o desafio de um jogo que ninguém pediu.
    """


class ContratoXadrezInvalido(ValueError):
    """A modalidade existe, mas o que se pediu dela não serve para jogar.

    O caso que mais importa: pedir o Magno a um contrato com
    `magno_no_build: false`. O app desse build não tem o Magno (RF-XDR-080), e
    um desafio contra ele seria um desafio contra ninguém.
    """


@dataclass(frozen=True, slots=True)
class ParametrosDoNivelXadrez:
    """Os números de um personagem numa modalidade, como o contrato os declara.

    `frozen=True` deixa o objeto imutável, e `slots=True` o faz ocupar menos
    memória (sem o dicionário interno de atributos).

    Atributos:
        personagem: `cacau` · `pita` · `tex` · `magno`.
        teto_de_nos: o orçamento da busca. ⚠️ É ele, e não o tempo, que define o
            nível: o mesmo teto joga igual em qualquer máquina.
        quiescencia: `nao` · `curta` · `sim`, como no contrato.
        chance_do_erro_milesimos, chance_da_cegueira_milesimos: as chances do
            ruído em milésimos (350 = 35%), para nenhum sorteio passar por ponto
            flutuante (R-09).
        rede_de_tempo_s: o limite de segurança em segundos, ou `None`.
        relogio_s: o relógio do lance da pessoa, ou `None` (sem relógio).
    """

    personagem: str
    profundidade_maxima: int
    teto_de_nos: int
    quiescencia: str
    margem_do_erro_cp: int
    chance_do_erro_milesimos: int
    chance_da_cegueira_milesimos: int
    rede_de_tempo_s: int | None
    relogio_s: int | None


@functools.lru_cache(maxsize=1)
def _bytes_do_contrato() -> bytes:
    """Os bytes do contrato, lidos uma vez.

    ⚠️ O cache torna o contrato **imutável durante a execução**: um job que o
    relesse no meio poderia medir metade dos candidatos com uma régua e metade
    com outra.
    """
    if not CAMINHO_DO_CONTRATO.exists():
        raise FileNotFoundError(
            f"contrato do xadrez ausente em {CAMINHO_DO_CONTRATO}.\n"
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
    um contrato de outra versão jogaria com outros números.
    """
    return hashlib.sha256(_bytes_do_contrato()).hexdigest()


def versao_do_contrato() -> str:
    """A versão declarada dentro do contrato (sobe quando o contrato muda)."""
    return carregar_contrato()["versao"]


def modalidades_declaradas() -> tuple[str, ...]:
    """As modalidades que o contrato declara, na ordem em que ele as lista."""
    return tuple(carregar_contrato()["por_modalidade"])


def magno_no_build() -> bool:
    """O build sai com o Magno? (RF-XDR-080, a decisão da T053.)

    ⚠️ Estritamente booleano: um `"false"` em texto seria verdadeiro em Python, e
    o job passaria a gerar desafios contra um Magno que o app não tem.
    """
    valor = carregar_contrato()["magno_no_build"]
    if not isinstance(valor, bool):
        raise ContratoXadrezInvalido(
            f"magno_no_build tem de ser true ou false, e veio {valor!r}."
        )
    return valor


def _entrada(modalidade: str) -> dict:
    """A entrada da [modalidade] no contrato, ou a recusa."""
    por_modalidade = carregar_contrato()["por_modalidade"]
    if modalidade not in por_modalidade:
        raise ModalidadeDesconhecida(
            f"o contrato do xadrez não declara a modalidade {modalidade!r}. "
            f"Declara: {', '.join(por_modalidade)}."
        )
    return por_modalidade[modalidade]


def fen_inicial(modalidade: str) -> str:
    """A posição inicial da [modalidade], em FEN, como o contrato a declara."""
    return _entrada(modalidade)["fen_inicial"]


def niveis_disponiveis(modalidade: str) -> tuple[NivelDeMotor, ...]:
    """Os níveis que o build oferece na [modalidade], do mais fraco ao mais forte.

    O Sagaz (o Magno) só entra com `magno_no_build: true`: sem a garantia de
    quase perfeição, o jogo sai com três personagens (a regra do nível Sagaz).
    """
    entrada = _entrada(modalidade)
    disponiveis = tuple(
        nivel
        for nivel, personagem in PERSONAGEM_DO_NIVEL.items()
        if personagem in entrada["niveis"]
        and (nivel is not NivelDeMotor.SAGAZ or magno_no_build())
    )
    return disponiveis


def _inteiro(caminho: str, valor: object, *, nulo: bool = False) -> int | None:
    """Confere que [valor] é um inteiro não negativo (ou `None`, se [nulo])."""
    if valor is None and nulo:
        return None
    # `bool` é subclasse de `int` em Python: `True` passaria por inteiro.
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
        raise ContratoXadrezInvalido(
            f"{caminho} tem de ser inteiro não negativo"
            f"{' ou null' if nulo else ''}, e veio {valor!r}."
        )
    return valor


def parametros_do_nivel(
    modalidade: str, nivel: NivelDeMotor
) -> ParametrosDoNivelXadrez:
    """Os números com que o personagem do [nivel] joga a [modalidade].

    Raises:
        ModalidadeDesconhecida: o contrato não declara a modalidade.
        ContratoXadrezInvalido: o build não oferece o nível (o Magno com
            `magno_no_build: false`), falta um campo, ou um número está fora do
            lugar. ⚠️ Falhar alto é o comportamento certo: cair num padrão faria
            o job calibrar o Magno com o orçamento da Cacau e gravar "sagaz".
    """
    entrada = _entrada(modalidade)
    personagem = PERSONAGEM_DO_NIVEL[nivel]
    caminho = f"por_modalidade.{modalidade}.niveis.{personagem}"
    if personagem not in entrada["niveis"]:
        # A modalidade não traz o personagem (a sonda não tem a Pita): é outra
        # recusa que a do Magno fora do build, e a mensagem diz qual.
        raise ContratoXadrezInvalido(
            f"a modalidade {modalidade!r} não traz o nível {nivel.value!r} "
            f"({personagem}). Traz: {', '.join(entrada['niveis'])}."
        )
    if nivel not in niveis_disponiveis(modalidade):
        raise ContratoXadrezInvalido(
            f"o build não oferece o nível {nivel.value!r} ({personagem}) na "
            f"modalidade {modalidade!r} (magno_no_build = {magno_no_build()})."
        )
    bruto = entrada["niveis"][personagem]
    faltam = [campo for campo in CAMPOS_DO_NIVEL if campo not in bruto]
    if faltam:
        raise ContratoXadrezInvalido(f"{caminho} sem {', '.join(faltam)}.")
    teto = _inteiro(f"{caminho}.teto_de_nos", bruto["teto_de_nos"])
    if teto == 0:
        raise ContratoXadrezInvalido(f"{caminho}.teto_de_nos = 0: um nível sem nós não joga.")
    for chance in ("chance_do_erro_milesimos", "chance_da_cegueira_milesimos"):
        if _inteiro(f"{caminho}.{chance}", bruto[chance]) > 1000:  # type: ignore[operator]
            raise ContratoXadrezInvalido(f"{caminho}.{chance} acima de 1000 milésimos.")
    return ParametrosDoNivelXadrez(
        personagem=personagem,
        profundidade_maxima=_inteiro(f"{caminho}.profundidade_maxima", bruto["profundidade_maxima"]),  # type: ignore[arg-type]
        teto_de_nos=teto,  # type: ignore[arg-type]
        quiescencia=str(bruto["quiescencia"]),
        margem_do_erro_cp=_inteiro(f"{caminho}.margem_do_erro_cp", bruto["margem_do_erro_cp"]),  # type: ignore[arg-type]
        chance_do_erro_milesimos=bruto["chance_do_erro_milesimos"],
        chance_da_cegueira_milesimos=bruto["chance_da_cegueira_milesimos"],
        rede_de_tempo_s=_inteiro(f"{caminho}.rede_de_tempo_s", bruto["rede_de_tempo_s"], nulo=True),
        relogio_s=_inteiro(f"{caminho}.relogio_s", bruto["relogio_s"], nulo=True),
    )


def versao_do_crate() -> str:
    """A versão do crate espelhado (`0.5.0`), lida do `Cargo.toml`.

    É a que o executável anuncia na abertura (`versao`), e o jogador recusa um
    executável de outra versão: ele foi compilado de outros fontes.
    """
    # `tomllib` (biblioteca padrão desde o Python 3.11) lê TOML; ele pede o
    # arquivo em BYTES (`"rb"`), para decidir a codificação sozinho.
    with CAMINHO_DO_CARGO.open("rb") as arquivo:
        return tomllib.load(arquivo)["package"]["version"]


def versao_do_motor() -> str:
    """O identificador do motor que jogou, no formato composto da migração 0014.

    `rust_0.5.0`: o mesmo texto que o app grava em `co_versao_motor` quando a
    partida usou o motor Rust (`dart_X|rust_Y` nas damas; o xadrez só tem o
    Rust). Assim uma linha do servidor e uma do aparelho com o mesmo motor se
    leem igual no banco.
    """
    return f"rust_{versao_do_crate()}"


def arquivos_do_motor() -> tuple[dict[str, str], ...]:
    """Os arquivos do espelho que DEFINEM este motor, com o SHA-256 de cada um.

    Ordenada pelo caminho, como a das damas e a do Quatro, para a dimensão
    `desafio.tb904_motor` tornar o carimbo decifrável com a MESMA lista de que ele
    saiu (`job/motor.py`, T082 da spec 012).
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


def versao_do_motor_no_espelho() -> str:
    """O carimbo do DESAFIO do xadrez: `xadrez-rust-<8 hex>` (T082 da spec 012).

    É o que o job grava em `desafio.tb001_desafio.co_versao_motor`, e sai dos
    hashes do espelho (`arquivos_do_motor`), com a conta das damas, do Pontinhos
    e do Quatro: os hashes ordenados entre si, concatenados, e o SHA-256 disso.

    ⚠️ **Não é o [versao_do_motor]** (`rust_0.10.0`), e de propósito, como nos
    outros jogos: o `rust_X` é o que o APP grava no log (a versão do binário) e
    o que a calibração do mate guarda; o carimbo do desafio é o que torna a linha
    da `tb904_motor` decifrável sem o Git. Uma versão do crate esquecida sem
    subir continuaria `rust_0.10.0` com fontes diferentes; o resumo, não.
    """
    hashes = sorted(arquivo["sha256"] for arquivo in arquivos_do_motor())
    digesto = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return f"xadrez-rust-{digesto[:8]}"
