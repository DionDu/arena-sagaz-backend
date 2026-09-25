/// Como uma posição de final vira um número — o alicerce da base de finais.
///
/// Este arquivo é o **port** de `../tablebase/indice_damas.py`, e vale aqui a
/// mesma regra do resto do motor: **o Python é a referência**, este é a versão
/// rápida. Mudança de numeração nasce lá, é conferida lá, e só então desce.
///
/// Por que portar
/// --------------
/// A versão em Python resolve ~9 mil índices por segundo. A base de 4 peças tem
/// 12,8 milhões de índices e a de 5 peças, 292 milhões — 25 minutos e 9 horas,
/// respectivamente. Não é o cálculo que é lento; é a linguagem. Aqui o mesmo
/// algoritmo trabalha em vetores de bytes e **não aloca um objeto por índice**,
/// que era o custo dominante.
///
/// O que é uma fatia, em uma frase
/// -------------------------------
/// A base não é um vetor só: é **um por combinação de material** ("2 pedras e 1
/// dama brancas contra 1 dama preta"). Fatiar assim não é arrumação — é o que
/// torna o cálculo possível, porque toda captura leva a uma fatia menor, e isso
/// dá uma ordem de dependência para resolver de trás para frente.
///
/// O detalhe que enxuga o índice
/// -----------------------------
/// **Pedra nunca está na própria fileira de coroação** — teria virado dama ao
/// parar lá. Então pedra dispõe de 28 casas, não de 32. Só a dama usa as 32.
library;

import 'dart:typed_data';

import 'tabuleiro_damas.dart';

// ---------------------------------------------------------------------------
// Resultados guardados na base
// ---------------------------------------------------------------------------
//
// Dois bits bastariam — só há três respostas. Hoje ocupam um byte cada; o
// empacotamento é da etapa 8, quando o tamanho no aparelho passa a importar.

/// Quem tem a vez **perde** com jogo perfeito dos dois lados.
const int derrota = 0;

/// Nem um lado nem outro força a vitória.
const int empate = 1;

/// Quem tem a vez **ganha** com jogo perfeito.
const int vitoria = 2;

/// Ainda não calculado. Só existe durante a análise retrógrada.
const int desconhecido = 3;

/// Marca de "não se aplica": posição de empate, ou vão da numeração.
const int semDistancia = -1;

const List<String> nomeDoResultado = [
  'derrota',
  'empate',
  'vitoria',
  'desconhecido',
];

// ---------------------------------------------------------------------------
// Coeficientes binomiais
// ---------------------------------------------------------------------------
//
// C(n, k) — "de quantos jeitos escolher k casas entre n". Aparece em todo lugar
// aqui, e sempre com n ≤ 32, então cabe numa tabela montada uma vez na carga.
// Calcular por fatorial a cada chamada seria o gargalo do gargalo.

final List<Int64List> _binomio = () {
  final tabela = List.generate(nCasas + 1, (_) => Int64List(nCasas + 2));
  for (var n = 0; n <= nCasas; n++) {
    tabela[n][0] = 1;
    // Triângulo de Pascal: C(n,k) = C(n-1,k-1) + C(n-1,k).
    for (var k = 1; k <= n; k++) {
      tabela[n][k] = tabela[n - 1][k - 1] + (k <= n - 1 ? tabela[n - 1][k] : 0);
    }
  }
  return tabela;
}();

/// C(n, k), com 0 quando k não cabe em n.
///
/// Devolver 0 em vez de lançar é proposital: a desnumeração testa pesos que
/// deliberadamente estouram o limite, e um zero encerra o laço sozinho.
///
/// Já `n` acima de 32 é outra história — **lança**. Não existe combinação de
/// mais de 32 casas neste jogo, então chegar aí significa índice corrompido; e
/// devolver 0 nesse caso transformaria o laço `while` da desnumeração em laço
/// infinito, que é o pior jeito possível de descobrir um erro.
int binomio(int n, int k) {
  if (n < 0 || k < 0 || k > n) return 0;
  if (n > nCasas) {
    throw StateError('C($n,$k) fora da tabela — índice corrompido?');
  }
  return _binomio[n][k];
}

