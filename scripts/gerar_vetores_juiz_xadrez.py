"""T069 (spec 012) - EMITE OS VETORES DO JUIZ DO XADREZ (fita de fatos → medidas → veredito).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O desafio do xadrez é julgado **duas vezes**: no aparelho, pelo medidor do app
(`lib/modulos/jogos/xadrez/logica/medidor_desafio_xadrez.dart`, T070), e aqui,
pelo juiz do servidor (`motores/juiz.py` + `motores/xadrez/feitos_xadrez.py`).
As duas escritas contam sobre os MESMOS fatos, que vêm do motor em Rust; o que
pode divergir é a conta (a troca nas duas ordens, a sequência de xeques, o
marco da última fileira). Estes vetores são o teste único que roda dos dois
lados, como os da 009 (`gerar_vetores_verificacao.py`).

═══════════════════════════════════════════════════════════════════════════
O QUE É ESCRITO À MÃO, E O QUE SAI DO MOTOR
═══════════════════════════════════════════════════════════════════════════

- **À mão**: a posição (FEN pequeno, conferível de cabeça), os lances, o
  veredito que eu espero e algumas medidas que eu espero (`confere`). O gerador
  **para** se o juiz disser outra coisa: é assim que um vetor escrito errado não
  vira um vetor mentiroso.
- **Do motor**: os FATOS e as MARCAS de cada lance (o executável
  `servidor_de_lances_xadrez`, operação `aplicar`). ⛔ Nenhum fato é escrito
  aqui: quem diz que o peão foi comido en passant ou que a torre andou no roque
  é o Rust.
- **Do medidor de produção**: as medidas e o lance em que o objetivo caiu
  (`juiz.julgar_desafio`). Recontar aqui seria uma terceira escrita da regra que
  o vetor existe para conferir.

⚠️ **As chegadas são montadas pelas RECEITAS do job** (`job/tipos_de_desafio.py`,
desde a T072): até ela, este arquivo escrevia a tabela de
`contracts/desafio-xadrez.md` §2 à mão, porque as receitas ainda não existiam.
A troca não mudou um byte do arquivo de vetores (foi conferido ao regerar), e
`tests/unitarios/test_receitas_do_xadrez.py` confere, vetor a vetor, que cada
receita monta exatamente a chegada gravada.

═══════════════════════════════════════════════════════════════════════════
OS CASOS OBRIGATÓRIOS (`contracts/desafio-xadrez.md` §3)
═══════════════════════════════════════════════════════════════════════════

Cada um tem pelo menos um vetor, marcado em `caso_obrigatorio`, e o teste
(`tests/unitarios/test_feitos_xadrez.py`) reprova o arquivo em que um faltar:
a espiã comida en passant; a torre espiã no roque; o peão espião promovido; o
xeque descoberto da espiã; as duas ordens da troca e a ordem 2 sem retomada; a
repetição tripla durante os xeques seguidos.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\gerar_vetores_juiz_xadrez.py

Precisa do executável compilado (`scripts/compilar_motor_xadrez.py`), e escreve
as duas cópias, byte-idênticas:

    arena-sagaz-backend/contratos/vetores-juiz-xadrez.json
    arena-sagaz-frontend/test/modulos/jogos/xadrez/vetores_juiz_xadrez.json

⚠️ **Vetor nunca é apagado nem editado** (a regra 4 dos vetores da 009):
corrigir um vetor errado é vetor NOVO, no fim da lista; o antigo, se descrevia
algo impossível, ganha `"obsoleto": true` com o motivo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR  # noqa: E402
from motores.juiz import julgar_desafio  # noqa: E402
from motores.xadrez import contrato_xadrez, feitos_xadrez  # noqa: E402
from motores.xadrez.jogador_xadrez import (  # noqa: E402
    JogadorXadrez,
    MotorXadrezRecusou,
)

#: A versão do documento. Sobe quando o FORMATO muda (um campo novo que o
#: leitor precisa conhecer), nunca quando entra vetor.
VERSAO = 1

#: A cópia daqui. Fica em `contratos/`, e não em `tests/dados/`: o
#: `.dockerignore` tira `tests/` da imagem, e é a lição da T064.
COPIA_DAQUI = RAIZ / "contratos" / "vetores-juiz-xadrez.json"

#: O repositório do app, quando está ao lado (no CI cada repositório roda
#: sozinho, e a cópia do app simplesmente não é escrita).
FRONTEND = RAIZ.parent / "arena-sagaz-frontend"

#: A cópia do app, que o teste do medidor do app (T070) lê.
COPIA_DO_APP = FRONTEND / "test" / "modulos" / "jogos" / "xadrez" / "vetores_juiz_xadrez.json"

#: Os casos que `contracts/desafio-xadrez.md` §3 exige, pelo nome que o campo
#: `caso_obrigatorio` de cada vetor usa.
CASOS_OBRIGATORIOS: tuple[str, ...] = (
    "espia_comida_en_passant",
    "torre_espia_no_roque",
    "peao_espiao_promovido",
    "xeque_descoberto_da_espia",
    "troca_ordem_1",
    "troca_ordem_2",
    "troca_ordem_2_sem_retomada",
    "repeticao_tripla_nos_xeques_seguidos",
)

#: As receitas do xadrez, no ar ou fora dele (a promoção da T078 MOVE uma
#: receita de um registro para o outro, e o gerador não pode depender de onde
#: ela mora).
RECEITAS_DO_XADREZ = {
    co_tipo: receita
    for co_tipo, receita in {**RECEITAS_FORA_DO_AR, **RECEITAS}.items()
    if receita.co_jogo == "xadrez"
}

#: O número de cada tipo, lido da receita (que tem os números da
#: `0040_desafio_xadrez`; `test_receitas_do_xadrez.py` confere os dois).
NUMERO_DO_TIPO: dict[str, int] = {
    co_tipo: receita.nu_tipo_desafio for co_tipo, receita in RECEITAS_DO_XADREZ.items()
}

#: A modalidade do xadrez, LIDA do contrato (o nome não se escreve aqui: é
#: dado, RF-XDR-013).
MODALIDADE = contrato_xadrez.modalidades_declaradas()[0]


# ═══════════════════════════════════════════════════════════════════════════
# As chegadas de `contracts/desafio-xadrez.md` §2
# ═══════════════════════════════════════════════════════════════════════════


def chegada_do_tipo(tipo: str, *, n: int, k: int = 1, peca: str = "peao") -> dict[str, Any]:
    """A chegada de [tipo], montada pela RECEITA do job (T072).

    Args:
        n: o N da janela (`lances`; no `xadrez_dar_mate`, o 5 da tabela).
        k: o K da cláusula de quantidade, onde há (`capturas` ou `xeques`,
            conforme o tipo: a receita lê só o que usa).
        peca: o tipo de peça do `xadrez_nao_perder`.

    ⚠️ **"`lances_do_jogador = N`" da tabela é a janela de N lances MAIS a
    cláusula `lances_do_jogador ≥ N`**, e quem a escreve agora é a receita.

    Raises:
        KeyError: tipo que não é do xadrez, ou sem receita.
    """
    receita = RECEITAS_DO_XADREZ.get(tipo)
    if receita is None:
        raise KeyError(f"tipo de desafio do xadrez desconhecido: {tipo!r}")
    return receita.montar({"lances": n, "capturas": k, "xeques": k, "peca": peca})


# ═══════════════════════════════════════════════════════════════════════════
# A posição publicada e o vetor
# ═══════════════════════════════════════════════════════════════════════════


def posicao(
    fen: str | None,
    *,
    cor: str = "branca",
    marcas: dict[str, str] | None = None,
    classes: dict[str, str] | None = None,
    troca: dict[str, str] | None = None,
) -> dict[str, Any]:
    """A `js_posicao_inicial` no formato de `contracts/desafio-xadrez.md` §1.

    `fen=None` é a posição inicial da modalidade, lida do contrato. `marcas`,
    `classes` e `troca` só entram quando o tipo os usa, como no §1.
    """
    dado: dict[str, Any] = {
        "jogo": "xadrez",
        "modalidade": MODALIDADE,
        "fen": fen or contrato_xadrez.fen_inicial(MODALIDADE),
        "cor_da_pessoa": cor,
    }
    if marcas is not None:
        dado["marcas"] = marcas
    if classes is not None:
        dado["classes"] = classes
    if troca is not None:
        dado["troca"] = troca
    # A origem é a da base equilibrada: as posições daqui são escritas à mão,
    # e o campo existe para o formato ser o mesmo que o job publica.
    dado["origem"] = "base_equilibrada"
    return dado


def _passos_ate_a_recusa(
    motor: JogadorXadrez, js_posicao: dict[str, Any], lances: list[str]
) -> tuple[list[dict[str, Any]], str | None]:
    """Os passos que o motor aceitou e o código da recusa, se houve uma.

    Reproduz lance a lance (o prefixo crescendo) para guardar os fatos de cada
    lance aceito ANTES do que foi recusado: o vetor `dado_invalido` mostra onde
    a fita deixou de ser uma partida.
    """
    codigo: str | None = None
    # Do mais longo para o mais curto: o 1º prefixo aceito é a parte da fita
    # que é partida, e o `codigo` guardado é o da recusa do lance seguinte.
    for quantos in range(len(lances), -1, -1):
        try:
            passos = feitos_xadrez.reproduzir(js_posicao, lances[:quantos], motor=motor)
        except MotorXadrezRecusou as recusa:
            codigo = recusa.codigo
            continue
        return passos, (None if quantos == len(lances) else codigo)
    raise AssertionError("nem a fita vazia foi aceita: a posição está errada")


def vetor(
    motor: JogadorXadrez,
    *,
    identificador: str,
    descricao: str,
    tipo: str,
    js_posicao: dict[str, Any],
    lances: list[str],
    chegada: dict[str, Any],
    veredito: str,
    lance_que_cumpre: int | None = None,
    confere: dict[str, int] | None = None,
    caso_obrigatorio: str | None = None,
) -> dict[str, Any]:
    """Um vetor: a posição, a fita com os fatos, a chegada e o esperado.

    Args:
        veredito, lance_que_cumpre, confere: o que EU espero, escrito à mão. O
            gerador para quando o juiz discorda (ver o cabeçalho).
    """
    passos, recusa = _passos_ate_a_recusa(motor, js_posicao, lances)
    fita = []
    for n, lance in enumerate(lances, start=1):
        # A pessoa tem a vez na posição publicada e é o `+1` (o J1, azul, que
        # é quem joga embaixo em qualquer cor de regra).
        entrada: dict[str, Any] = {"n": n, "jogador": 1 if n % 2 else -1, "lance": lance}
        if n <= len(passos):
            entrada["fatos"] = passos[n - 1]["fatos"]
            entrada["marcas"] = passos[n - 1]["marcas"]
        else:
            # O lance que o motor recusou (os seguintes nem chegam a ele).
            entrada["recusa"] = recusa if n == len(passos) + 1 else None
        fita.append(entrada)

    julgamento = julgar_desafio(
        co_jogo="xadrez",
        js_posicao_inicial=js_posicao,
        js_chegada=chegada,
        fita=[{k: l[k] for k in ("n", "jogador", "lance")} for l in fita],
        jogador=1,
    )
    assert julgamento.veredito == veredito, (
        f"{identificador}: eu esperava {veredito}, o juiz disse {julgamento.veredito} "
        f"({julgamento.de_motivo}); feitos {julgamento.feitos}"
    )
    assert julgamento.nu_lance_cumpre_desafio == lance_que_cumpre, (
        f"{identificador}: eu esperava o objetivo no lance {lance_que_cumpre}, o juiz "
        f"disse {julgamento.nu_lance_cumpre_desafio}"
    )
    for chave, valor in (confere or {}).items():
        assert julgamento.feitos.get(chave) == valor, (
            f"{identificador}: eu esperava {chave} = {valor}, o juiz mediu "
            f"{julgamento.feitos.get(chave)}"
        )

    return {
        "id": identificador,
        "de_vetor": descricao,
        "caso_obrigatorio": caso_obrigatorio,
        "co_jogo": "xadrez",
        "co_modalidade": MODALIDADE,
        "nu_tipo_desafio": NUMERO_DO_TIPO[tipo],
        "co_tipo_desafio": tipo,
        "jogador": 1,
        "js_posicao_inicial": js_posicao,
        "lances": fita,
        "js_chegada": chegada,
        "esperado": {
            "veredito": julgamento.veredito,
            "feitos": julgamento.feitos,
            "nu_lance_cumpre_desafio": julgamento.nu_lance_cumpre_desafio,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# As posições, uma frase cada (brancas maiúsculas, pretas minúsculas)
# ═══════════════════════════════════════════════════════════════════════════

#: Rei branco em e1 com um peão em e2; rei preto em e8 com um peão em d4. O
#: peão branco avança duas casas e passa ao lado do preto: o en passant.
FEN_EN_PASSANT_SOFRIDO = "4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1"
#: Peão branco em e5, peão preto em d7: o preto avança duas, e o branco come de
#: passagem.
FEN_EN_PASSANT_FEITO = "4k3/3p4/8/4P3/8/8/8/4K3 w - - 0 1"
#: Rei branco em e1 e torre em h1, com o direito ao roque curto; rei preto em f8.
#: Depois do roque, a torre para em f1 e a coluna f está livre até o rei.
FEN_ROQUE = "5k2/8/8/8/8/8/8/4K2R w K - 0 1"
#: Peão branco em b7, a um passo da promoção; rei preto em h8; cavalo preto em
#: b1, na coluna do peão.
FEN_PROMOCAO = "7k/1P6/8/8/8/8/8/1n2K3 w - - 0 1"
#: Bispo branco em a1 e cavalo branco em d4 na mesma diagonal do rei preto (h8):
#: o cavalo sai, e o bispo dá o xeque.
FEN_DESCOBERTO = "7k/8/8/8/3N4/8/8/B3K3 w - - 0 1"
#: Bispo branco em b1, torre branca em a4, cavalo preto em f6: o bispo vai a e4,
#: onde o cavalo o come, e a torre retoma pela 4ª fileira.
FEN_TROCA_OFERECIDA = "4k3/8/5n2/8/R7/8/8/1B2K3 w - - 0 1"
#: Bispo branco em b2 e cavalo preto em f6 na mesma diagonal; peão preto em g7,
#: que pode retomar.
FEN_TROCA_COMENDO = "4k3/6p1/5n2/8/8/8/1B6/4K3 w - - 0 1"
#: Dama branca em d5, rei preto em h8 (com o peão de h7): a dama vai e volta
#: entre d4 e d5, sempre dando xeque, e o rei vai e volta entre h8 e g8.
FEN_XEQUES = "7k/7p/8/3Q4/8/8/8/4K3 w - - 0 1"
#: Cavalo branco em c3, torre branca em b1; torre preta em b5 (o alvo) e peão
#: preto em a4. O cavalo come a torre direto, ou o peão, e a torre come a torre.
FEN_ALVO = "4k3/8/8/1r6/p7/2N5/8/1R2K3 w - - 0 1"
#: Cavalo branco em c3 e bispo branco em f2; peões pretos em a4 e c5. O cavalo
#: come um peão e depois o outro, ou o bispo come o segundo.
FEN_COMER_COM = "4k3/8/8/2p5/p7/2N5/5B2/4K3 w - - 0 1"
#: A pessoa joga de PRETAS: torre preta em h8 com a coluna h livre até h1, a
#: última fileira de quem joga de pretas.
FEN_PRETAS = "4k2r/8/8/8/8/8/8/R3K3 b - - 0 1"

#: O vai e vem da dama e do rei (FEN_XEQUES). A posição do início volta depois
#: do 4º e do 8º meio-lance: no 8º ela aparece pela 3ª vez, e o motor encerra a
#: partida por repetição, num lance do ADVERSÁRIO, logo depois do 4º xeque.
VAI_E_VEM = ["d5d4", "h8g8", "d4d5", "g8h8", "d5d4", "h8g8", "d4d5", "g8h8"]


def vetores_da_espia(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """A espiã: en passant, roque, promoção e xeque descoberto, e o alvo."""
    espia_e2 = posicao(FEN_EN_PASSANT_SOFRIDO, marcas={"espia": "e2"})
    torre = posicao(FEN_ROQUE, marcas={"espia": "h1"})
    peao = posicao(FEN_PROMOCAO, marcas={"espia": "b7"})
    return [
        vetor(
            motor,
            identificador="xadrez-espia-comida-en-passant",
            descricao="O peão espião avança duas casas, e o peão preto o come DE "
            "PASSAGEM: a peça comida não está na casa de destino. A espiã sai do "
            "tabuleiro, e a cláusula 'a espiã não foi comida' fica violada para "
            "sempre: o 2o lance da pessoa não salva mais nada.",
            tipo="xadrez_espia_proteger",
            js_posicao=espia_e2,
            lances=["e2e4", "d4e3", "e1d1"],
            chegada=chegada_do_tipo("xadrez_espia_proteger", n=2),
            veredito="nao_cumpriu",
            confere={"espia_comida": 1, "pecas_perdidas_peao": 1, "lances_do_jogador": 2},
            caso_obrigatorio="espia_comida_en_passant",
        ),
        vetor(
            motor,
            identificador="xadrez-espia-protegida-sem-en-passant",
            descricao="A MESMA posição e o mesmo avanço, e o preto não come: a "
            "espiã chega viva ao 2o lance da pessoa.",
            tipo="xadrez_espia_proteger",
            js_posicao=espia_e2,
            lances=["e2e4", "e8d7", "e1d1"],
            chegada=chegada_do_tipo("xadrez_espia_proteger", n=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"espia_comida": 0},
        ),
        vetor(
            motor,
            identificador="xadrez-espia-come-en-passant",
            descricao="O preto avança duas casas ao lado do peão espião, e a "
            "espiã come de passagem: o motor diz que ela comeu, e a peça comida "
            "é o peão de d5, e não uma peça em d6.",
            tipo="xadrez_espia_comer",
            js_posicao=posicao(FEN_EN_PASSANT_FEITO, marcas={"espia": "e5"}),
            lances=["e1d1", "d7d5", "e5d6"],
            chegada=chegada_do_tipo("xadrez_espia_comer", n=3, k=1),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"capturas_da_espia": 1, "pecas_comidas_peao": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-torre-espia-no-roque-da-xeque",
            descricao="A torre espiã de h1 anda no roque (o lance é do REI, e1 "
            "para g1) e para em f1, de frente para o rei preto: é ela quem dá o "
            "xeque. Quem seguisse a casa h1 não veria xeque nenhum.",
            tipo="xadrez_espia_xeque",
            js_posicao=torre,
            lances=["e1g1"],
            chegada=chegada_do_tipo("xadrez_espia_xeque", n=2, k=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"xeques_da_espia": 1},
            caso_obrigatorio="torre_espia_no_roque",
        ),
        vetor(
            motor,
            identificador="xadrez-torre-espia-no-roque-atravessa",
            descricao="A mesma torre, depois do roque, sobe a coluna f até a 8a "
            "fileira: a marca foi seguida pela identidade da peça.",
            tipo="xadrez_espia_atravessar",
            js_posicao=torre,
            lances=["e1g1", "f8e7", "f1f8"],
            chegada=chegada_do_tipo("xadrez_espia_atravessar", n=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"espia_na_ultima_fileira": 1},
            caso_obrigatorio="torre_espia_no_roque",
        ),
        vetor(
            motor,
            identificador="xadrez-torre-espia-no-roque-nao-atravessa-por-pouco",
            descricao="A MESMA fita com a janela de um lance só: o roque leva a "
            "torre a f1, que é a 1a fileira das brancas (a dela, e não a do outro "
            "lado). A chegada à 8a cai fora da janela.",
            tipo="xadrez_espia_atravessar",
            js_posicao=torre,
            lances=["e1g1", "f8e7", "f1f8"],
            chegada=chegada_do_tipo("xadrez_espia_atravessar", n=1),
            veredito="nao_cumpriu",
            confere={"espia_na_ultima_fileira": 0, "lances_do_jogador": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-peao-espiao-promovido-come",
            descricao="O peão espião vira dama em b8, e é a DAMA nova que desce a "
            "coluna e come o cavalo de b1: a marca passou para a peça nova.",
            tipo="xadrez_espia_comer",
            js_posicao=peao,
            lances=["b7b8q", "h8h7", "b8b1"],
            chegada=chegada_do_tipo("xadrez_espia_comer", n=2, k=1),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"capturas_da_espia": 1, "pecas_comidas_cavalo": 1},
            caso_obrigatorio="peao_espiao_promovido",
        ),
        vetor(
            motor,
            identificador="xadrez-peao-espiao-promovido-atravessa",
            descricao="A promoção em b8 é a chegada à 8a fileira: o marco cai no "
            "próprio lance da promoção.",
            tipo="xadrez_espia_atravessar",
            js_posicao=peao,
            lances=["b7b8q"],
            chegada=chegada_do_tipo("xadrez_espia_atravessar", n=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"espia_na_ultima_fileira": 1},
            caso_obrigatorio="peao_espiao_promovido",
        ),
        vetor(
            motor,
            identificador="xadrez-xeque-descoberto-da-espia",
            descricao="O bispo espião de a1 está atrás do cavalo de d4, na "
            "diagonal do rei preto. O cavalo sai, e o xeque é do BISPO, que não "
            "andou: conta como xeque da espiã (RF-XDR-195).",
            tipo="xadrez_espia_xeque",
            js_posicao=posicao(FEN_DESCOBERTO, marcas={"espia": "a1"}),
            lances=["d4b5"],
            chegada=chegada_do_tipo("xadrez_espia_xeque", n=1, k=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"xeques_da_espia": 1},
            caso_obrigatorio="xeque_descoberto_da_espia",
        ),
        vetor(
            motor,
            identificador="xadrez-xeque-descoberto-nao-e-da-peca-que-andou",
            descricao="O MESMO lance com o CAVALO como espião: o xeque saiu do "
            "lance dele, e não é dele. Quem contasse 'o lance da espiã deu xeque' "
            "diria cumpriu.",
            tipo="xadrez_espia_xeque",
            js_posicao=posicao(FEN_DESCOBERTO, marcas={"espia": "d4"}),
            lances=["d4b5"],
            chegada=chegada_do_tipo("xadrez_espia_xeque", n=1, k=1),
            veredito="nao_cumpriu",
            confere={"xeques_da_espia": 0, "maior_sequencia_de_xeques": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-espia-come-o-alvo",
            descricao="O cavalo espião de c3 come a torre marcada como alvo em b5.",
            tipo="xadrez_espia_alvo",
            js_posicao=posicao(FEN_ALVO, marcas={"espia": "c3", "alvo": "b5"}),
            lances=["c3b5"],
            chegada=chegada_do_tipo("xadrez_espia_alvo", n=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"alvo_comido_pela_espia": 1, "capturas_da_espia": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-alvo-comido-por-outra-peca",
            descricao="A espiã come um peão, e quem come a torre-alvo é a torre "
            "branca: o alvo saiu do tabuleiro, mas não pela espiã.",
            tipo="xadrez_espia_alvo",
            js_posicao=posicao(FEN_ALVO, marcas={"espia": "c3", "alvo": "b5"}),
            lances=["c3a4", "e8d7", "b1b5"],
            chegada=chegada_do_tipo("xadrez_espia_alvo", n=3),
            veredito="nao_cumpriu",
            confere={
                "alvo_comido_pela_espia": 0,
                "capturas_da_espia": 1,
                "pecas_comidas_torre": 1,
            },
        ),
        vetor(
            motor,
            identificador="xadrez-espia-preta-atravessa",
            descricao="A pessoa joga de PRETAS: a última fileira dela é a 1a. A "
            "torre espiã desce a coluna h até h1.",
            tipo="xadrez_espia_atravessar",
            js_posicao=posicao(FEN_PRETAS, cor="preta", marcas={"espia": "h8"}),
            lances=["h8h1"],
            chegada=chegada_do_tipo("xadrez_espia_atravessar", n=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"espia_na_ultima_fileira": 1, "xeques_da_espia": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-espia-come-e-e-comida",
            descricao="O bispo espião come o cavalo de f6, e o peão de g7 o come "
            "de volta. Faltava uma captura, e com a espiã fora do tabuleiro o "
            "desafio fecha como não cumprido: a 2a captura não viria nunca mais.",
            tipo="xadrez_espia_comer",
            js_posicao=posicao(FEN_TROCA_COMENDO, marcas={"espia": "b2"}),
            lances=["b2f6", "g7f6", "e1d1"],
            chegada=chegada_do_tipo("xadrez_espia_comer", n=2, k=2),
            veredito="nao_cumpriu",
            confere={"capturas_da_espia": 1, "espia_comida": 1},
        ),
    ]


def vetores_da_troca(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """A troca nas duas ordens (RF-XDR-200 a 202)."""
    bispo_por_cavalo = {"minha": "bispo", "dele": "cavalo"}
    oferecida = posicao(FEN_TROCA_OFERECIDA, troca=bispo_por_cavalo)
    comendo = posicao(FEN_TROCA_COMENDO, troca=bispo_por_cavalo)
    return [
        vetor(
            motor,
            identificador="xadrez-troca-ordem-1-oferece-e-retoma",
            descricao="Ordem 1: a pessoa põe o bispo em e4, o cavalo preto o come, "
            "e a torre branca come o cavalo. A troca conta no lance da retomada.",
            tipo="xadrez_troca",
            js_posicao=oferecida,
            lances=["b1e4", "f6e4", "a4e4"],
            chegada=chegada_do_tipo("xadrez_troca", n=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"trocas_feitas": 1, "pecas_perdidas_bispo": 1, "pecas_comidas_cavalo": 1},
            caso_obrigatorio="troca_ordem_1",
        ),
        vetor(
            motor,
            identificador="xadrez-troca-ordem-1-sem-retomar-nao-cumpre",
            descricao="A MESMA oferta, e a pessoa não retoma: perdeu o bispo e "
            "não trocou nada.",
            tipo="xadrez_troca",
            js_posicao=oferecida,
            lances=["b1e4", "f6e4", "e1f1"],
            chegada=chegada_do_tipo("xadrez_troca", n=2),
            veredito="nao_cumpriu",
            confere={"trocas_feitas": 0, "pecas_perdidas_bispo": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-troca-ordem-2-com-retomada",
            descricao="Ordem 2: o bispo come o cavalo em f6, e o peão de g7 "
            "retoma. A troca conta já no lance da captura.",
            tipo="xadrez_troca",
            js_posicao=comendo,
            lances=["b2f6", "g7f6"],
            chegada=chegada_do_tipo("xadrez_troca", n=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"trocas_feitas": 1},
            caso_obrigatorio="troca_ordem_2",
        ),
        vetor(
            motor,
            identificador="xadrez-troca-ordem-2-sem-retomada",
            descricao="O bispo come o cavalo, e o preto não retoma: conta como "
            "cumprido do mesmo jeito (RF-XDR-201).",
            tipo="xadrez_troca",
            js_posicao=comendo,
            lances=["b2f6", "e8d7"],
            chegada=chegada_do_tipo("xadrez_troca", n=1),
            veredito="cumpriu",
            lance_que_cumpre=1,
            confere={"trocas_feitas": 1, "pecas_perdidas_bispo": 0},
            caso_obrigatorio="troca_ordem_2_sem_retomada",
        ),
        vetor(
            motor,
            identificador="xadrez-troca-par-errado",
            descricao="A MESMA captura com o par torre por torre: comer um cavalo "
            "com um bispo não é trocar torre.",
            tipo="xadrez_troca",
            js_posicao=posicao(FEN_TROCA_COMENDO, troca={"minha": "torre", "dele": "torre"}),
            lances=["b2f6", "g7f6"],
            chegada=chegada_do_tipo("xadrez_troca", n=1),
            veredito="nao_cumpriu",
            confere={"trocas_feitas": 0},
        ),
    ]


def vetores_dos_xeques(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """Os xeques seguidos, a repetição tripla no meio deles, e os recebidos."""
    xeques = posicao(FEN_XEQUES)
    return [
        vetor(
            motor,
            identificador="xadrez-xeques-seguidos-ate-a-repeticao",
            descricao="Quatro xeques seguidos da dama, vai e vem. O 4o cai no "
            "lance 7; no 8 o rei volta a h8, a posição do início aparece pela 3a "
            "vez, e o motor empata por repetição. O objetivo caiu antes.",
            tipo="xadrez_xeques_seguidos",
            js_posicao=xeques,
            lances=VAI_E_VEM,
            chegada=chegada_do_tipo("xadrez_xeques_seguidos", n=6, k=4),
            veredito="cumpriu",
            lance_que_cumpre=7,
            confere={"maior_sequencia_de_xeques": 4, "empate": 0},
            caso_obrigatorio="repeticao_tripla_nos_xeques_seguidos",
        ),
        vetor(
            motor,
            identificador="xadrez-xeques-seguidos-a-repeticao-empata-antes-do-5o",
            descricao="A MESMA fita pedindo cinco: a repetição tripla encerra a "
            "partida antes do 5o xeque (é por isso que o tipo vai no máximo a 4, "
            "PRD §8.4). A sequência para em 4, e a partida termina empatada.",
            tipo="xadrez_xeques_seguidos",
            js_posicao=xeques,
            lances=VAI_E_VEM,
            chegada=chegada_do_tipo("xadrez_xeques_seguidos", n=6, k=5),
            veredito="nao_cumpriu",
            confere={"maior_sequencia_de_xeques": 4, "empate": 1, "vitoria": 0},
            caso_obrigatorio="repeticao_tripla_nos_xeques_seguidos",
        ),
        vetor(
            motor,
            identificador="xadrez-lance-depois-da-repeticao-e-dado-invalido",
            descricao="A MESMA fita com o 5o xeque DEPOIS do empate: o motor "
            "recusa (partida terminada), e a fita não é a gravação de uma "
            "partida. Dado inválido, e não 'não cumpriu'.",
            tipo="xadrez_xeques_seguidos",
            js_posicao=xeques,
            lances=VAI_E_VEM + ["d5d4"],
            chegada=chegada_do_tipo("xadrez_xeques_seguidos", n=6, k=4),
            veredito="dado_invalido",
            caso_obrigatorio="repeticao_tripla_nos_xeques_seguidos",
        ),
        vetor(
            motor,
            identificador="xadrez-xeques-interrompidos-nao-somam",
            descricao="Xeque, um lance da dama sem xeque, e xeque de novo: são "
            "dois xeques, e nenhum par SEGUIDO. A sequência é 1.",
            tipo="xadrez_xeques_seguidos",
            js_posicao=xeques,
            lances=["d5d4", "h8g8", "d4d1", "g8h8", "d1d4"],
            chegada=chegada_do_tipo("xadrez_xeques_seguidos", n=3, k=2),
            veredito="nao_cumpriu",
            confere={"maior_sequencia_de_xeques": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-sem-levar-xeque-cumpre",
            descricao="Dois lances de abertura, nenhum xeque do adversário.",
            tipo="xadrez_sem_levar_xeque",
            js_posicao=posicao(None),
            lances=["e2e4", "e7e5", "g1f3", "b8c6"],
            chegada=chegada_do_tipo("xadrez_sem_levar_xeque", n=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"xeques_recebidos": 0},
        ),
        vetor(
            motor,
            identificador="xadrez-sem-levar-xeque-leva-mate",
            descricao="O mate do louco: a dama preta dá xeque-mate em h4 no 4o "
            "meio-lance. A pessoa levou xeque e nem chegou ao 3o lance.",
            tipo="xadrez_sem_levar_xeque",
            js_posicao=posicao(None),
            lances=["f2f3", "e7e5", "g2g4", "d8h4"],
            chegada=chegada_do_tipo("xadrez_sem_levar_xeque", n=3),
            veredito="nao_cumpriu",
            confere={"xeques_recebidos": 1, "lances_do_jogador": 2, "vitoria": 0},
        ),
    ]


def vetores_das_pecas(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """Comer com a classe marcada, não perder peças, e o mate."""
    cavalo_come_peao = {"come": "cavalo", "comida": "peao"}
    return [
        vetor(
            motor,
            identificador="xadrez-comer-com-o-cavalo",
            descricao="O cavalo come o peão de a4 e depois o de c5: dois peões "
            "comidos pelo cavalo.",
            tipo="xadrez_comer_com",
            js_posicao=posicao(FEN_COMER_COM, classes=cavalo_come_peao),
            lances=["c3a4", "e8d8", "a4c5"],
            chegada=chegada_do_tipo("xadrez_comer_com", n=2, k=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"capturas_da_classe_marcada": 2, "pecas_comidas_peao": 2},
        ),
        vetor(
            motor,
            identificador="xadrez-comer-com-outra-peca-nao-conta",
            descricao="O cavalo come o 1o peão, e o BISPO come o 2o: dois peões "
            "comidos, um só pelo cavalo.",
            tipo="xadrez_comer_com",
            js_posicao=posicao(FEN_COMER_COM, classes=cavalo_come_peao),
            lances=["c3a4", "e8d8", "f2c5"],
            chegada=chegada_do_tipo("xadrez_comer_com", n=2, k=2),
            veredito="nao_cumpriu",
            confere={"capturas_da_classe_marcada": 1, "pecas_comidas_peao": 2},
        ),
        vetor(
            motor,
            identificador="xadrez-nao-perder-peao-cumpre",
            descricao="Três lances de abertura sem perder peão.",
            tipo="xadrez_nao_perder",
            js_posicao=posicao(None),
            lances=["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],
            chegada=chegada_do_tipo("xadrez_nao_perder", n=3, peca="peao"),
            veredito="cumpriu",
            lance_que_cumpre=5,
            confere={"pecas_perdidas_peao": 0},
        ),
        vetor(
            motor,
            identificador="xadrez-nao-perder-peao-perde",
            descricao="O peão de d5 come o de e4 antes do 3o lance da pessoa.",
            tipo="xadrez_nao_perder",
            js_posicao=posicao(None),
            lances=["e2e4", "d7d5", "g1f3", "d5e4", "f3g5"],
            chegada=chegada_do_tipo("xadrez_nao_perder", n=3, peca="peao"),
            veredito="nao_cumpriu",
            confere={"pecas_perdidas_peao": 1, "lances_do_jogador": 3},
        ),
        vetor(
            motor,
            identificador="xadrez-dar-mate-em-4",
            descricao="O mate do pastor: a dama come em f7 no 4o lance da pessoa, "
            "dentro dos cinco.",
            tipo="xadrez_dar_mate",
            js_posicao=posicao(None),
            lances=["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"],
            chegada=chegada_do_tipo("xadrez_dar_mate", n=5),
            veredito="cumpriu",
            lance_que_cumpre=7,
            confere={"vitoria": 1, "lances_do_jogador": 4},
        ),
        vetor(
            motor,
            identificador="xadrez-dar-mate-no-6o-lance-nao-cumpre",
            descricao="O mesmo mate com dois lances de espera: ele cai no 6o "
            "lance da pessoa, um depois da janela.",
            tipo="xadrez_dar_mate",
            js_posicao=posicao(None),
            lances=[
                "e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "a7a6",
                "a2a3", "a6a5", "b2b3", "h7h6", "h5f7",
            ],
            chegada=chegada_do_tipo("xadrez_dar_mate", n=5),
            veredito="nao_cumpriu",
            confere={"vitoria": 0, "lances_do_jogador": 5},
        ),
        vetor(
            motor,
            identificador="xadrez-lance-ilegal-e-dado-invalido",
            descricao="Um peão que anda três casas: o motor recusa o lance, e a "
            "fita é dado inválido.",
            tipo="xadrez_dar_mate",
            js_posicao=posicao(None),
            lances=["e2e5"],
            chegada=chegada_do_tipo("xadrez_dar_mate", n=5),
            veredito="dado_invalido",
        ),
    ]


#: A oferta da ordem 1 com um 2º cavalo preto em a5, ao alcance da torre de a4.
FEN_TROCA_COM_OUTRO_CAVALO = "4k3/8/5n2/n7/R7/8/8/1B2K3 w - - 0 1"
#: Cavalo branco em c3 e um bispo preto em b5, que o cavalo pode comer.
FEN_CAVALO_E_BISPO = "4k3/8/8/1b6/8/2N5/8/4K3 w - - 0 1"


def vetores_da_t070(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """Dois vetores que a T070 pediu (20/11/2026), no fim para o diff ser acréscimo.

    As mutações do medidor do APP (`medidor_desafio_xadrez.dart`) mostraram duas
    regras que os 32 primeiros não separavam: no servidor elas já tinham teste
    de unidade com fatos escritos à mão, mas o lado do app só tem os vetores (o
    estado dele vem do motor). Aqui viram vetores, e valem para os dois lados.
    """
    return [
        vetor(
            motor,
            identificador="xadrez-troca-ordem-1-comendo-outro-cavalo",
            descricao="O cavalo de f6 come o bispo oferecido em e4, e a torre "
            "come OUTRO cavalo, o de a5. A ordem 1 pede comer a peça que comeu, "
            "na casa em que ela parou: não houve troca.",
            tipo="xadrez_troca",
            js_posicao=posicao(
                FEN_TROCA_COM_OUTRO_CAVALO, troca={"minha": "bispo", "dele": "cavalo"}
            ),
            lances=["b1e4", "f6e4", "a4a5"],
            chegada=chegada_do_tipo("xadrez_troca", n=2),
            veredito="nao_cumpriu",
            confere={"trocas_feitas": 0, "pecas_comidas_cavalo": 1, "pecas_perdidas_bispo": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-comer-com-o-cavalo-um-bispo-nao-e-peao",
            descricao="'Coma peões com o cavalo', e o cavalo come um BISPO: a "
            "peça que come é a certa, a comida não.",
            tipo="xadrez_comer_com",
            js_posicao=posicao(FEN_CAVALO_E_BISPO, classes={"come": "cavalo", "comida": "peao"}),
            lances=["c3b5"],
            chegada=chegada_do_tipo("xadrez_comer_com", n=1, k=1),
            veredito="nao_cumpriu",
            confere={"capturas_da_classe_marcada": 0, "pecas_comidas_bispo": 1},
        ),
    ]


#: Cavalo branco em c3 e bispo branco em f2 (as duas espias); torre preta em f8,
#: na coluna do bispo, e peao preto em a4, que o cavalo come. O rei preto em a8.
FEN_DUAS_ESPIAS_E_A_TORRE = "k4r2/8/8/8/p7/2N5/5B2/4K3 w - - 0 1"


def vetores_das_duas_espias(motor: JogadorXadrez) -> list[dict[str, Any]]:
    """As duas espias (21/11/2026, `DECISOES-do-dono.md` §8zzzz64), no fim.

    As medidas da espia valem para as DUAS marcas (`espia` e `espia2`): as
    capturas somam ("vale o total", ate de uma so), e qualquer uma comida fecha
    o desafio. Os vetores de uma espia so, acima, nao mudaram um byte ao
    regerar: e a prova de que, com uma espia, a conta e a de antes.
    """
    duas = posicao(FEN_COMER_COM, marcas={"espia": "c3", "espia2": "f2"})
    return [
        vetor(
            motor,
            identificador="xadrez-duas-espias-somam-as-capturas",
            descricao="O cavalo espiao come o peao de a4, e o bispo espiao, o de "
            "c5: uma captura de cada, e as duas somam as 2 do desafio.",
            tipo="xadrez_duas_espias",
            js_posicao=duas,
            lances=["c3a4", "e8d8", "f2c5"],
            chegada=chegada_do_tipo("xadrez_duas_espias", n=3, k=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"capturas_da_espia": 2, "pecas_comidas_peao": 2, "espia_comida": 0},
        ),
        vetor(
            motor,
            identificador="xadrez-duas-espias-uma-so-tambem-vale",
            descricao="A MESMA posicao, e o cavalo espiao come os dois peoes "
            "(a4, depois c5): vale o total, e nao se exige que cada espia coma.",
            tipo="xadrez_duas_espias",
            js_posicao=duas,
            lances=["c3a4", "e8d8", "a4c5"],
            chegada=chegada_do_tipo("xadrez_duas_espias", n=3, k=2),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"capturas_da_espia": 2},
        ),
        vetor(
            motor,
            identificador="xadrez-duas-espias-a-segunda-comida-encerra",
            descricao="A torre preta come o bispo, que e a SEGUNDA espia, e o "
            "cavalo espiao come o peao depois: a captura nao salva mais nada, "
            "porque 'nenhuma espia comida' vale para as duas.",
            tipo="xadrez_duas_espias",
            js_posicao=posicao(
                FEN_DUAS_ESPIAS_E_A_TORRE, marcas={"espia": "c3", "espia2": "f2"}
            ),
            lances=["e1d1", "f8f2", "c3a4"],
            chegada=chegada_do_tipo("xadrez_duas_espias", n=3, k=1),
            veredito="nao_cumpriu",
            confere={"espia_comida": 1, "capturas_da_espia": 1, "pecas_perdidas_bispo": 1},
        ),
        vetor(
            motor,
            identificador="xadrez-uma-espia-a-outra-peca-nao-conta",
            descricao="O controle do de cima, com UMA espia: o bispo de f2 nao e "
            "espia, e a torre o come sem violar nada. O cavalo espiao come o "
            "peao, e o desafio de uma espia so cumpre.",
            tipo="xadrez_espia_comer",
            js_posicao=posicao(FEN_DUAS_ESPIAS_E_A_TORRE, marcas={"espia": "c3"}),
            lances=["e1d1", "f8f2", "c3a4"],
            chegada=chegada_do_tipo("xadrez_espia_comer", n=3, k=1),
            veredito="cumpriu",
            lance_que_cumpre=3,
            confere={"espia_comida": 0, "capturas_da_espia": 1, "pecas_perdidas_bispo": 1},
        ),
    ]


def montar(motor: JogadorXadrez) -> dict[str, Any]:
    """O documento inteiro, com os vetores em ordem estável.

    ⚠️ **Ordem estável importa**: as duas cópias são comparadas byte a byte, e
    vetor novo entra NO FIM, para o diff do dia ser acréscimo.
    """
    vetores = (
        vetores_da_espia(motor)
        + vetores_da_troca(motor)
        + vetores_dos_xeques(motor)
        + vetores_das_pecas(motor)
        # Os dois que as mutações do medidor do app pediram (T070), no fim.
        + vetores_da_t070(motor)
        # As duas espias (21/11/2026, no lugar da troca), no fim de novo.
        + vetores_das_duas_espias(motor)
    )
    identificadores = [v["id"] for v in vetores]
    assert len(set(identificadores)) == len(identificadores), "há id repetido"
    faltam = set(CASOS_OBRIGATORIOS) - {v["caso_obrigatorio"] for v in vetores}
    assert not faltam, f"casos obrigatórios sem vetor: {sorted(faltam)}"
    return {
        "de_documento": "Vetores do juiz do xadrez (spec 012, T069; contracts/"
        "desafio-xadrez.md §3): a fita com os fatos do motor, as medidas e o "
        "veredito. GERADO por scripts/gerar_vetores_juiz_xadrez.py - nao edite a "
        "mao. Vetor nunca e apagado nem editado: corrigir e vetor NOVO.",
        "versao": VERSAO,
        "casos_obrigatorios": list(CASOS_OBRIGATORIOS),
        "chaves_das_medidas": list(feitos_xadrez.CHAVES_DAS_MEDIDAS),
        "vetores": vetores,
    }


def main() -> int:
    with JogadorXadrez() as motor:
        documento = montar(motor)
    # `newline=""` e o `\n` explícito: as cópias são comparadas por SHA-256
    # entre repositórios, e o Windows converteria LF em CRLF num `write_text`.
    texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"
    for destino in (COPIA_DAQUI, COPIA_DO_APP):
        if destino == COPIA_DO_APP and not FRONTEND.is_dir():
            print(f"pulado (sem o repositório do app ao lado): {destino}")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8", newline="") as arquivo:
            arquivo.write(texto)
        print(f"escrito: {destino} ({len(texto.encode('utf-8'))} bytes)")
    print(f"{len(documento['vetores'])} vetores, versão {VERSAO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
