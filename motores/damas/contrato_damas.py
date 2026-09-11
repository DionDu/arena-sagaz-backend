"""Os parâmetros dos quatro níveis, LIDOS DO CONTRATO em tempo de execução.

═══════════════════════════════════════════════════════════════════════════
POR QUE LER, E NÃO REPETIR OS NÚMEROS AQUI
═══════════════════════════════════════════════════════════════════════════

RF-DES-140 diz que o contrato do jogo é a **única** declaração dos parâmetros de
nível, e RF-DES-141 diz que o **backend lê o contrato em tempo de execução**.

Repetir `profundidade=1, ruido=90, ...` neste arquivo seria mais rápido de
escrever e criaria uma terceira cópia dos mesmos números — depois do Python do
laboratório e do Dart do app. Três cópias divergem; e a divergência não daria
erro nenhum: o job simplesmente calibraria o desafio contra um adversário
ligeiramente diferente do que a pessoa enfrenta, e a etiqueta "difícil"
descreveria alguém que não existe.

⚠️ **Note a assimetria entre os dois jogos, que é deliberada** (`research.md`
§R-20): nas damas o contrato é **gerado** do código do laboratório, então ler é
ler a fonte; no Pontinhos a política vive em Dart e o contrato é a **declaração**
dela, conferida por teste. Os dois arquivos explicam isso por dentro, e ⛔ não se
"uniformiza".

═══════════════════════════════════════════════════════════════════════════
DE ONDE O CONTRATO É LIDO
═══════════════════════════════════════════════════════════════════════════

De dentro do espelho, e não de `../ia`: **o Railway constrói a imagem a partir do
repositório do backend**, e o que não estiver lá dentro não existe na nuvem.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from pathlib import Path

from motores.nucleo.papeis import NivelDeMotor

# `parents[2]` sobe de `motores/damas/este_arquivo.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[2]
ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"

CAMINHO_DO_CONTRATO = (
    ESPELHO / "jogos" / "jogo_damas" / "contrato" / "contrato_damas.json"
)
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

# Os arquivos do espelho que, mudando, mudam **como o motor joga**. É deles que
# sai a versão carimbada — ver `versao_do_motor`.
PREFIXO_DO_MOTOR = "jogos/jogo_damas/"


@dataclass(frozen=True, slots=True)
class ParametrosDeNivel:
    """O orçamento e o desleixo de um nível, como o contrato os declara.

    ⚠️ **Os quatro níveis não são quatro motores**: são o mesmo motor com mais ou
    menos permissão para pensar, e com mais ou menos chance de escolher a segunda
    melhor ideia. Os nomes dos campos são os do contrato de propósito — quem lê
    uma linha do JSON e quem lê este arquivo estão olhando a mesma coisa.

    Atributos:
        identificador: `cacau` · `pita` · `tex` · `sagaz`.
        profundidade: teto de profundidade da busca.
        ruido: barulho na avaliação, em centésimos de pedra. ⚠️ Vale bem menos do
            que o número sugere: o minimax é um filtro de ruído, porque máximos e
            mínimos sobre muitas folhas independentes o cancelam na média.
        teto_de_nos: o orçamento que faz o mesmo nível jogar igual em qualquer
            máquina — é ele, e não o tempo, que define o nível.
        tempo_maximo: a **rede de segurança**, não um parâmetro de dificuldade.
            Toda vez que ela morde, a promessa do teto de nós se quebra.
        extensao_de_captura: a quiescência. É o freio mais forte da lista:
            desligada, produz o erro mais humano que existe em damas — parar de
            contar no meio da troca.
        chance_de_errar: probabilidade de jogar o **segundo** melhor lance, e só
            quando os dois estão perto em nota. Sortear entre todos os lances
            produziria erros absurdos, que irritam.
        margem_do_erro: o quão perto os dois precisam estar para o erro valer.
    """

    identificador: str
    profundidade: int
    ruido: int
    teto_de_nos: int
    tempo_maximo: float
    extensao_de_captura: bool
    chance_de_errar: float
    margem_do_erro: int


@functools.lru_cache(maxsize=1)
def carregar_contrato() -> dict:
    """O contrato de damas, lido do espelho e guardado em memória.

    `lru_cache` porque o job pergunta os parâmetros milhares de vezes durante uma
    calibração, e reler um JSON de 30 KB a cada pergunta seria desperdício puro.

    ⚠️ O cache também torna o contrato **imutável durante a execução**, o que é o
    comportamento certo: um job que recarregasse o arquivo no meio poderia medir
    metade dos candidatos com uma régua e metade com outra, e a `co_versao_perfil`
    gravada mentiria sobre os dois.
    """
    if not CAMINHO_DO_CONTRATO.exists():
        raise FileNotFoundError(
            f"contrato de damas ausente em {CAMINHO_DO_CONTRATO}.\n"
            "Ele viaja dentro do espelho do laboratório (RF-DES-148). "
            "Rode, na máquina do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    return json.loads(CAMINHO_DO_CONTRATO.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=8)
def parametros_do_nivel(nivel: NivelDeMotor) -> ParametrosDeNivel:
    """Os parâmetros do nível, como o contrato os declara.

    Raises:
        KeyError: se o contrato não declarar o nível. ⚠️ Falhar alto é o
            comportamento certo: cair num valor padrão faria o job calibrar o
            Sagaz com o orçamento do Cacau e gravar "sagaz" no banco.
    """
    niveis = carregar_contrato()["dificuldade"]["niveis"]
    if nivel.value not in niveis:
        raise KeyError(
            f"o contrato de damas não declara o nível {nivel.value!r}. "
            f"Declara: {', '.join(sorted(niveis))}."
        )
    bruto = niveis[nivel.value]
    return ParametrosDeNivel(
        identificador=bruto["identificador"],
        profundidade=int(bruto["profundidade"]),
        ruido=int(bruto["ruido"]),
        teto_de_nos=int(bruto["teto_de_nos"]),
        tempo_maximo=float(bruto["tempo_maximo"]),
        extensao_de_captura=bool(bruto["extensao_de_captura"]),
        chance_de_errar=float(bruto["chance_de_errar"]),
        margem_do_erro=int(bruto["margem_do_erro"]),
    )


def modalidades_declaradas() -> tuple[str, ...]:
    """As modalidades que o contrato conhece, na ordem em que ele as lista.

    ⚠️ **Modalidade é DADO, não `enum`** — é isso que faz italiana e russa caberem
    depois sem migração, e é a mesma regra que o app já segue.
    """
    return tuple(carregar_contrato()["regulamentos"])


def arquivos_do_motor() -> tuple[dict[str, str], ...]:
    """Os arquivos do espelho que DEFINEM este motor, com o SHA-256 de cada um.

    Returns:
        Uma tupla de `{"caminho", "sha256"}`, **ordenada pelo caminho** — a ordem
        de leitura humana, que é a que serve à linha do banco.

    ⚠️ **Esta função existe para que a lista seja UMA só** (T049e). Ela nasceu de
    dentro de `versao_do_motor`, que é quem já sabia quais arquivos entram no
    resumo; `desafio.tb904_motor` precisa da mesma lista para tornar o
    `damas-py-<8 hex>` decifrável, e reescrevê-la lá seria a segunda fonte que
    divergiria no primeiro arquivo novo do motor — com o sintoma pior possível:
    a linha do banco diria que o resumo saiu de um conjunto, e o resumo teria
    saído de outro.

    ⛔ **Não é cacheada de propósito.** Ela devolve dicionários novos a cada
    chamada, e quem os recebe pode guardá-los num JSON; um objeto compartilhado
    entre chamadas convidaria a mutação acidental do que o cadeado compara.
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