// ---------------------------------------------------------------------------
// As casas disponíveis para cada tipo de peça
// ---------------------------------------------------------------------------

/// Casas em que uma pedra branca pode estar: todas menos a fileira onde ela
/// coroaria. São 28.
final Int32List casasDePedraBranca = Int32List.fromList([
  for (var casa = 1; casa <= nCasas; casa++)
    if (!casasDeCoroacao[brancas].contains(casa)) casa,
]);

/// Idem para a pedra preta: todas menos a fileira de coroação dela. São 28.
final Int32List casasDePedraPreta = Int32List.fromList([
  for (var casa = 1; casa <= nCasas; casa++)
    if (!casasDeCoroacao[pretas].contains(casa)) casa,
]);

// O caminho inverso: dado o número da casa, qual é a sua posição (0-based)
// dentro da lista acima. −1 quando a casa não serve àquele tipo de peça.
final Int32List _ordemDaPedraBranca = _inverter(casasDePedraBranca);
final Int32List _ordemDaPedraPreta = _inverter(casasDePedraPreta);

Int32List _inverter(Int32List casas) {
  final ordem = Int32List(nCasas + 1)..fillRange(0, nCasas + 1, -1);
  for (var i = 0; i < casas.length; i++) {
    ordem[casas[i]] = i;
  }
  return ordem;
}

// ---------------------------------------------------------------------------
// Numeração de combinações
// ---------------------------------------------------------------------------
//
// Para colocar k peças **iguais** em n casas, o que interessa é qual
// subconjunto de casas elas ocupam — a ordem entre peças idênticas não existe.
// Numerar subconjuntos de tamanho fixo é um problema resolvido: o "sistema
// numérico combinatório", que dá uma correspondência 1 para 1 entre os
// subconjuntos e os números de 0 a C(n,k)−1.
//
// A conta, para um subconjunto {c₀ < c₁ < … < c_{k−1}} de posições 0-based:
//     número = C(c₀,1) + C(c₁,2) + … + C(c_{k−1},k)
// Não é preciso decorar a fórmula — é preciso saber que ela é reversível, e o
// teste de paridade com o Python confere isso índice a índice.

/// Numera um subconjunto ordenado de posições 0-based.
///
/// [quantas] existe para permitir passar um buffer maior que o subconjunto, o
/// que evita alocar uma lista do tamanho exato a cada chamada.
int numerarCombinacao(Int32List posicoes, int quantas) {
  var numero = 0;
  for (var ordem = 1; ordem <= quantas; ordem++) {
    numero += binomio(posicoes[ordem - 1], ordem);
  }
  return numero;
}

/// A operação inversa: do número de volta ao subconjunto, escrito em [saida].
///
/// Percorre de trás para frente escolhendo, em cada "casa decimal", a maior
/// posição cujo peso ainda cabe no que resta do número. Escreve direto no lugar
/// certo de [saida], então o resultado já sai em ordem crescente.
void desnumerarCombinacao(int numero, int quantas, Int32List saida) {
  var restante = numero;
  for (var ordem = quantas; ordem >= 1; ordem--) {
    var posicao = ordem - 1;
    while (binomio(posicao + 1, ordem) <= restante) {
      posicao++;
    }
    saida[ordem - 1] = posicao;
    restante -= binomio(posicao, ordem);
  }
}

// ---------------------------------------------------------------------------
// A fatia de material
// ---------------------------------------------------------------------------

/// Uma combinação de material: quantas peças de cada tipo estão no tabuleiro.
///
/// O nome curto (`2100` = 2 pedras brancas, 1 dama branca, 0 e 0) é o que vira
/// nome de arquivo quando a base é gravada em disco.
class Fatia {
  final int pedrasBrancas;
  final int damasBrancas;
  final int pedrasPretas;
  final int damasPretas;

