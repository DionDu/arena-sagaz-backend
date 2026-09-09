r"""A avaliação **treinada**: o arquivo de pesos, o leitor dele e a nota.

O que este módulo é
-------------------
A etapa 7 treinou cinco tabelas de padrões (`../treino/regressao_logistica_damas.py`).
Treinar acontece no PC, com `numpy`, em `float64`. **Jogar acontece no aparelho**,
e lá não há `numpy`, nem `.npz`, nem `float64` sobrando. Este módulo é a ponte:

1. define o **formato do arquivo** `pesos_padroes_<modalidade>.bin` — o único
   artefato que o app carrega;
2. **lê** esse arquivo de volta para tabelas densas;
3. **avalia** uma posição somando as nove leituras, em centésimos de pedra.

⚠️ Ele é escrito de propósito **sem `numpy`**
----------------------------------------------
Não é purismo. Este módulo é o **lado Python da escrituração dupla** com
`../motor_dart/lib/avaliacao_treinada_damas.dart`, e as duas implementações têm de
fazer a mesma conta com os mesmos tipos. `numpy` traria inteiros de largura fixa
que dão a volta em silêncio (`int16 + int16` continua `int16`), e o Dart não faz
isso — o `int` do Dart tem 64 bits. Usar `array("h")` do próprio Python dá o
melhor dos dois: **2 bytes por entrada na memória**, como no aparelho, e `int` de
precisão arbitrária ao indexar, como no Dart.

Por que o arquivo é ESPARSO
---------------------------
As cinco tabelas somam 1.953.125 entradas, e a rodada de 2.000 partidas encheu
**13.257** delas — 0,68%. Guardar o vetor denso custaria 3,73 MB de arquivo para
carregar 3,7 MB de zeros; guardar só os pares `(índice, valor)` custa cerca de
**80 KB**.

Repare que isso **não** contradiz a decisão de manter as tabelas densas em
memória: no disco o que importa é tamanho, e na RAM o que importa é que a leitura
seja um acesso a vetor. O leitor faz a expansão uma vez, na carga.

Por que a GEOMETRIA viaja dentro do arquivo
--------------------------------------------
As nove janelas (quais casas, em que ordem, qual tabela, se inverte o ponto de
vista) estão gravadas no próprio `.bin`, e o Dart as lê de lá em vez de trazer
uma cópia compilada.

É a lição do contrato de codificação do Jogo dos Pontinhos, aplicada mais cedo:
duas cópias de uma geometria divergem em silêncio, e o sintoma é uma avaliação
*plausível* e errada. Com a geometria dentro do arquivo, tabela e geometria não
podem se separar — elas são o mesmo byte-a-byte.

O formato, campo por campo
---------------------------
Tudo **little-endian**, sem preenchimento. `<` no `struct`, `Endian.little` no
Dart. Um dia num processador big-endian isto estoura na magia, que é o lugar certo
para estourar.

```
CABEÇALHO FIXO (50 bytes)
  0   8 bytes   magia "DAMAPAD\n"
  8   uint16    versão do layout (1)
 10   uint16    estados por casa (5)   ─┐ conferidos na leitura: um arquivo
 12   uint16    casas por janela (8)    │ gerado por outra geometria é recusado
 14   uint16    número de tabelas (5)   │ em vez de dar nota errada
 16   uint16    número de janelas (9)  ─┘
 18   uint32    entradas por tabela (390.625)
 22   float32   escala: centésimos de pedra por logit
 26   int16     viés
 28   4×int16   material: minhas pedras, minhas damas, pedras dele, damas dele
 36   int32     total de entradas não nulas  ─┐ soma de verificação: o leitor
 40   int64     soma de todos os valores     ─┘ reconta e recusa se divergir
 48   uint16    tamanho do nome do regulamento
 50   n bytes   o nome, em UTF-8 ("brasileira")

GEOMETRIA — uma vez por janela, na ordem em que a avaliação as soma
      uint16 + bytes   identificador ("L0C0")
      uint16 + bytes   nome da tabela ("T1")
      uint8            inverte o ponto de vista (0 ou 1)
      8×uint8          as oito casas jogáveis, na ORDEM DE LEITURA

TABELAS — uma vez por tabela
      uint16 + bytes   nome ("T1")
      int32            quantas entradas não nulas
      por entrada:  int32 índice, int16 valor
```

⚠️ Por que a magia termina em `\n`
-----------------------------------
Truque emprestado do PNG. Se alguém transferir o arquivo em modo texto entre
Windows e Unix, o `\n` viaja como `\r\n` e a magia deixa de bater — o arquivo é
recusado na primeira leitura em vez de ser aceito com todos os deslocamentos
deslizados em um byte. Corrupção que se anuncia vale muito mais que corrupção
silenciosa.

Como isto se relaciona com a avaliação escrita à mão
-----------------------------------------------------
`avaliacao_damas.py` (a manual) e este módulo têm a **mesma assinatura** de
propósito: `avaliar(tabuleiro)` devolve centésimos de pedra do ponto de vista de
quem tem a vez. É o que permite a arena da etapa 9 trocar uma pela outra e medir
a diferença em Elo — que é o critério que decide se este ramo inteiro se paga.

⚠️ Uma dependência que parece invertida, e é de propósito
----------------------------------------------------------
Este módulo mora em `motor/` e importa de `../treino/janelas_damas.py` — uma
pasta que, pelo nome, é de laboratório. A geometria das janelas **não é** de
treino: é do modelo, e o treino apenas foi o primeiro a precisar dela.

O lugar arquitetonicamente certo para `janelas_damas.py` seria aqui em `motor/`.
Ele ficou lá porque **dezoito arquivos** já o importam de `treino/` — incluindo o
gerador do contrato e sete figuras —, e mover para ganhar arrumação seria dezoito
edições de risco em troca de zero comportamento. Fica escrito aqui em vez de
esquecido: se um dia houver outro motivo para mexer nesse arquivo, ele muda de
pasta na mesma viagem.
"""
from __future__ import annotations

