// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A contagem de posições DISTINTAS por número de lances, a prova de que as
// regras estão certas. Para o tabuleiro 7 × 6 a resposta é conhecida e
// publicada: a sequência A212693 da OEIS (John Tromp, 2012). Um erro de regra
// qualquer (uma linha que vaza pela borda, uma coluna que aceita a 7ª peça, uma
// partida que continua depois da vitória) muda algum desses números.
//
// A contagem anda pela interface `RegrasDaModalidadeQuatro`, como a busca: ela
// não sabe qual modalidade conta, e por isso a modalidade-sonda dos testes
// também passa por aqui.
//
// ⚠️ **Uma posição com desfecho não gera filhos.** A partida acabou nela, e as
// posições "depois da vitória" não são posições legais. É a definição da OEIS:
// as duas leituras coincidem até o 7º lance e se separam no 8º (a primeira
// vitória possível é no 7º), e só esta bate com a A212693 no 8º em diante
// (conferido na T010; o teste guarda a prova).

import 'dart:typed_data';

import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// Quantas posições distintas existem depois de 0, 1, ..., [profundidade]
/// lances, jogando pelas [regras] a partir do tabuleiro vazio.
///
/// Devolve uma lista com `profundidade + 1` números; o primeiro é sempre 1 (o
/// tabuleiro vazio). "Distintas" quer dizer: a mesma posição alcançada por
/// caminhos diferentes (`s4s3s5` e `s5s3s4`) conta uma vez só.
///
/// Anda por níveis: o conjunto de chaves de um nível gera o do seguinte. Só a
/// CHAVE de cada posição é guardada (um inteiro de 8 bytes), porque ela se
/// desfaz de volta nos bits da posição (ver [_posicaoDaChave]); é o que deixa
/// contar dezenas de milhões de posições sem guardar dezenas de milhões de
/// objetos.
List<int> contarPosicoes(RegrasDaModalidadeQuatro regras, int profundidade) {
  if (profundidade < 0) {
    throw ArgumentError.value(profundidade, 'profundidade', 'negativa');
  }
  final inicial = PosicaoQuatro.inicial(regras);
  final contagem = <int>[1];
  // O nível 0 é o tabuleiro vazio, cuja chave é 0. O conjunto abaixo usa o 0
  // como "casa vazia", então o nível 0 é tratado à parte: a lista dele é a
  // própria posição inicial.
  Iterable<PosicaoQuatro> nivel = [inicial];
  for (var lances = 1; lances <= profundidade; lances++) {
    final proximo = _ConjuntoDeChaves();
    for (final posicao in nivel) {
      if (regras.desfecho(posicao) != null) continue; // acabou: sem filhos
      for (final lance in regras.lancesLegais(posicao)) {
        proximo.adicionar(regras.aplicar(posicao, lance).chave);
      }
    }
    contagem.add(proximo.tamanho);
    // O nível seguinte é lido PREGUIÇOSAMENTE: `map` sobre as chaves não
    // cria a lista de posições, só desfaz cada chave na hora em que o laço
    // de cima pede. Com 12 milhões de posições num nível, a lista pronta
    // seriam 12 milhões de objetos na memória ao mesmo tempo.
    // (`final` dentro do laço: cada volta prende o SEU número de lances.)
    final lancesDoNivel = lances;
    nivel = proximo.chaves().map(
        (chave) => _posicaoDaChave(inicial.dimensoes, chave, lancesDoNivel));
  }
  return contagem;
}

/// Desfaz uma chave (`pecasDaVez + mascara`) de volta nos bits da posição.
///
/// Coluna a coluna (cada uma com `altura + 1` bits): se a coluna tem `k`
/// peças, o pedaço `v` da chave cai entre `2^k - 1` e `2^(k+1) - 2` (ver
/// `PosicaoQuatro.chave`). Então `v + 1` fica entre `2^k` e `2^(k+1) - 1`, e
/// `k` é a posição do bit mais alto de `v + 1`. A máscara da coluna é
/// `2^k - 1` e as peças da vez são `v - (2^k - 1)`.
PosicaoQuatro _posicaoDaChave(
    DimensoesQuatro dimensoes, int chave, int lancesJogados) {
  final bitsPorColuna = dimensoes.altura + 1;
  final filtro = (1 << bitsPorColuna) - 1; // os bits de UMA coluna
  var mascara = 0;
  var pecas = 0;
  for (var c = 0; c < dimensoes.largura; c++) {
    final deslocamento = c * bitsPorColuna;
    final v = (chave >> deslocamento) & filtro;
    final k = (v + 1).bitLength - 1; // quantas peças na coluna
    final mascaraDaColuna = (1 << k) - 1;
    mascara |= mascaraDaColuna << deslocamento;
    pecas |= (v - mascaraDaColuna) << deslocamento;
  }
  return PosicaoQuatro.deBits(
    dimensoes: dimensoes,
    pecasDaVez: pecas,
    mascara: mascara,
    lancesJogados: lancesJogados,
  );
}

/// Um conjunto de inteiros POSITIVOS, enxuto em memória.
///
/// O `Set<int>` do Dart guarda cada número num objeto de entrada encadeado,
/// várias vezes o tamanho do número; aqui os números moram direto num
/// `Int64List` (8 bytes cada), com "endereçamento aberto": o número cai numa
/// gaveta calculada a partir dele e, se a gaveta está ocupada, anda para a
/// seguinte. O 0 marca a gaveta vazia (por isso só aceita positivos, e as
/// chaves depois do 1º lance sempre são).
class _ConjuntoDeChaves {
  Int64List _gavetas = Int64List(1 << 10);
  int _tamanho = 0;

  /// Quantos números distintos foram adicionados.
  int get tamanho => _tamanho;

  /// Adiciona [chave] (positiva); repetida não conta de novo.
  void adicionar(int chave) {
    // Cresce antes de passar de metade cheio: com folga, a procura pela
    // gaveta livre anda pouco.
    if (_tamanho * 2 >= _gavetas.length) _crescer();
    _inserir(_gavetas, chave);
  }

  /// Insere em [gavetas] e conta se era novo.
  void _inserir(Int64List gavetas, int chave) {
    final limite = gavetas.length - 1; // o tamanho é potência de 2
    var i = _espalhar(chave) & limite;
    while (true) {
      final atual = gavetas[i];
      if (atual == 0) {
        gavetas[i] = chave;
        _tamanho++;
        return;
      }
      if (atual == chave) return;
      i = (i + 1) & limite;
    }
  }

  /// Dobra o número de gavetas e reinsere tudo.
  void _crescer() {
    final antigas = _gavetas;
    _gavetas = Int64List(antigas.length * 2);
    _tamanho = 0;
    for (final chave in antigas) {
      if (chave != 0) _inserir(_gavetas, chave);
    }
  }

  /// Os números guardados (em ordem de gaveta, que não importa a ninguém).
  Iterable<int> chaves() => _gavetas.where((c) => c != 0);

  /// Mistura os bits da chave para as gavetas se espalharem por igual: chaves
  /// de posições parecidas diferem em poucos bits, e cairiam grudadas.
  /// Multiplicar por uma constante ímpar grande (a da "razão áurea", usada no
  /// hash de Fibonacci) e pegar os bits altos espalha bem.
  static int _espalhar(int chave) {
    final misturado = chave * 0x9E3779B97F4A7C15;
    // `>>>` desloca sem arrastar o sinal (o produto pode sair negativo).
    return misturado >>> 20;
  }
}