  /// Multiplicadores posicionais do índice — cada tipo de peça é uma "casa
  /// decimal" do número final. Calculados uma vez, no construtor.
  final int _baseDamasPretas;
  final int _baseDamasBrancas;
  final int _basePedrasPretas;

  /// Quantos índices esta fatia ocupa **sem** contar o lado a jogar.
  final int _total;

  factory Fatia(
    int pedrasBrancas,
    int damasBrancas,
    int pedrasPretas,
    int damasPretas,
  ) {
    if (pedrasBrancas < 0 ||
        damasBrancas < 0 ||
        pedrasPretas < 0 ||
        damasPretas < 0) {
      throw ArgumentError('contagem negativa de peças');
    }
    final total = pedrasBrancas + damasBrancas + pedrasPretas + damasPretas;
    if (total > nCasas) throw ArgumentError('mais peças que casas');

    // As damas se acomodam nas casas que sobraram depois das pedras; as pretas,
    // depois também das brancas. Daí as duas contas encadeadas.
    final livresParaDamas = nCasas - pedrasBrancas - pedrasPretas;
    final nDamasPretas =
        binomio(livresParaDamas - damasBrancas, damasPretas);
    final nDamasBrancas = binomio(livresParaDamas, damasBrancas);
    final nPedrasPretas = binomio(casasDePedraPreta.length, pedrasPretas);
    final nPedrasBrancas = binomio(casasDePedraBranca.length, pedrasBrancas);

    return Fatia._(
      pedrasBrancas,
      damasBrancas,
      pedrasPretas,
      damasPretas,
      nDamasPretas,
      nDamasBrancas,
      nPedrasPretas,
      nPedrasBrancas * nPedrasPretas * nDamasBrancas * nDamasPretas,
    );
  }

  const Fatia._(
    this.pedrasBrancas,
    this.damasBrancas,
    this.pedrasPretas,
    this.damasPretas,
    this._baseDamasPretas,
    this._baseDamasBrancas,
    this._basePedrasPretas,
    this._total,
  );

  int get totalDePecas =>
      pedrasBrancas + damasBrancas + pedrasPretas + damasPretas;

  /// Quantas pedras há. É a chave da ordem de dependência: uma promoção troca
  /// pedra por dama sem mudar o total, então uma fatia com pedras depende das
  /// que têm menos.
  int get totalDePedras => pedrasBrancas + pedrasPretas;

  /// `2100` — pedras brancas, damas brancas, pedras pretas, damas pretas.
  String get nome =>
      '$pedrasBrancas$damasBrancas$pedrasPretas$damasPretas';

  /// Posição sem um dos lados não é final: a partida já acabou.
  bool get temOsDoisLados =>
      pedrasBrancas + damasBrancas > 0 && pedrasPretas + damasPretas > 0;

  /// Quantos índices esta fatia ocupa, contando os dois lados a jogar.
  ///
  /// ⚠️ É um pouco **maior** que o número de posições legais, de propósito. As
  /// pedras brancas e as pretas são numeradas em conjuntos que se sobrepõem
  /// (casas 5 a 28 servem às duas), então algumas combinações de índice
  /// corresponderiam a duas pedras na mesma casa — posição que não existe e que
  /// nunca é consultada. O desperdício é de 3% a ~15% conforme a fatia, e foi
  /// aceito em troca de uma numeração que os testes conseguem verificar
  /// exaustivamente. Base de finais errada é o pior erro possível deste projeto.
  int get tamanho => _total * 2;

  /// O código inteiro deste material. Ver [codigoDeMaterial].
  int get codigo =>
      codigoDeMaterial(pedrasBrancas, damasBrancas, pedrasPretas, damasPretas);

  /// O índice desta posição dentro da fatia.
  ///
  /// Aloca buffers a cada chamada. Em laço quente use [Indexador], que os
  /// reaproveita — na análise retrógrada isso é a diferença entre um objeto por
  /// sucessor e nenhum.
  int daPosicao(Tabuleiro tabuleiro) => Indexador().indiceEm(this, tabuleiro);