import struct
from array import array
from dataclasses import dataclass
from pathlib import Path

from jogos.jogo_damas.motor.tabuleiro_damas import Cor, Peca, Tabuleiro
from jogos.jogo_damas.treino.janelas_damas import (
    CASAS_POR_JANELA,
    ENTRADAS_POR_TABELA,
    ESTADOS_POR_CASA,
    JANELAS,
    TABELAS,
    Janela,
    estado_da_casa,
)

MAGIA = b"DAMAPAD\n"
"""Oito bytes que identificam o formato. Ver a nota sobre o `\\n` no cabeçalho."""

VERSAO = 1
"""Versão do **layout**. A magia diz "isto é um arquivo de padrões de damas"; a
versão diz "e está no arranjo número tal". Mudou a ordem dos campos? Sobe a
versão, e o leitor antigo recusa em vez de ler lixo."""

_CABECALHO = "<8sHHHHHIfh4hiqH"
"""O formato do cabeçalho fixo, para o `struct`. Ver a tabela no cabeçalho do
módulo. `<` é o que garante little-endian **e** ausência de preenchimento — sem
ele o `struct` alinharia os campos conforme a máquina, e o Dart leria torto."""

TAMANHO_DO_CABECALHO = struct.calcsize(_CABECALHO)
"""50 bytes. Calculado, nunca escrito à mão: um campo novo mudaria o número e a
constante decorada continuaria dizendo 50."""

COLUNAS_DE_MATERIAL = 4
"""minhas pedras · minhas damas · pedras dele · damas dele. A mesma ordem do
conjunto de treino, e ela é contrato: trocar duas colunas dá um motor que
prefere as peças do adversário."""


class ArquivoDePesosInvalido(ValueError):
    """O arquivo não é um `.bin` de padrões, ou não é o que este código espera.

    Exceção própria, e não `ValueError` cru, para que quem carrega possa
    distinguir "o arquivo está corrompido" de "o caminho está errado" — e para
    que a mensagem chegue ao usuário do app como falha de recurso, não como bug.
    """


