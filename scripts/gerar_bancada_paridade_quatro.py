"""A BANCADA DE PARIDADE DO QUATRO EM LINHA - o servidor joga, o aplicativo reproduz.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT FAZ
═══════════════════════════════════════════════════════════════════════════

Ele joga partidas de CPU contra CPU pelo caminho REAL do servidor
(`JogadorDartQuatro.decidir`, o executável compilado do motor do aparelho, com a
semente de cada lance por `job/semente.py`), guarda a semente-mestra e **todos
os lances** - com a ação, os nós, a profundidade e o motivo de parada -, e
escreve um arquivo versionado nas duas pontas. O aplicativo reproduz cada
partida em `test/modulos/jogos/quatro/paridade_com_servidor_quatro_test.dart`,
pelo `CpuQuatro` (o mesmo objeto que a tela usa), e para na **primeira**
divergência.

⚠️ É a ideia do dono de 26/09/2026 (`docs/DECISOES-do-dono.md` §8zj, no
repositório do app), escrita para as damas em `gerar_vetores_paridade_motores.py`
e repetida para o Pontinhos: as travas de SHA-256 provam que os dois lados rodam
**o mesmo código**, e os episódios de divergência foram todos o mesmo código
recebendo **argumentos diferentes** (o relógio, o teto, a semente).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE UM ARQUIVO SEPARADO, E POR QUE ESTE NOME
═══════════════════════════════════════════════════════════════════════════

O das damas é feito de FEN, regulamento e base de finais, e regerá-lo custa
dezenas de minutos ao dono; o do Pontinhos carrega a softmax da rede em cada
lance. Cada jogo tem o seu, com a mesma FORMA (`de_documento`, `versao`,
`motor`, `partidas`), e quem aprendeu a ler um lê o outro.

O nome é `bancada-paridade-quatro.json`, e não `vetores-paridade-quatro.json`,
porque esse já existe: são os vetores de REGRAS, MEDIDAS e PREDICADO (T106),
gerados pelo motor Dart. Este é gerado pelo SERVIDOR, jogando.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS DECISÕES DO FORMATO
═══════════════════════════════════════════════════════════════════════════

1. **A semente vem pelo caminho do DESAFIO** (`job/semente.py`): uma mestra por
   partida e `semente_do_lance(mestra, n)`, com `n` contado a partir da
   **posição publicada**.

2. ⛔ **Há partidas que começam de uma posição publicada**, e não só do
   tabuleiro vazio. No Quatro a posição de partida é uma SEQUÊNCIA de lances, e
   a sequência que o app passa ao motor inclui os publicados; quem conta a
   ordem do lance pela sequência inteira semeia o 1º lance do desafio como o
   7º. Foi exatamente o defeito do desafio do Pontinhos (o lance 4 semeado como
   18), e uma bancada só do tabuleiro vazio passaria por cima dele: com zero
   lances publicados as duas contas coincidem.

3. **Os níveis FRACOS entram**, todos os que o contrato oferece: é neles que o
   sorteador manda (ε e `percebe`), e foi neles que os episódios moraram.

4. **Ação, nós, profundidade e motivo entram no arquivo**, e não só o lance:
   dois motores podem escolher a mesma coluna parando em pontos diferentes da
   busca, ou por outro caminho da política.

5. **Os argumentos de cada nível entram no arquivo** (`argumentos`), e o app os
   confere contra o contrato DELE antes do 1º lance: é a parte que acusa o
   defeito pelo nome, e não pelo sintoma.

6. **As sementes-mestras são fixas**: rodar duas vezes dá o mesmo arquivo, e o
   `git diff` mostra só o que mudou de verdade.

7. **As duas cópias são byte-idênticas** (`-text` no `.gitattributes` dos dois
   repositórios), e há teste conferindo o SHA-256 delas.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\gerar_bancada_paridade_quatro.py

Leva poucos segundos. ⚠️ **Sempre que o motor ou o contrato mudarem** - o teste
do backend avisa, comparando os resumos gravados com os do espelho de hoje.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from job import semente as semente_mod  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from motores.quatro.jogador_dart_quatro import jogador_compartilhado  # noqa: E402
from motores.quatro.motor_quatro import MotorQuatro, estado_inicial  # noqa: E402

#: A versão do documento. Sobe quando a FORMA muda, e nunca por conteúdo novo.
VERSAO = 1

#: As duas cópias: a do app fica em `contracts/` da spec 010, ao lado dos
#: vetores de regras; a daqui fica em `contratos/`.
DESTINOS = (
    RAIZ / "contratos" / "bancada-paridade-quatro.json",
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "contracts"
    / "bancada-paridade-quatro.json",
)

#: As sementes-mestras das partidas do tabuleiro vazio. As mesmas três da
#: bancada das damas: arbitrárias, dentro da faixa de `job/semente.py`, e
#: distantes uma da outra.
SEMENTES_MESTRAS: tuple[int, ...] = (697571591, 12345, 4_000_000_007)

#: A posição publicada das partidas que começam no meio (decisão 2).
#:
#: ⚠️ Seis lances, e não um: com um só, o deslocamento seria de 1, e uma conta
#: que errasse por "um a mais" passaria despercebida por coincidir em outro
#: lugar. Seis lances legais, sem linha formada, com a vez do J1.
POSICAO_PUBLICADA = "s4s4s3s5s4s3"

#: A semente-mestra das partidas da posição publicada: a do primeiro desafio.
SEMENTE_DA_POSICAO_PUBLICADA = 697571591

#: Os níveis do motor, pelo personagem do contrato (`magno` → `SAGAZ`).
NIVEL_DO_PERSONAGEM: dict[str, NivelDeMotor] = {
    personagem: nivel for nivel, personagem in contrato_quatro.PERSONAGEM_DO_NIVEL.items()
}


def argumentos_do_nivel(co_modalidade: str, nivel: NivelDeMotor) -> dict[str, Any]:
    """O que o servidor manda ao motor naquele nível, como dado.

    ⚠️ Sai do contrato (o mesmo `para_pedido` que `JogadorDartQuatro.decidir`
    usa), e não de números escritos aqui. ⚠️ O `limiteMs` não entra, e a
    ausência é a informação: o servidor joga só por nós; o app joga com a rede
    de 10 s, e é por isso que o teste de lá olha o motivo quando os nós
    divergem.
    """
    parametros = contrato_quatro.parametros_do_personagem(co_modalidade, nivel)
    return {"personagem": parametros.personagem, **parametros.para_pedido()}


def jogar_uma_partida(
    *,
    co_modalidade: str,
    nivel: NivelDeMotor,
    nu_semente: int,
    lances_iniciais: str = "",
) -> dict[str, Any]:
    """Uma partida inteira de CPU contra CPU, no mesmo nível dos dois lados.

    ⚠️ Os dois lados no MESMO nível: o que se quer comparar é o adversário que
    o aparelho enfrenta, e um nível de cada lado mediria uma combinação que o
    desafio não produz.

    Args:
        lances_iniciais: a posição publicada, na notação (`s4s4s3`); vazia no
            tabuleiro vazio. Os lances dela não são jogados por ninguém aqui: a
            ordem `n` do 1º lance jogado é 1.
    """
    arbitro = MotorQuatro(co_modalidade)
    estado = (
        arbitro.estado_de_sequencia(lances_iniciais)
        if lances_iniciais
        else estado_inicial(co_modalidade)
    )
    jogador = jogador_compartilhado()

    lances: list[dict[str, Any]] = []
    n = 0
    while True:
        veredito = arbitro.veredito(estado)
        if veredito.acabou:
            break
        n += 1
        # ⚠️ A semente do lance pela conta do DESAFIO, com `n` contado a partir
        # da posição publicada (decisão 2 do cabeçalho).
        semente = semente_mod.semente_do_lance(nu_semente, n)
        resposta = jogador.decidir(
            lances=estado.sequencia,
            co_modalidade=co_modalidade,
            nivel=nivel,
            semente=semente,
        )
        lances.append(
            {
                "n": n,
                "semente": semente,
                "lance": resposta["lance"],
                "acao": resposta["acao"],
                "nos": resposta["nosVisitados"],
                "profundidade": resposta["profundidadeAtingida"],
                "motivo": resposta["motivoParada"],
            }
        )
        estado = arbitro.aplicar(estado, resposta["lance"])

    prefixo = "publicada" if lances_iniciais else "vazio"
    return {
        "id": f"quatro-{co_modalidade}-{nivel.value}-{prefixo}-{nu_semente}",
        "co_jogo": "quatro",
        "co_modalidade": co_modalidade,
        "co_nivel": nivel.value,
        "nu_semente": nu_semente,
        "lances_iniciais": lances_iniciais,
        "argumentos": argumentos_do_nivel(co_modalidade, nivel),
        "lances": lances,
        "co_lances_finais": estado.sequencia,
        "co_desfecho": veredito.co_motivo,
        "vencedor": veredito.vencedor,
    }


def combinacoes(
    modalidades: tuple[str, ...],
) -> list[tuple[str, NivelDeMotor, int, str]]:
    """As partidas a jogar, em ordem estável: `(modalidade, nível, mestra, posição)`.

    ⚠️ Ordem estável importa: as duas cópias são comparadas byte a byte.
    """
    lista: list[tuple[str, NivelDeMotor, int, str]] = []
    for co_modalidade in modalidades:
        for personagem in contrato_quatro.niveis_disponiveis(co_modalidade):
            nivel = NIVEL_DO_PERSONAGEM[personagem]
            for mestra in SEMENTES_MESTRAS:
                lista.append((co_modalidade, nivel, mestra, ""))
            lista.append(
                (co_modalidade, nivel, SEMENTE_DA_POSICAO_PUBLICADA, POSICAO_PUBLICADA)
            )
    return lista


def montar(*, modalidades: tuple[str, ...], falar: bool = True) -> dict[str, Any]:
    """O documento inteiro."""
    partidas: list[dict[str, Any]] = []
    comeco = time.monotonic()
    for co_modalidade, nivel, mestra, iniciais in combinacoes(modalidades):
        t0 = time.monotonic()
        partida = jogar_uma_partida(
            co_modalidade=co_modalidade,
            nivel=nivel,
            nu_semente=mestra,
            lances_iniciais=iniciais,
        )
        partidas.append(partida)
        if falar:
            print(
                f"  {partida['id']}: {len(partida['lances'])} lances, "
                f"{partida['co_desfecho']}, {time.monotonic() - t0:.1f}s",
                flush=True,
            )

    identificadores = [p["id"] for p in partidas]
    assert len(set(identificadores)) == len(identificadores), identificadores
    if falar:
        print(f"total: {time.monotonic() - comeco:.1f}s", flush=True)

    jogador = jogador_compartilhado()
    return {
        "de_documento": "Bancada de paridade do Quatro em Linha (T111 da spec "
        "010). GERADO por scripts/gerar_bancada_paridade_quatro.py - nao edite a "
        "mao. O aplicativo reproduz estas partidas em "
        "test/modulos/jogos/quatro/paridade_com_servidor_quatro_test.dart.",
        "versao": VERSAO,
        # De que motor e de que contrato saíram estes lances. Um arquivo gerado
        # por um motor antigo se denuncia por aqui, e não por uma divergência
        # misteriosa no meio de uma partida.
        "motor": {
            "quatro": jogador.resumo_do_motor,
            "contrato": contrato_quatro.sha256_do_contrato(),
        },
        "partidas": partidas,
    }


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Gera as partidas da bancada de paridade do Quatro (T111).",
    )
    analisador.add_argument(
        "--amostra",
        action="store_true",
        help="escreve num arquivo temporário e NÃO toca as cópias versionadas",
    )
    args = analisador.parse_args(argv)
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8", errors="replace")

    documento = montar(modalidades=contrato_quatro.modalidades_declaradas())

    # `newline=""` porque o arquivo é comparado por SHA-256 entre repositórios:
    # o `write_text` do Windows converteria LF em CRLF.
    texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"
    destinos: tuple[Path, ...] = (
        (Path(tempfile.gettempdir()) / "amostra-bancada-paridade-quatro.json",)
        if args.amostra
        else DESTINOS
    )
    for destino in destinos:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8", newline="") as saida:
            saida.write(texto)
        print(f"escrito: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