  @override
  String toString() {
    String lado(int pedras, int damas) {
      final partes = <String>[];
      if (pedras > 0) partes.add('$pedras pedra${pedras > 1 ? 's' : ''}');
      if (damas > 0) partes.add('$damas dama${damas > 1 ? 's' : ''}');
      return partes.isEmpty ? 'nada' : partes.join(' e ');
    }

    return '${lado(pedrasBrancas, damasBrancas)} × '
        '${lado(pedrasPretas, damasPretas)}';
  }

  @override
  bool operator ==(Object outro) =>
      outro is Fatia &&
      outro.pedrasBrancas == pedrasBrancas &&
      outro.damasBrancas == damasBrancas &&
      outro.pedrasPretas == pedrasPretas &&
      outro.damasPretas == damasPretas;

  @override
  int get hashCode =>
      ((pedrasBrancas * 33 + damasBrancas) * 33 + pedrasPretas) * 33 +
      damasPretas;
}

// ---------------------------------------------------------------------------
// O código de material — a chave que substitui o nome
// ---------------------------------------------------------------------------
//
// A base guarda um vetor por fatia, e a retrógrada consulta a fatia de destino
// de CADA sucessor de CADA índice — bilhões de vezes. Procurar por `nome` custa
// montar uma String a cada consulta, e String em laço quente é o tipo de custo
// que não aparece lendo o código, só medindo.
//
// O código é um número: quatro contagens em base 9 (nenhum final útil tem 9
// peças de um mesmo tipo). Cabe em 13 bits, e vira índice direto de um vetor.
//
// ⚠️ **Base 9 só é injetiva enquanto cada contagem couber num dígito** — e uma
// partida começa com 12 pedras por lado. Por isso [codigoDaPosicao] verifica
// antes de empacotar; ler o aviso lá antes de mexer em qualquer coisa aqui.

/// Maior código possível, mais um. É o tamanho do vetor indexado por código.
const int totalDeCodigosDeMaterial = 9 * 9 * 9 * 9;

/// Empacota as quatro contagens num único inteiro.
int codigoDeMaterial(
  int pedrasBrancas,
  int damasBrancas,
  int pedrasPretas,
  int damasPretas,
) =>
    ((pedrasBrancas * 9 + damasBrancas) * 9 + pedrasPretas) * 9 + damasPretas;

/// O que [codigoDaPosicao] devolve quando **não existe** código para a posição.
///
/// ⚠️ Não é decoração: sem este valor o empacotamento em base 9 **mente em
/// silêncio**. Ver o aviso em [codigoDaPosicao].
const int semCodigoDeMaterial = totalDeCodigosDeMaterial;

/// O código de material desta posição, **sem alocar nada**.
///
/// Devolve [semCodigoDeMaterial] quando algum dos quatro tipos tem **mais de 8**
/// peças — isto é, sempre que a posição está fora do alcance da base.
///
/// ── ⚠️ Por que a checagem existe (e o que acontecia sem ela) ──────────
///
/// O código são quatro contagens em **base 9**, e base 9 só é injetiva enquanto
/// cada contagem couber num dígito. Uma partida começa com **12** pedras por
/// lado, e aí o empacotamento faz duas coisas ruins, não uma:
///
///  1. **Estoura o vetor.** A posição inicial dá `8856`, e o vetor indexado por
///     código tem `6561` entradas — `RangeError`.
///  2. **Pior: ALIASA.** `3` pedras brancas contra `9` pedras pretas — meio de
///     jogo comumíssimo — dá `2268`, que é exatamente o código da fatia `3100`
///     (3 pedras + 1 dama brancas). O código cai **dentro** do vetor, a fatia
///     existe na base de 4 peças, e a consulta segue adiante sobre a fatia
///     **errada** — sem que nada denuncie até o índice estourar lá dentro.
///
/// Os dois foram medidos em 2026-08-25, pela T185 parte 2a — a primeira vez em
/// que a base foi consultada a partir de uma posição **viva**, e não de dentro
/// do seu próprio domínio. No laboratório nunca apareceu porque lá toda consulta
/// nasce de uma fatia que já cabe. Ver research **D-30**.
int codigoDaPosicao(Tabuleiro tabuleiro) {
  var pb = 0, db = 0, pp = 0, dp = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    switch (tabuleiro.ler(casa)) {
      case pedraBranca:
        pb++;
      case damaBranca:
        db++;
      case pedraPreta:
        pp++;
      case damaPreta:
        dp++;
    }
  }
  // Quatro comparações contra as 32 leituras do laço acima: o custo não aparece
  // nem na retrógrada, onde nenhuma delas chega a disparar (lá todo material já
  // cabe, por construção).
  if (pb > 8 || db > 8 || pp > 8 || dp > 8) return semCodigoDeMaterial;
  return codigoDeMaterial(pb, db, pp, dp);
}