@dataclass(frozen=True)
class PesosDosPadroes:
    """Os pesos já prontos para consultar, em centésimos de pedra.

    Attributes:
        tabelas: `{nome: array("h") de 390.625}`. Densas — a razão de existir
            deste formato é que consultar seja um acesso a vetor.
        janelas: a geometria **lida do arquivo**, não importada. Ver o cabeçalho.
        material: os quatro coeficientes, em centésimos.
        vies: o intercepto, em centésimos. É a vantagem de ter a vez, e é por
            isso que a nota treinada **não** é antissimétrica — ver
            `avaliar_absoluto`.
        escala_logito_para_centesimos: quantos centésimos de pedra vale um logit
            do modelo. Não entra na conta da nota (ela já está em centésimos);
            viaja no arquivo para que se possa voltar aos logits e, com eles, à
            probabilidade de vitória — que é o que a tela de análise mostraria.
        regulamento: a modalidade em que estes pesos foram treinados. Carregar os
            pesos das brasileiras num motor de anglo-americanas não daria erro
            nenhum, e é justamente por isso que o identificador viaja aqui.
    """

    tabelas: dict[str, array]
    janelas: tuple[Janela, ...]
    material: tuple[int, ...]
    vies: int
    escala_logito_para_centesimos: float
    regulamento: str

    def entradas_nao_nulas(self) -> int:
        """Quantas entradas de tabela têm peso. Serve à figura e ao relatório."""
        return sum(
            sum(1 for valor in tabela if valor != 0)
            for tabela in self.tabelas.values()
        )


# --------------------------------------------------------------------------- #
# Gravar
# --------------------------------------------------------------------------- #


def _bloco_com_tamanho(texto: str) -> bytes:
    """Um texto precedido do seu tamanho em `uint16`.

    Prefixar o tamanho, em vez de terminar com zero, é o que permite ao leitor
    saber quanto ler **antes** de ler — e é como o Dart consegue avançar pelo
    arquivo sem procurar terminadores.
    """
    cru = texto.encode("utf-8")
    return struct.pack("<H", len(cru)) + cru


def serializar(
    tabelas: dict[str, "list[int] | array"],
    material: "list[int] | tuple[int, ...]",
    vies: int,
    escala_logito_para_centesimos: float,
    regulamento: str,
) -> bytes:
    """Monta os bytes do arquivo de pesos.

    Args:
        tabelas: `{nome: sequência de 390.625 inteiros em centésimos}`. Aceita
            lista, `array` ou array de `numpy` — só se exige indexação e
            iteração, e é o que permite este módulo não importar `numpy`.
        material: os quatro coeficientes em centésimos.
        vies: o intercepto em centésimos.
        escala_logito_para_centesimos: o fator medido no treino.
        regulamento: identificador da modalidade.

    Raises:
        ValueError: se faltar tabela, se uma tabela tiver tamanho errado ou se o
            material não tiver quatro colunas. Falhar aqui é falhar na gravação,
            que é onde alguém está olhando — muito melhor que falhar no aparelho.
    """
    if set(tabelas) != set(TABELAS):
        raise ValueError(
            f"as tabelas do modelo {sorted(tabelas)} não são as esperadas "
            f"{sorted(TABELAS)}"
        )
    if len(material) != COLUNAS_DE_MATERIAL:
        raise ValueError(
            f"o material tem {len(material)} colunas; são {COLUNAS_DE_MATERIAL}"
        )

    # Primeiro os pares não nulos de cada tabela, porque o cabeçalho precisa
    # anunciar o total e a soma de verificação — e para isso é preciso já saber.
    pares_por_tabela: dict[str, list[tuple[int, int]]] = {}
    for nome in TABELAS:
        tabela = tabelas[nome]
        if len(tabela) != ENTRADAS_POR_TABELA:
            raise ValueError(
                f"a tabela {nome} tem {len(tabela)} entradas; são "
                f"{ENTRADAS_POR_TABELA}"
            )
        pares_por_tabela[nome] = [
            (indice, int(valor))
            for indice, valor in enumerate(tabela)
            if int(valor) != 0
        ]

    total = sum(len(pares) for pares in pares_por_tabela.values())
    soma = sum(valor for pares in pares_por_tabela.values() for _, valor in pares)

    partes = [struct.pack(
        _CABECALHO,
        MAGIA,
        VERSAO,
        ESTADOS_POR_CASA,
        CASAS_POR_JANELA,
        len(TABELAS),
        len(JANELAS),
        ENTRADAS_POR_TABELA,
        float(escala_logito_para_centesimos),
        int(vies),
        *(int(coeficiente) for coeficiente in material),
        total,
        soma,
        len(regulamento.encode("utf-8")),
    )]
    partes.append(regulamento.encode("utf-8"))

    for janela in JANELAS:
        partes.append(_bloco_com_tamanho(janela.identificador))
        partes.append(_bloco_com_tamanho(janela.tabela))
        partes.append(struct.pack("<B", 1 if janela.inverte_o_ponto_de_vista else 0))
        # As casas cabem em um byte cada (1 a 32) — e vão na ORDEM DE LEITURA,
        # que é o que define o índice. Ordenar aqui destruiria a tabela em
        # silêncio, e é o erro que a etapa 7 já quase cometeu uma vez.
        partes.append(bytes(janela.casas))

    for nome in TABELAS:
        partes.append(_bloco_com_tamanho(nome))
        pares = pares_por_tabela[nome]
        partes.append(struct.pack("<i", len(pares)))
        # Um `pack` por entrada, e não um `pack` gigante montado por formato
        # dinâmico: 13 mil chamadas são instantâneas, e o código fica igual ao
        # laço que o Dart executa do outro lado.
        for indice, valor in pares:
            partes.append(struct.pack("<ih", indice, valor))

    return b"".join(partes)


