// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// A paridade de linha (o primeiro jogador quer as ameaças nas linhas ímpares,
// o segundo nas pares) é a análise pública de Victor Allis (1988); a tabela
// de "quantas linhas passam por cada casa" é a avaliação clássica do jogo.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A HEURÍSTICA da busca (spec 010, T030; RF-QTR-030, R-04): o valor de uma
// posição quando a visão da busca acaba antes do fim da partida. Sem ela, toda
// posição sem desfecho valia 0, e a busca escolhia às cegas entre os lances
// que não perdem.
//
// Duas parcelas, calculadas para cada jogador e subtraídas (a minha menos a
// do outro):
//
// 1. **As ameaças** (as casas vazias onde uma peça a mais completa a linha,
//    pela T029), com o peso da PARIDADE DE LINHA. Quando as colunas enchem,
//    as peças entram alternadas, e quem abriu a partida (o Jogador 1) acaba
//    ocupando as casas de linha ÍMPAR (1, 3, 5) nas colunas que sobram, e o
//    Jogador 2 as de linha PAR. Uma ameaça na linha "do dono" tende a ser
//    cumprida no fim; na linha do outro, tende a ser tapada. Por isso vale
//    mais na linha certa.
// 2. **A posição das peças**: cada peça vale o número de linhas de `alinhar`
//    casas que passam pela casa dela. O centro entra em mais linhas que a
//    borda (13 contra 3 no 7 × 6), e é isso que faz a busca preferir o meio
//    quando ainda não há ameaça nenhuma.
//
// ⚠️ É a heurística BÁSICA (decisão do dono, 13/10/2026, §8zzv): entrou antes
// da medição do teto do Magno, para a bancada medir o custo de um motor que
// pensa de verdade. Os pesos abaixo são um ponto de partida; o refino, se
// vier, vem da escada (T036) e não refaz a medição.
//
// ⚠️ A paridade como está escrita (ímpar para o J1) é a do tabuleiro de altura
// PAR, como o 7 × 6. Numa altura ímpar (a sonda, 6 × 5) a conta roda igual,
// mas a teoria por trás dela não vale: é só uma heurística, e a busca continua
// exata onde enxerga o fim.
//
// O valor NUNCA chega perto do de uma partida decidida
// (`limiarDecididoQuatro`): é limitado a ±[tetoDaHeuristicaQuatro], para a
// busca não confundir "posição boa" com "vitória forçada".

import 'ameacas_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// O peso de uma ameaça na linha da paridade certa para o dono dela (ímpar
/// para o J1, par para o J2).
const int pesoAmeacaNaParidadeQuatro = 32;

/// O peso de uma ameaça na linha da paridade do outro: ainda vale (obriga o
/// outro a vigiar a casa), mas bem menos.
const int pesoAmeacaForaDaParidadeQuatro = 12;

/// O maior valor (em módulo) que a heurística devolve. Bem abaixo do valor de
/// uma partida decidida (`limiarDecididoQuatro`, 936), para nenhuma posição
/// sem desfecho parecer uma vitória forçada.
const int tetoDaHeuristicaQuatro = 500;

/// A heurística de um tamanho de tabuleiro.
///
/// Tudo o que depende só das DIMENSÕES (as máscaras das linhas ímpares, o peso
/// de cada casa) é calculado uma vez, na criação: a busca chama [avaliar] a
/// cada posição em que a visão acaba, centenas de milhares de vezes por lance.
final class HeuristicaQuatro {
  /// As dimensões do tabuleiro.
  final DimensoesQuatro dimensoes;

  /// Os bits de todas as casas (sem as sentinelas).
  final int _tabuleiro;

  /// Os bits das casas de linha ímpar (1, 3, 5... contando de baixo, a partir
  /// de 1).
  final int _linhasImpares;

  /// O peso posicional, agrupado: `_pesos[k]` é um peso, e
  /// `_casasDoPeso[k]` são os bits de todas as casas que valem esse peso. Assim
  /// a soma das peças é "peso × quantas peças caem nessas casas", poucas contas
  /// por posição em vez de uma por peça.
  final List<int> _pesos;
  final List<int> _casasDoPeso;

  HeuristicaQuatro._(this.dimensoes, this._tabuleiro, this._linhasImpares,
      this._pesos, this._casasDoPeso);