/// A fatia correspondente a um código de material.
Fatia fatiaDoCodigo(int codigo) => Fatia(
      codigo ~/ 729,
      (codigo ~/ 81) % 9,
      (codigo ~/ 9) % 9,
      codigo % 9,
    );

/// A fatia a que esta posição pertence, ou `null` quando **não há fatia**.
///
/// `null` é a resposta honesta para uma posição com mais de 8 peças de um mesmo
/// tipo: ela não pertence a fatia nenhuma. Até 2026-08-25 esta função devolvia a
/// fatia de um código **alheio**, e quem a usava como guarda acertava por
/// acidente — o tipo de acerto que some quando o vizinho muda.
Fatia? fatiaDaPosicao(Tabuleiro tabuleiro) {
  final codigo = codigoDaPosicao(tabuleiro);
  if (codigo == semCodigoDeMaterial) return null;
  return fatiaDoCodigo(codigo);
}

/// Todas as fatias com até [totalDePecas] peças, **em ordem de dependência**.
///
/// A ordem é o que torna a análise retrógrada possível, e ela tem dois níveis:
///
/// 1. **menos peças primeiro** — toda captura leva a uma fatia menor, que
///    portanto precisa estar pronta;
/// 2. dentro do mesmo número de peças, **menos pedras primeiro** — uma promoção
///    troca pedra por dama sem mudar o total.
///
/// Fatias sem um dos lados ficam de fora: não são final, são partida acabada.
List<Fatia> fatiasAte(int totalDePecas) {
  final fatias = <Fatia>[];
  for (var total = 2; total <= totalDePecas; total++) {
    for (var pb = 0; pb <= total; pb++) {
      for (var db = 0; db <= total - pb; db++) {
        for (var pp = 0; pp <= total - pb - db; pp++) {
          final dp = total - pb - db - pp;
          final fatia = Fatia(pb, db, pp, dp);
          if (fatia.temOsDoisLados) fatias.add(fatia);
        }
      }
    }
  }
  // Ordenação **estável** pelos dois critérios, igual à do Python: dentro do
  // mesmo par (peças, pedras) a ordem de geração é preservada, e os dois lados
  // precisam produzir exatamente a mesma sequência de arquivos.
  fatias.sort((a, b) {
    final porPecas = a.totalDePecas.compareTo(b.totalDePecas);
    if (porPecas != 0) return porPecas;
    return a.totalDePedras.compareTo(b.totalDePedras);
  });
  return fatias;
}

// ---------------------------------------------------------------------------
// Posição → índice, sem alocar
// ---------------------------------------------------------------------------

/// Converte posição em índice reaproveitando os buffers de trabalho.
///
/// O caminho de ida (posição → índice) é percorrido uma vez por **sucessor**,
/// não por índice: é o mais quente dos dois. Guardar os buffers num objeto tira
/// seis alocações de dentro dele.
///
/// > ⚠️ Como o [Reconstrutor], não é reentrante — um por laço.
class Indexador {
  final Int32List _casasPb = Int32List(8);
  final Int32List _casasDb = Int32List(8);
  final Int32List _casasPp = Int32List(8);
  final Int32List _casasDp = Int32List(8);
  final Int32List _ordem = Int32List(8);
  final Int32List _livres = Int32List(nCasas);
  final Int32List _livresPretas = Int32List(nCasas);

