/// Avaliação escrita à mão, em Dart — o "olho" do motor que roda no aparelho.
///
/// Port de `../motor/avaliacao_damas.py`, com os mesmos pesos e a mesma conta.
/// A regra vale aqui como vale para as regras do jogo: **decisão nasce no
/// Python**, que é o motor de referência; este arquivo obedece. O teste do
/// harness confere posição a posição contra os valores que o Python devolve.
///
/// Convenção de sinal: [avaliar] devolve a nota **do ponto de vista de quem tem
/// a vez** — é o que a busca *negamax* espera. [avaliarAbsoluto] devolve sempre
/// do ponto de vista das brancas, que é o referencial fixo para log e relatório.
library;

import 'dart:typed_data';

import 'tabuleiro_damas.dart';

/// Nota de uma posição ganha. Muito acima de qualquer soma de peças, para que
/// nenhuma vantagem posicional imaginável se compare a um desfecho.
const int vitoria = 1000000;

/// Os pesos da avaliação, em centésimos de pedra.
///
/// A unidade é a pedra = 100, convenção de motores de tabuleiro: assim um
/// ajuste fino cabe num inteiro ("+12" é doze centésimos de pedra).
///
/// O porquê de cada peso está documentado no equivalente em Python; aqui os
/// valores são só reproduzidos. Mudou lá? Muda aqui, e o harness reprova se
/// esquecerem.
class PesosAvaliacao {
  final int pedra;
  final int dama;
  final int avancoPorFileira;
  final int colunaDeBorda;
  final int grandeDiagonalPeso;
  final int fileiraDeFundo;

  const PesosAvaliacao({
    this.pedra = 100,
    this.dama = 300,
    this.avancoPorFileira = 6,
    this.colunaDeBorda = 8,
    this.grandeDiagonalPeso = 12,
    this.fileiraDeFundo = 10,
  });
}

const PesosAvaliacao pesosPadrao = PesosAvaliacao();

// Tabelas pré-calculadas por casa: uma varredura das 32 casas na carga do
// programa evita repetir `linhaColuna`, `contains` e comparações de coluna em
// cada uma das centenas de milhares de avaliações por segundo que a busca faz.
//
// A conta que cada uma guarda está no Python; aqui só se armazena o resultado.
final Int8List _avancoDasBrancas = _tabelaDeAvanco(brancas);
final Int8List _avancoDasPretas = _tabelaDeAvanco(pretas);
final Int8List _bonusDeCasa = _tabelaDeBonusDeCasa();
final Uint8List _fundoDasBrancas = _tabelaDeFundo(brancas);
final Uint8List _fundoDasPretas = _tabelaDeFundo(pretas);

Int8List _tabelaDeAvanco(int cor) {
  final tabela = Int8List(nCasas + 1);
  for (var casa = 1; casa <= nCasas; casa++) {
    final (linha, _) = linhaColuna(casa);
    tabela[casa] = cor == brancas ? (lado - 1 - linha) : linha;
  }
  return tabela;
}

/// Bônus que independem da cor da peça: borda e grande diagonal, em "unidades"
/// (1 de borda + 1 de diagonal viram 2 aqui, e os pesos multiplicam depois).
Int8List _tabelaDeBonusDeCasa() {
  final tabela = Int8List(nCasas + 1);
  for (var casa = 1; casa <= nCasas; casa++) {
    final (_, coluna) = linhaColuna(casa);
    tabela[casa] = ((coluna == 0 || coluna == lado - 1) ? 1 : 0) +
        (grandeDiagonal.contains(casa) ? 2 : 0);
  }
  return tabela;
}

Uint8List _tabelaDeFundo(int cor) {
  final tabela = Uint8List(nCasas + 1);
  // A fileira de fundo de uma cor é a fileira de coroação da OUTRA — é para lá
  // que o adversário está indo, e é por isso que segurá-la vale alguma coisa.
  for (final casa in casasDeCoroacao[cor == brancas ? pretas : brancas]) {
    tabela[casa] = 1;
  }
  return tabela;
}

/// A nota **sempre do ponto de vista das brancas**, para relatório e conferência.
///
/// Uma passada só pelas 32 casas, somando os dois lados ao mesmo tempo. A versão
/// anterior varria o tabuleiro duas vezes — uma por cor — e isso aparecia na
/// medição da bancada.
int avaliarAbsoluto(Tabuleiro tabuleiro, [PesosAvaliacao pesos = pesosPadrao]) {
  var total = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    final conteudo = tabuleiro.casas[casa - 1];
    if (conteudo == vazia) continue;

    final bonusDaCasa = _bonusDeCasa[casa];
    final borda = (bonusDaCasa & 1) != 0 ? pesos.colunaDeBorda : 0;
    final diagonal = (bonusDaCasa & 2) != 0 ? pesos.grandeDiagonalPeso : 0;

    switch (conteudo) {
      case pedraBranca:
        total += pesos.pedra +
            _avancoDasBrancas[casa] * pesos.avancoPorFileira +
            (_fundoDasBrancas[casa] != 0 ? pesos.fileiraDeFundo : 0) +
            borda + diagonal;
      case damaBranca:
        total += pesos.dama + borda + diagonal;
      case pedraPreta:
        total -= pesos.pedra +
            _avancoDasPretas[casa] * pesos.avancoPorFileira +
            (_fundoDasPretas[casa] != 0 ? pesos.fileiraDeFundo : 0) +
            borda + diagonal;
      case damaPreta:
        total -= pesos.dama + borda + diagonal;
    }
  }
  return total;
}

/// A nota da posição, **do ponto de vista de quem tem a vez**.
///
/// Não sabe se a partida acabou — quem descobre isso é a busca, ao ver que não
/// sobrou lance legal.
int avaliar(Tabuleiro tabuleiro, [PesosAvaliacao pesos = pesosPadrao]) {
  final absoluto = avaliarAbsoluto(tabuleiro, pesos);
  return tabuleiro.vez == brancas ? absoluto : -absoluto;
}