  /// Monta a heurística das [dimensoes].
  factory HeuristicaQuatro(DimensoesQuatro dimensoes) {
    final pesoPorBit = pesoDasCasasQuatro(dimensoes);
    // Junta as casas de mesmo peso numa máscara só (o `Map` vai do peso aos
    // bits das casas que o têm).
    final porPeso = <int, int>{};
    var impares = 0;
    for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
      for (var linha = 1; linha <= dimensoes.altura; linha++) {
        final indice = indiceDoBit(dimensoes, coluna, linha);
        final peso = pesoPorBit[indice];
        porPeso[peso] = (porPeso[peso] ?? 0) | (1 << indice);
        if (linha.isOdd) impares |= 1 << indice;
      }
    }
    // A ordem das entradas não muda a soma; ordenar só deixa a conta igual em
    // qualquer execução (o `Map` do Dart guarda a ordem de inserção).
    final pesos = porPeso.keys.toList()..sort();
    return HeuristicaQuatro._(
      dimensoes,
      mascaraDoTabuleiro(dimensoes),
      impares,
      List.unmodifiable(pesos),
      List.unmodifiable([for (final p in pesos) porPeso[p]!]),
    );
  }

  /// O valor de [posicao] para QUEM TEM A VEZ (o referencial do negamax).
  int avaliar(PosicaoQuatro posicao) =>
      posicao.jogadorDaVez * avaliarJ1(posicao);

  /// O valor de [posicao] do ponto de vista do Jogador 1: positivo = melhor
  /// para o azul. Depende só das peças, e não de quem tem a vez.
  int avaliarJ1(PosicaoQuatro posicao) => diferenca(
        posicao.pecasDoJ1,
        posicao.pecasDoJ2,
        posicao.mascara,
        paridadeImparParaA: true,
      );

  /// A pontuação do lado A menos a do lado B, limitada a
  /// ±[tetoDaHeuristicaQuatro]. [paridadeImparParaA] diz qual paridade de
  /// linha é a de A (a de B é a outra).
  ///
  /// É a forma da antissimetria: trocar A com B e as paridades troca o sinal,
  /// exatamente. O teste confere isso.
  int diferenca(int pecasA, int pecasB, int mascara,
      {required bool paridadeImparParaA}) {
    final valor = pontuacaoDoLado(pecasA, mascara,
            paridadeImpar: paridadeImparParaA) -
        pontuacaoDoLado(pecasB, mascara, paridadeImpar: !paridadeImparParaA);
    // `clamp` prende o valor no intervalo (com limites inteiros, devolve int).
    return valor.clamp(-tetoDaHeuristicaQuatro, tetoDaHeuristicaQuatro);
  }

  /// A pontuação de UM lado, com as [pecas] dele e a [mascara] de todas as
  /// casas ocupadas: as ameaças (com o peso da paridade) mais a posição.
  int pontuacaoDoLado(int pecas, int mascara, {required bool paridadeImpar}) =>
      pontuacaoDasAmeacas(pecas, mascara, paridadeImpar: paridadeImpar) +
      pontuacaoPosicional(pecas);

  /// As ameaças de [pecas]: cada casa vazia que completaria a linha vale
  /// [pesoAmeacaNaParidadeQuatro] na linha da paridade do lado
  /// ([paridadeImpar] = linhas 1, 3, 5) e [pesoAmeacaForaDaParidadeQuatro] na
  /// outra. Uma casa conta uma vez, mesmo completando duas linhas.
  int pontuacaoDasAmeacas(int pecas, int mascara,
      {required bool paridadeImpar}) {
    final ameacas = casasDeAmeacaQuatro(dimensoes, pecas, mascara);
    // As casas da paridade do lado: as ímpares, ou as pares (o resto do
    // tabuleiro).
    final daParidade =
        paridadeImpar ? _linhasImpares : _tabuleiro & ~_linhasImpares;
    final boas = contarBitsQuatro(ameacas & daParidade);
    final outras = contarBitsQuatro(ameacas & ~daParidade);
    return boas * pesoAmeacaNaParidadeQuatro +
        outras * pesoAmeacaForaDaParidadeQuatro;
  }

  /// A posição de [pecas]: a soma, peça a peça, do número de linhas que
  /// passam pela casa dela.
  int pontuacaoPosicional(int pecas) {
    var soma = 0;
    for (var k = 0; k < _pesos.length; k++) {
      soma += _pesos[k] * contarBitsQuatro(pecas & _casasDoPeso[k]);
    }
    return soma;
  }
}

/// Quantas linhas de `alinhar` casas (nas quatro direções) passam por cada
/// casa, indexado pelo número do bit (as sentinelas ficam com 0).
///
/// No 7 × 6, alinhar 4, é a tabela clássica: 3 no canto, 13 nas casas do
/// meio. Calculada das dimensões, para valer em qualquer tabuleiro.
List<int> pesoDasCasasQuatro(DimensoesQuatro dimensoes) {
  final pesos = List<int>.filled((dimensoes.altura + 1) * dimensoes.largura, 0);
  final n = dimensoes.alinhar;
  // As quatro direções, como (passo na coluna, passo na linha): vertical,
  // horizontal, diagonal que sobe e diagonal que desce.
  const direcoes = [(0, 1), (1, 0), (1, 1), (1, -1)];
  for (final (dc, dl) in direcoes) {
    for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
      for (var linha = 1; linha <= dimensoes.altura; linha++) {
        // A linha que COMEÇA em (coluna, linha) e anda n - 1 passos: só conta
        // se a última casa ainda está dentro do tabuleiro.
        final colunaFinal = coluna + dc * (n - 1);
        final linhaFinal = linha + dl * (n - 1);
        if (colunaFinal < 1 || colunaFinal > dimensoes.largura) continue;
        if (linhaFinal < 1 || linhaFinal > dimensoes.altura) continue;
        for (var i = 0; i < n; i++) {
          pesos[indiceDoBit(dimensoes, coluna + dc * i, linha + dl * i)]++;
        }
      }
    }
  }
  return pesos;
}

/// Quantos bits ligados há em [bits] (que não pode ser negativo).
///
/// A conta "em paralelo" clássica (Hacker's Delight, cap. 5): soma os bits de
/// dois em dois, depois de quatro em quatro, depois de oito em oito, e a
/// multiplicação final junta os oito bytes no byte de cima. É bem mais rápida
/// que olhar os 63 bits um a um, e a heurística a chama várias vezes por
/// posição.
int contarBitsQuatro(int bits) {
  // `>>>` desloca sem estender o sinal (o bit de cima entra como 0).
  var x = bits - ((bits >>> 1) & 0x5555555555555555);
  x = (x & 0x3333333333333333) + ((x >>> 2) & 0x3333333333333333);
  x = (x + (x >>> 4)) & 0x0F0F0F0F0F0F0F0F;
  // A multiplicação soma os oito bytes no byte de cima (o "vai um" que passa
  // dos 64 bits é descartado, e é isso que se quer).
  return (x * 0x0101010101010101) >>> 56;
}