  /// O índice de [tabuleiro] dentro de [fatia].
  ///
  /// Lança [ArgumentError] se a posição não pertence à fatia — erro alto e cedo,
  /// porque consultar a fatia errada devolve uma resposta plausível e sem
  /// nenhuma relação com o tabuleiro.
  int indiceEm(Fatia fatia, Tabuleiro tabuleiro) {
    var nPb = 0, nDb = 0, nPp = 0, nDp = 0;
    for (var casa = 1; casa <= nCasas; casa++) {
      switch (tabuleiro.ler(casa)) {
        case pedraBranca:
          _casasPb[nPb++] = casa;
        case damaBranca:
          _casasDb[nDb++] = casa;
        case pedraPreta:
          _casasPp[nPp++] = casa;
        case damaPreta:
          _casasDp[nDp++] = casa;
      }
    }

    if (nPb != fatia.pedrasBrancas ||
        nDb != fatia.damasBrancas ||
        nPp != fatia.pedrasPretas ||
        nDp != fatia.damasPretas) {
      throw ArgumentError(
        'a posição tem material $nPb$nDb$nPp$nDp, não ${fatia.nome}',
      );
    }

    // As pedras são numeradas nos conjuntos restritos de 28 casas…
    for (var i = 0; i < nPb; i++) {
      _ordem[i] = _ordemDaPedraBranca[_casasPb[i]];
    }
    final numeroPb = numerarCombinacao(_ordem, nPb);
    for (var i = 0; i < nPp; i++) {
      _ordem[i] = _ordemDaPedraPreta[_casasPp[i]];
    }
    final numeroPp = numerarCombinacao(_ordem, nPp);

    // …e as damas, nas casas que sobraram depois das pedras.
    var nLivres = 0;
    for (var casa = 1; casa <= nCasas; casa++) {
      final conteudo = tabuleiro.ler(casa);
      if (conteudo != pedraBranca && conteudo != pedraPreta) {
        _livres[nLivres++] = casa;
      }
    }
    for (var i = 0; i < nDb; i++) {
      _ordem[i] = _posicaoEm(_livres, nLivres, _casasDb[i]);
    }
    final numeroDb = numerarCombinacao(_ordem, nDb);

    // As damas pretas, nas que sobraram também das damas brancas.
    var nLivresPretas = 0;
    for (var i = 0; i < nLivres; i++) {
      if (tabuleiro.ler(_livres[i]) != damaBranca) {
        _livresPretas[nLivresPretas++] = _livres[i];
      }
    }
    for (var i = 0; i < nDp; i++) {
      _ordem[i] = _posicaoEm(_livresPretas, nLivresPretas, _casasDp[i]);
    }
    final numeroDp = numerarCombinacao(_ordem, nDp);

    final indice =
        ((numeroPb * fatia._basePedrasPretas + numeroPp) *
                        fatia._baseDamasBrancas +
                    numeroDb) *
                fatia._baseDamasPretas +
            numeroDp;
    return indice * 2 + tabuleiro.vez;
  }

  /// Onde [alvo] está dentro dos [quantos] primeiros elementos de [lista].
  static int _posicaoEm(Int32List lista, int quantos, int alvo) {
    for (var i = 0; i < quantos; i++) {
      if (lista[i] == alvo) return i;
    }
    throw StateError('casa $alvo não estava entre as livres');
  }
}

// ---------------------------------------------------------------------------
// Reconstrução sem alocar
// ---------------------------------------------------------------------------