@functools.lru_cache(maxsize=1)
def versao_do_motor() -> str:
    """O identificador do motor que jogou — para o carimbo (RF-DES-164).

    ⚠️ **Sai dos hashes do espelho, e não de um número escrito à mão.** Um número
    à mão envelhece calado: alguém reespelha um motor novo, esquece de subir a
    versão, e as medições novas ficam indistinguíveis das velhas no banco. É
    exatamente a armadilha de `co_versao_motor` registrada em 26/08/2026.

    A forma é `damas-py-<8 hex>`, onde os 8 dígitos são o começo do SHA-256 da
    **lista de hashes** dos arquivos do motor de damas dentro do espelho. Cabe
    nos 40 caracteres da coluna e respeita a forma que o carimbo exige.
    """
    import hashlib

    # ⚠️ **Ordenado pelos HASHES, e não pelos caminhos** — e a diferença não é
    # cosmética: é esta ordem que o resumo de 8 dígitos já publicado no banco
    # usou. Trocá-la por `sorted(por caminho)` daria outro `damas-py-…` sem que
    # um único byte do motor tivesse mudado, e as medições novas ficariam
    # indistinguíveis de motor novo. A lista de arquivos vem de
    # `arquivos_do_motor()` para não haver dois filtros a divergir (T049e).
    hashes = sorted(arquivo["sha256"] for arquivo in arquivos_do_motor())
    digesto = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
    return f"damas-py-{digesto[:8]}"


def versao_do_contrato() -> str:
    """A versão declarada dentro do contrato — sobe quando a FORMA dele muda."""
    return carregar_contrato()["versao"]
