"""A FRASE DO DESAFIO, em portugues, como a pessoa a le no aplicativo (T040b).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate 16/09/2026 o painel de curadoria mostrava o objetivo assim:

    objetivo  desafioObjetivoPaciencia {'lances': 3, 'variante': 'pequeno', ...}

⚠️ **E o dono precisou PERGUNTAR o que aquilo queria dizer**, no meio de uma
sessao: *"Me explique tambem qual o objetivo do desafio de paciencia"*. Depois ele
pediu, com todas as letras: *"Eu gostaria de ver no painel de curadoria tambem a
frase completa de cada desafio, como o usuario ira le-la no App, em pt-br
apenas."*

⛔ **E o pedido e maior do que parece: a frase E parte do desafio.** Um desafio
cuja chegada esta perfeita e cujo enunciado e ambiguo e um desafio ruim, e a
curadoria nao tinha como ver isso. ⚠️ Foi exatamente assim que a `damas_sobreviver`
ganhou o teto de perdas na frase, em 15/09 — alguem leu a frase e viu que faltava.

═══════════════════════════════════════════════════════════════════════════
⛔ DE ONDE VEM O TEXTO, E POR QUE HA UMA COPIA
═══════════════════════════════════════════════════════════════════════════

A fonte da verdade e `arena-sagaz-frontend/lib/l10n/app_pt.arb`. ⛔ **Mas o painel
roda dentro da imagem da API**, onde o repositorio do aplicativo nao existe — ler
o `.arb` em runtime funcionaria na maquina do dono e falharia em producao, que e
o pior modo de falhar que ha.

✅ **Entao ha uma copia**, `contratos/frases_objetivo_pt.json`, gerada por
`scripts/gerar_frases_objetivo.py` e travada por
`tests/unitarios/test_frases_objetivo.py`, que compara com o `.arb` e **falha**
quando divergem. ⚠️ E o mesmo padrao do contrato da CNN e dos vetores de
verificacao — o projeto ja resolveu este problema duas vezes, e do mesmo jeito.

⚠️ **So o portugues.** O painel e ferramenta interna de uma pessoa so; carregar
tres idiomas triplicaria a copia para servir ninguem.

═══════════════════════════════════════════════════════════════════════════
⚠️ O FORMATO E ICU, E ELE NAO E DECORATIVO
═══════════════════════════════════════════════════════════════════════════

    '{damas, plural, =1{Coroe 1 dama} other{Coroe {damas} damas}} em ate ...'

O plural existe porque *"Coroe 1 damas"* e errado em portugues, e o `.arb` ja
resolve isso para o aplicativo. ⛔ **Renderizar com um `str.format()` simples
imprimiria as chaves do plural na tela**, e a frase do painel deixaria de ser *"a
frase como o usuario a le"* — que e a unica coisa que ela precisa ser.

⚠️ **Este renderizador cobre o que os `.arb` do projeto usam, e nao o ICU
inteiro:** `{var}` e `{var, plural, =N{...} other{...}}`, com `{var}` dentro do
ramo. ⛔ Ele **levanta** diante do que nao conhece, em vez de imprimir lixo —
`select`, `plural` com `offset` ou aninhamento de dois niveis param aqui, e o
teste avisa antes de o painel mostrar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional

#: A copia das frases, ao lado dos outros contratos do backend.
CAMINHO_DAS_FRASES = (
    Path(__file__).resolve().parents[3] / "contratos" / "frases_objetivo_pt.json"
)

#: O prefixo das chaves que descrevem objetivo de desafio.
PREFIXO = "desafioObjetivo"


class FraseInvalida(ValueError):
    """A frase usa um recurso de ICU que este renderizador nao cobre."""


def carregar_frases(caminho: Optional[Path] = None) -> dict[str, str]:
    """As frases de objetivo em portugues, por chave.

    ⚠️ **Arquivo ausente devolve vazio, e nao estoura.** O painel tem de abrir
    mesmo assim: sem a copia ele volta a mostrar a chave crua, que e o
    comportamento de antes — ⛔ e uma ferramenta de curadoria que nao abre e pior
    que uma que mostra menos.
    """
    alvo = caminho or CAMINHO_DAS_FRASES
    if not alvo.exists():
        return {}
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    return {chave: texto for chave, texto in dados.items() if not chave.startswith("@")}


def _um_nivel(texto: str, inicio: int) -> tuple[str, int]:
    """Le um `{...}` equilibrado a partir de `inicio`, devolvendo (miolo, fim).

    ⚠️ **Contar chaves, e nao procurar o proximo `}`.** Os ramos do plural contem
    `{damas}` dentro, entao o primeiro `}` que aparece quase nunca e o certo — e
    um regex ganancioso engoliria a frase inteira.
    """
    if texto[inicio] != "{":
        raise FraseInvalida(f"esperava `{{` na posicao {inicio}: {texto!r}")
    nivel = 0
    for posicao in range(inicio, len(texto)):
        if texto[posicao] == "{":
            nivel += 1
        elif texto[posicao] == "}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio + 1 : posicao], posicao + 1
    raise FraseInvalida(f"chave `{{` sem fechamento: {texto!r}")


#: `damas, plural, ` — o cabecalho de um bloco de plural.
_CABECALHO_PLURAL = re.compile(r"^\s*(\w+)\s*,\s*(\w+)\s*,\s*")


def _ramos_do_plural(corpo: str) -> dict[str, str]:
    """Os ramos `=1{...}` / `other{...}` de um bloco de plural, por rotulo."""
    ramos: dict[str, str] = {}
    posicao = 0
    while posicao < len(corpo):
        if corpo[posicao].isspace():
            posicao += 1
            continue
        fim_do_rotulo = corpo.find("{", posicao)
        if fim_do_rotulo == -1:
            raise FraseInvalida(f"ramo sem corpo em {corpo!r}")
        rotulo = corpo[posicao:fim_do_rotulo].strip()
        miolo, posicao = _um_nivel(corpo, fim_do_rotulo)
        ramos[rotulo] = miolo
    return ramos


def renderizar(frase: str, valores: Mapping[str, Any]) -> str:
    """A frase ICU com os valores aplicados.

    Args:
        frase: o texto como esta no `.arb`.
        valores: os parametros do desafio (`js_objetivo`).

    Returns:
        A frase pronta, como a pessoa a le no aplicativo.

    Raises:
        FraseInvalida: recurso de ICU nao coberto, ou placeholder sem valor.

    ⛔ **Placeholder sem valor LEVANTA**, em vez de virar texto vazio. Uma frase
    *"Coroe damas em ate 6 lances"* e pior que um erro: ela parece certa, e so o
    numero que importa some.
    """
    saida: list[str] = []
    posicao = 0
    while posicao < len(frase):
        caractere = frase[posicao]
        if caractere != "{":
            saida.append(caractere)
            posicao += 1
            continue

        miolo, posicao = _um_nivel(frase, posicao)
        cabecalho = _CABECALHO_PLURAL.match(miolo)

        # ── Caso 1: `{personagem}` — substituicao direta ──────────────────
        if cabecalho is None:
            nome = miolo.strip()
            if nome not in valores:
                raise FraseInvalida(f"sem valor para `{nome}` em {frase!r}")
            saida.append(str(valores[nome]))
            continue

        # ── Caso 2: `{damas, plural, =1{...} other{...}}` ─────────────────
        nome, tipo = cabecalho.group(1), cabecalho.group(2)
        if tipo != "plural":
            # ⛔ `select`, `selectordinal` e o resto do ICU param aqui — de
            # proposito. Ver o cabecalho do modulo.
            raise FraseInvalida(f"`{tipo}` nao e suportado (chave `{nome}`)")
        if nome not in valores:
            raise FraseInvalida(f"sem valor para `{nome}` em {frase!r}")

        ramos = _ramos_do_plural(miolo[cabecalho.end() :])
        quantidade = valores[nome]
        # ⚠️ `=1` ganha de `one`/`other`, como manda o ICU: o ramo exato e mais
        # especifico que a categoria.
        escolhido = ramos.get(f"={quantidade}")
        if escolhido is None:
            escolhido = ramos.get("one" if quantidade == 1 else "other")
        if escolhido is None:
            escolhido = ramos.get("other")
        if escolhido is None:
            raise FraseInvalida(f"plural sem ramo aplicavel para {quantidade}")

        # ⚠️ Recursivo: o ramo escolhido ainda pode ter `{damas}` dentro.
        saida.append(renderizar(escolhido, valores))

    return "".join(saida)


def frase_do_desafio(
    co_chave_objetivo: str,
    js_objetivo: Mapping[str, Any],
    *,
    frases: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """A frase pronta daquele desafio, ou `None` quando nao da para montar.

    Args:
        co_chave_objetivo: a chave do `.arb` (`desafioObjetivoCoroarEmLances`).
        js_objetivo: os parametros gravados com o desafio.
        frases: a tabela de frases; le do disco quando omitida.

    ⚠️ **Devolve `None` em vez de estourar**, e o painel mostra a chave crua nesse
    caso. ⛔ Uma chave nova no aplicativo antes de a copia ser regerada nao pode
    derrubar a pagina de curadoria — e o cadeado do teste ja avisa que a copia
    envelheceu, que e o lugar certo para esse aviso.

    ⚠️ **O personagem entra com inicial maiuscula.** No banco ele e `magno`
    (codigo); na tela do aplicativo e **Magno** (nome proprio), e a frase diz
    *"contra {personagem}"*.
    """
    tabela = carregar_frases() if frases is None else frases
    modelo = tabela.get(co_chave_objetivo)
    if modelo is None:
        return None

    valores = dict(js_objetivo)
    personagem = valores.get("personagem")
    if isinstance(personagem, str):
        valores["personagem"] = personagem[:1].upper() + personagem[1:]

    try:
        return renderizar(modelo, valores)
    except FraseInvalida:
        # ⚠️ O painel continua abrindo; o teste e quem grita.
        return None