/// Reconstrói posições de uma fatia **sem alocar nada por índice**.
///
/// É a peça que faz a diferença de velocidade. A versão em Python cria um objeto
/// `Tabuleiro`, quatro listas e dois conjuntos a cada índice; numa varredura de
/// 292 milhões de índices, isso é o custo dominante — não a aritmética.
///
/// Aqui tudo mora em buffers reaproveitados, e [tabuleiro] é **o mesmo objeto**
/// a cada chamada.
///
/// > ⚠️ Justamente por reaproveitar, um `Reconstrutor` **não** pode ser usado por
/// > dois laços ao mesmo tempo, nem ter o seu [tabuleiro] guardado para depois.
/// > Precisa guardar? Chame `tabuleiro.clonar()`.
class Reconstrutor {
  final Fatia fatia;

  /// O tabuleiro reaproveitado. Só é válido logo após um [reconstruir] que
  /// devolveu `true`.
  final Tabuleiro tabuleiro = Tabuleiro.vazio();

  final Int32List _numeros = Int32List(8);
  final Int32List _livres = Int32List(nCasas);
  final Int32List _livresPretas = Int32List(nCasas);
  final Uint8List _ocupada = Uint8List(nCasas + 1);

  Reconstrutor(this.fatia);

  /// Monta em [tabuleiro] a posição de número [indice].
  ///
  /// Devolve `false` quando o índice cai num **vão da numeração** — as
  /// combinações em que uma pedra branca e uma preta ocupariam a mesma casa.
  /// Ver a nota em [Fatia.tamanho].
  bool reconstruir(int indice) {
    if (indice < 0 || indice >= fatia.tamanho) {
      throw RangeError('índice $indice fora da fatia ${fatia.nome}');
    }

    final vez = indice & 1; // 0 = brancas, 1 = pretas
    var resto = indice >> 1;

    // Desmonta o número posicional na ordem inversa da montagem.
    final numeroDp = resto % fatia._baseDamasPretas;
    resto = resto ~/ fatia._baseDamasPretas;
    final numeroDb = resto % fatia._baseDamasBrancas;
    resto = resto ~/ fatia._baseDamasBrancas;
    final numeroPp = resto % fatia._basePedrasPretas;
    final numeroPb = resto ~/ fatia._basePedrasPretas;

    tabuleiro.limpar(vez: vez);
    _ocupada.fillRange(0, nCasas + 1, 0);

    // Pedras brancas.
    desnumerarCombinacao(numeroPb, fatia.pedrasBrancas, _numeros);
    for (var i = 0; i < fatia.pedrasBrancas; i++) {
      final casa = casasDePedraBranca[_numeros[i]];
      tabuleiro.escrever(casa, pedraBranca);
      _ocupada[casa] = 1;
    }

    // Pedras pretas. Aqui é onde o vão aparece: se a casa já tem pedra branca,
    // este índice não corresponde a posição nenhuma.
    desnumerarCombinacao(numeroPp, fatia.pedrasPretas, _numeros);
    for (var i = 0; i < fatia.pedrasPretas; i++) {
      final casa = casasDePedraPreta[_numeros[i]];
      if (_ocupada[casa] == 1) return false;
      tabuleiro.escrever(casa, pedraPreta);
      _ocupada[casa] = 1;
    }

    // As damas brancas ocupam as casas que sobraram.
    var nLivres = 0;
    for (var casa = 1; casa <= nCasas; casa++) {
      if (_ocupada[casa] == 0) _livres[nLivres++] = casa;
    }
    desnumerarCombinacao(numeroDb, fatia.damasBrancas, _numeros);
    for (var i = 0; i < fatia.damasBrancas; i++) {
      tabuleiro.escrever(_livres[_numeros[i]], damaBranca);
    }

    // E as damas pretas, nas que sobraram também das damas brancas.
    var nLivresPretas = 0;
    for (var i = 0; i < nLivres; i++) {
      if (tabuleiro.ler(_livres[i]) != damaBranca) {
        _livresPretas[nLivresPretas++] = _livres[i];
      }
    }
    desnumerarCombinacao(numeroDp, fatia.damasPretas, _numeros);
    for (var i = 0; i < fatia.damasPretas; i++) {
      tabuleiro.escrever(_livresPretas[_numeros[i]], damaPreta);
    }

    return true;
  }
}