def gravar(
    caminho: Path,
    tabelas: dict[str, "list[int] | array"],
    material: "list[int] | tuple[int, ...]",
    vies: int,
    escala_logito_para_centesimos: float,
    regulamento: str,
) -> Path:
    """Serializa e escreve. Cria a pasta se ela não existir."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(serializar(
        tabelas, material, vies, escala_logito_para_centesimos, regulamento
    ))
    return caminho


# --------------------------------------------------------------------------- #
# Ler
# --------------------------------------------------------------------------- #


class _Leitor:
    """Um cursor sobre os bytes. Existe para o Dart poder ser igual.

    Podia ser um punhado de `struct.unpack_from` com deslocamentos calculados à
    mão, e seria mais curto — e mais frágil. Um cursor que avança sozinho é o que
    permite acrescentar um campo sem recontar cinquenta deslocamentos, e é
    exatamente o que a classe correspondente em Dart faz.
    """

    def __init__(self, cru: bytes) -> None:
        self._cru = cru
        self.posicao = 0

    def ler(self, formato: str) -> tuple:
        """Desempacota um formato do `struct` e avança o cursor."""
        tamanho = struct.calcsize(formato)
        if self.posicao + tamanho > len(self._cru):
            raise ArquivoDePesosInvalido(
                f"o arquivo acabou antes do esperado (queria {tamanho} bytes na "
                f"posição {self.posicao}, e ele tem {len(self._cru)})"
            )
        valores = struct.unpack_from(formato, self._cru, self.posicao)
        self.posicao += tamanho
        return valores

    def um(self, formato: str) -> int | float:
        """Um campo só, já fora da tupla — açúcar para o caso mais comum."""
        return self.ler(formato)[0]

    def texto(self) -> str:
        """Um bloco `uint16` + bytes, como `_bloco_com_tamanho` gravou."""
        tamanho = self.um("<H")
        return bytes(self.ler(f"<{tamanho}s")[0]).decode("utf-8")


def desserializar(cru: bytes) -> PesosDosPadroes:
    """Reconstrói os pesos a partir dos bytes, conferindo tudo que pode conferir.

    Cinco recusas possíveis, e cada uma existe porque o erro que ela pega daria
    uma avaliação **plausível e errada**:

    1. **magia diferente** — não é este formato (ou veio corrompido em modo texto);
    2. **versão diferente** — é este formato, em outro arranjo de campos;
    3. **geometria diferente** — outro número de janelas, casas ou estados: a
       tabela foi treinada com um recorte de tabuleiro que este código não usa;
    4. **contagem de entradas diferente** da anunciada no cabeçalho;
    5. **soma dos valores diferente** da anunciada — pega byte-order trocada e
       truncamento, os dois erros que não mudam o *tamanho* do arquivo.
    """
    leitor = _Leitor(cru)
    (
        magia, versao, estados, casas_por_janela, numero_de_tabelas,
        numero_de_janelas, entradas_por_tabela, escala, vies,
        material_0, material_1, material_2, material_3,
        total_anunciado, soma_anunciada, tamanho_do_regulamento,
    ) = leitor.ler(_CABECALHO)

    if magia != MAGIA:
        raise ArquivoDePesosInvalido(
            f"magia {magia!r} — esperava {MAGIA!r}. Se a diferença for um "
            "\\r\\n no fim, o arquivo foi transferido em modo texto."
        )
    if versao != VERSAO:
        raise ArquivoDePesosInvalido(
            f"versão de layout {versao}; este código lê a {VERSAO}"
        )
    if (estados, casas_por_janela, entradas_por_tabela) != (
        ESTADOS_POR_CASA, CASAS_POR_JANELA, ENTRADAS_POR_TABELA
    ):
        raise ArquivoDePesosInvalido(
            f"geometria do arquivo ({estados} estados, {casas_por_janela} casas "
            f"por janela, {entradas_por_tabela} entradas) diferente da deste "
            f"código ({ESTADOS_POR_CASA}, {CASAS_POR_JANELA}, "
            f"{ENTRADAS_POR_TABELA})"
        )
    if (numero_de_tabelas, numero_de_janelas) != (len(TABELAS), len(JANELAS)):
        raise ArquivoDePesosInvalido(
            f"o arquivo traz {numero_de_janelas} janelas em "
            f"{numero_de_tabelas} tabelas; este código usa {len(JANELAS)} em "
            f"{len(TABELAS)}"
        )

    regulamento = bytes(
        leitor.ler(f"<{tamanho_do_regulamento}s")[0]
    ).decode("utf-8")

    janelas = []
    for _ in range(numero_de_janelas):
        identificador = leitor.texto()
        nome_da_tabela = leitor.texto()
        inverte = bool(leitor.um("<B"))
        casas = tuple(leitor.ler(f"<{CASAS_POR_JANELA}B"))
        janelas.append(Janela(
            identificador=identificador,
            casas=casas,
            tabela=nome_da_tabela,
            inverte_o_ponto_de_vista=inverte,
        ))

    tabelas: dict[str, array] = {}
    total_lido = 0
    soma_lida = 0
    for _ in range(numero_de_tabelas):
        nome = leitor.texto()
        quantas = leitor.um("<i")
        # `array("h")` zerado e depois preenchido: é a expansão do esparso para o
        # denso, feita uma vez na carga. O aparelho paga 3,73 MB de RAM e ganha
        # leitura em tempo constante para o resto da partida.
        tabela = array("h", bytes(ENTRADAS_POR_TABELA * 2))
        for _ in range(quantas):
            indice, valor = leitor.ler("<ih")
            if not 0 <= indice < ENTRADAS_POR_TABELA:
                raise ArquivoDePesosInvalido(
                    f"a tabela {nome} traz o índice {indice}, fora de "
                    f"0..{ENTRADAS_POR_TABELA - 1}"
                )
            tabela[indice] = valor
            soma_lida += valor
        total_lido += quantas
        tabelas[nome] = tabela

    if total_lido != total_anunciado:
        raise ArquivoDePesosInvalido(
            f"o cabeçalho anuncia {total_anunciado} entradas não nulas e o corpo "
            f"traz {total_lido}"
        )
    if soma_lida != soma_anunciada:
        raise ArquivoDePesosInvalido(
            f"a soma de verificação não bate: o cabeçalho diz "
            f"{soma_anunciada} e os valores somam {soma_lida}"
        )

    return PesosDosPadroes(
        tabelas=tabelas,
        janelas=tuple(janelas),
        material=(material_0, material_1, material_2, material_3),
        vies=vies,
        escala_logito_para_centesimos=escala,
        regulamento=regulamento,
    )


def carregar(caminho: Path) -> PesosDosPadroes:
    """Lê um `.bin` do disco."""
    return desserializar(Path(caminho).read_bytes())


# --------------------------------------------------------------------------- #
# Avaliar
# --------------------------------------------------------------------------- #


def indice_da_janela(
    tabuleiro: Tabuleiro, janela: Janela, ponto_de_vista: Cor
) -> int:
    """A fotografia desta janela como número na base 5.

    Repetido aqui, em vez de importado de `../treino/janelas_damas.py`, por um
    motivo: **a geometria vem do arquivo**, e as janelas de `PesosDosPadroes` são
    objetos lidos, não os do módulo de treino. A função de lá recebe as janelas
    de lá. Esta recebe qualquer uma — e é a que o Dart espelha.

    A conta é a mesma, e o teste confere que as duas concordam.
    """
    if janela.inverte_o_ponto_de_vista:
        ponto_de_vista = (
            Cor.PRETAS if ponto_de_vista is Cor.BRANCAS else Cor.BRANCAS
        )
    indice = 0
    # Da última casa para a primeira, multiplicando por 5 a cada passo: é a
    # mesma conta que `d₀·5⁰ + … + d₇·5⁷`, sem calcular potência nenhuma (regra
    # de Horner). O Dart faz igual.
    for casa in reversed(janela.casas):
        indice = indice * ESTADOS_POR_CASA + estado_da_casa(
            tabuleiro, casa, ponto_de_vista
        )
    return indice


def _material_relativo(tabuleiro: Tabuleiro, ponto_de_vista: Cor) -> tuple[int, ...]:
    """As quatro contagens, na ordem de `COLUNAS_DE_MATERIAL`.

    Mesma conta de `../treino/conjunto_de_treino_damas.py`, e é obrigatório que
    seja: o modelo aprendeu com aquelas colunas naquela ordem.
    """
    contagem = tabuleiro.contar()
    if ponto_de_vista is Cor.BRANCAS:
        return (contagem[Peca.PEDRA_BRANCA], contagem[Peca.DAMA_BRANCA],
                contagem[Peca.PEDRA_PRETA], contagem[Peca.DAMA_PRETA])
    return (contagem[Peca.PEDRA_PRETA], contagem[Peca.DAMA_PRETA],
            contagem[Peca.PEDRA_BRANCA], contagem[Peca.DAMA_BRANCA])


def avaliar_do_ponto_de_vista(
    pesos: PesosDosPadroes, tabuleiro: Tabuleiro, ponto_de_vista: Cor
) -> int:
    """A nota em centésimos de pedra, do ponto de vista pedido.

    A conta inteira, em uma linha de prosa: **o viés, mais uma leitura de tabela
    por janela, mais o material.** Nenhuma multiplicação de matriz, nenhuma
    exponencial — nove somas e quatro multiplicações por posição. É por isso que
    esta avaliação cabe num aparelho simples.
    """
    total = pesos.vies
    for janela in pesos.janelas:
        total += pesos.tabelas[janela.tabela][
            indice_da_janela(tabuleiro, janela, ponto_de_vista)
        ]
    material = _material_relativo(tabuleiro, ponto_de_vista)
    for coeficiente, quantas in zip(pesos.material, material):
        total += coeficiente * quantas
    return total


def avaliar(pesos: PesosDosPadroes, tabuleiro: Tabuleiro) -> int:
    """A nota **do ponto de vista de quem tem a vez** — o que a busca quer.

    Mesma convenção de sinal de `avaliacao_damas.avaliar`, e é o que permite a
    arena da etapa 9 trocar uma avaliação pela outra sem mexer na busca.
    """
    return avaliar_do_ponto_de_vista(pesos, tabuleiro, tabuleiro.vez)


def avaliar_absoluto(pesos: PesosDosPadroes, tabuleiro: Tabuleiro) -> int:
    """A nota sempre do ponto de vista das **brancas**, para log e relatório.

    ⚠️ **Cuidado que não existe na avaliação manual:** a treinada **não é
    antissimétrica**. Negar a nota de quem tem a vez não dá a nota do outro lado,
    porque o viés é a vantagem de *ter a vez* e não muda de sinal com a cor.

    Concretamente: se as brancas têm a vez, esta função devolve `avaliar`; se as
    pretas têm, devolve `-avaliar`. As duas notas são coerentes **dentro** de um
    lance, que é o que log e relatório precisam. Comparar a nota absoluta de duas
    posições com vez diferente carrega o dobro do viés, e a diferença é da ordem
    de poucos centésimos — mas está aqui escrito para não ser descoberto como
    "bug" seis meses depois.
    """
    nota = avaliar(pesos, tabuleiro)
    return nota if tabuleiro.vez is Cor.BRANCAS else -nota
