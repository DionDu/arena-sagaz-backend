/// Tabuleiro de damas 8x8 em Dart: geometria das 32 casas, estado e FEN.
///
/// Este arquivo é o **port** de `../motor/tabuleiro_damas.py`. A versão em
/// Python é o motor de referência — ela existe para estar certa e para ser lida.
/// Esta aqui existe para ser **rápida**, porque é ela que vai rodar dentro do
/// app, no celular do jogador.
///
/// Por que duas implementações e não uma
/// -------------------------------------
/// Porque uma confere a outra. O motor em Python já bate com o `perft`
/// publicado para damas anglo-americanas até 845.931 folhas; este port tem de
/// reproduzir exatamente os mesmos números. Duas implementações escritas em
/// linguagens diferentes chegando ao mesmo resultado é evidência bem mais forte
/// do que uma implementação passando nos próprios testes.
///
/// Regra ao mexer aqui: **mudança de regra nasce no Python**, é conferida lá, e
/// só então desce para o Dart. Nunca o contrário — senão o motor de referência
/// deixa de ser referência.
library;

import 'dart:math';
import 'dart:typed_data';

/// Lado do tabuleiro. 8 aqui; 10 nas damas internacionais, fora de escopo.
const int lado = 8;

/// Casas jogáveis por fileira: 4. Numa fileira de 8 casas, metade é escura.
const int casasPorFileira = lado ~/ 2;

/// Total de casas jogáveis: 32. É o tamanho do vetor que guarda a posição.
const int nCasas = lado * lado ~/ 2;

// O que pode ocupar uma casa. São `int` e não `enum` de propósito: o vetor da
// posição é um `Uint8List`, e a busca compara estes valores milhões de vezes por
// segundo. Os números são os mesmos do Python e do §5.2 do documento didático.
const int vazia = 0;
const int pedraBranca = 1;
const int damaBranca = 2;
const int pedraPreta = 3;
const int damaPreta = 4;

/// De quem é a vez, e de quem é uma peça.
const int brancas = 0;
const int pretas = 1;

// As quatro diagonais. "Cima" é a fileira 0, onde as PRETAS começam — logo, é
// para onde as BRANCAS avançam.
const int cimaEsquerda = 0;
const int cimaDireita = 1;
const int baixoEsquerda = 2;
const int baixoDireita = 3;

const List<int> _passoLinha = [-1, -1, 1, 1];
const List<int> _passoColuna = [-1, 1, -1, 1];

/// Para onde cada cor avança. Importa só para a pedra, que anda só para frente.
const List<List<int>> direcoesDeAvanco = [
  [cimaEsquerda, cimaDireita], // brancas
  [baixoEsquerda, baixoDireita], // pretas
];

/// Diz se a casa (linha, coluna) é escura — ou seja, se peça pode pisar nela.
///
/// Ímpar = escura, para que o canto inferior esquerdo seja jogável, que é como
/// um tabuleiro de damas é montado de verdade.
bool eCasaJogavel(int linha, int coluna) => (linha + coluna) % 2 == 1;

/// Converte (linha, coluna) no número da casa, de 1 a 32. Zero se for casa clara.
///
/// Devolve 0 — e não `null` — para não pagar *boxing* num caminho que a geração
/// de lances percorre o tempo todo. Casa 0 não existe, então o valor é seguro
/// como marcador de "não tem".
int numeroDaCasa(int linha, int coluna) {
  if (linha < 0 || linha >= lado || coluna < 0 || coluna >= lado) return 0;
  if (!eCasaJogavel(linha, coluna)) return 0;
  return linha * casasPorFileira + coluna ~/ 2 + 1;
}

/// Converte o número da casa (1 a 32) no par (linha, coluna).
(int, int) linhaColuna(int casa) {
  final indice = casa - 1;
  final linha = indice ~/ casasPorFileira;
  final posicaoNaLinha = indice % casasPorFileira;
  final deslocamento = linha % 2 == 0 ? 1 : 0;
  return (linha, posicaoNaLinha * 2 + deslocamento);
}

/// De que cor é esta peça. -1 para casa vazia.
int corDaPeca(int peca) {
  if (peca == pedraBranca || peca == damaBranca) return brancas;
  if (peca == pedraPreta || peca == damaPreta) return pretas;
  return -1;
}

/// É dama? (as duas cores)
bool eDama(int peca) => peca == damaBranca || peca == damaPreta;

// ---------------------------------------------------------------------------
// Diagonais
// ---------------------------------------------------------------------------
//
// Em damas tudo anda na diagonal, então o gerador não pergunta "quais casas
// existem?", pergunta "o que há nesta diagonal a partir daqui?". A tabela abaixo
// responde de uma vez, montada na carga do programa.
//
// Indexada por `[casa - 1][direcao]`. O achatamento em uma lista só, que seria
// mais rápido, fica para quando a medição pedir — hoje o gargalo não está aqui.

final List<List<Int8List>> _raios = _construirRaios();

List<List<Int8List>> _construirRaios() {
  return List.generate(nCasas, (indice) {
    final casa = indice + 1;
    final (linha, coluna) = linhaColuna(casa);
    return List.generate(4, (direcao) {
      final caminho = <int>[];
      var l = linha + _passoLinha[direcao];
      var c = coluna + _passoColuna[direcao];
      while (l >= 0 && l < lado && c >= 0 && c < lado) {
        // Nunca é 0: vizinho diagonal de casa escura é casa escura.
        caminho.add(numeroDaCasa(l, c));
        l += _passoLinha[direcao];
        c += _passoColuna[direcao];
      }
      return Int8List.fromList(caminho);
    });
  });
}

/// As casas a partir de [casa] na [direcao], em ordem, até a borda.
///
/// É o que a **dama voadora** percorre. Vazio se a casa já está na borda.
Int8List raio(int casa, int direcao) => _raios[casa - 1][direcao];

/// A casa imediatamente adjacente na diagonal, ou 0 se for fora do tabuleiro.
///
/// É o passo da **pedra**, que anda uma casa de cada vez.
int vizinho(int casa, int direcao) {
  final caminho = _raios[casa - 1][direcao];
  return caminho.isEmpty ? 0 : caminho[0];
}

/// A grande diagonal escura: as 8 casas do canto 4 ao canto 29.
///
/// As Regras Oficiais mandam que ela fique à esquerda de cada damista, e o
/// art. 100 declara empate o final de três damas contra uma dama **nela**.
const Set<int> grandeDiagonal = {4, 8, 11, 15, 18, 22, 25, 29};

/// O **«Rio»** das damas portuguesas (FPD 2.3) — e é a MESMA diagonal de cima.
///
/// O regulamento português batiza a grande diagonal de "Rio" e constrói a
/// "Forçada" (3.8.a) em cima dela. O apelido existe para que a busca por
/// qualquer um dos dois termos chegue aqui, e o `=` declara em código que são a
/// mesma coisa.
///
/// ⚠️ Não era óbvio: a definição do Rio **não está no texto** daquele
/// regulamento, está numa figura da página 7. E os dois tabuleiros são espelhos
/// (FPD 1.2 põe a diagonal longa à direita de cada jogador; o CBJD, à esquerda),
/// de modo que converter a numeração com `33 - k` — que é o que parece — rasga a
/// diagonal. Ver `docs/imagens/60_o_rio_e_a_forcada.png` e o docstring de
/// `casa_da_numeracao_portuguesa` no Python.
const Set<int> rio = grandeDiagonal;

/// Casas de coroação de cada cor: a última fileira do lado do adversário.
const List<Set<int>> casasDeCoroacao = [
  {1, 2, 3, 4}, // brancas coroam em cima
  {29, 30, 31, 32}, // pretas coroam embaixo
];

// ---------------------------------------------------------------------------
// Hash de Zobrist
// ---------------------------------------------------------------------------
//
// Cada combinação (casa, peça) recebe um número aleatório de 64 bits; o hash da
// posição é o XOR de todos os que estão em jogo, mais um número para "é a vez
// das pretas". A propriedade que torna isso valioso é o XOR ser **reversível**:
// tirar uma peça de uma casa é o mesmo XOR que pôr — então o hash pode ser
// ATUALIZADO a cada alteração, em vez de recalculado varrendo as 32 casas.
//
// Isso mora aqui, e não na busca, por um motivo medido: recalcular o hash a cada
// nó custava caro o bastante para aparecer no relatório da bancada. Mantendo-o
// dentro do `Tabuleiro`, cada `escrever` paga um XOR e o nó de busca não paga
// varredura nenhuma.
//
// Semente fixa de propósito: o hash precisa ser o mesmo em toda execução, senão
// duas rodadas do mesmo teste podem divergir por colisão diferente — e um bug
// que só aparece às vezes é o pior tipo de bug.

final List<Int64List> _zobristPeca = () {
  final sorteio = Random(20260724);
  int aleatorio64() =>
      sorteio.nextInt(1 << 32) | (sorteio.nextInt(1 << 32) << 32);
  return List.generate(
    nCasas + 1,
    (_) => Int64List.fromList(List.generate(5, (_) => aleatorio64())),
  );
}();

final int _zobristVezDasPretas = () {
  final sorteio = Random(20260725);
  return sorteio.nextInt(1 << 32) | (sorteio.nextInt(1 << 32) << 32);
}();

// ---------------------------------------------------------------------------
// O estado de uma posição
// ---------------------------------------------------------------------------

/// Uma posição de damas: o que há em cada uma das 32 casas, e de quem é a vez.
///
/// `casas[0]` é a **casa 1** e `casas[31]` é a **casa 32**. Esse "menos um" fica
/// contido em [ler] e [escrever]; todo o resto do código fala em número de casa.
///
/// `Uint8List` e não `List<int>`: é um bloco contínuo de bytes, sem indireção
/// por elemento. Numa busca que visita milhões de posições por segundo, a
/// diferença aparece.
class Tabuleiro {
  final Uint8List casas;

  int _vez;
  int _hash;

  /// De quem é a vez. Trocar a vez atualiza o hash junto — por isso é
  /// propriedade e não campo público.
  int get vez => _vez;
  set vez(int novaVez) {
    if (novaVez == _vez) return;
    _hash ^= _zobristVezDasPretas;
    _vez = novaVez;
  }

  /// O hash de Zobrist desta posição, mantido incrementalmente.
  ///
  /// Ler é de graça: quem paga é cada [escrever], com um XOR. Recalcular
  /// varrendo as 32 casas a cada nó de busca custava caro o bastante para
  /// aparecer na medição da bancada.
  int get hash => _hash;

  Tabuleiro._(this.casas, this._vez, this._hash);

  /// Tabuleiro sem nenhuma peça.
  factory Tabuleiro.vazio({int vez = brancas}) => Tabuleiro._(
      Uint8List(nCasas), vez, vez == pretas ? _zobristVezDasPretas : 0);

  /// A posição de começo de partida: 12 peças de cada lado.
  ///
  /// Quem começa **muda conforme a variante** — brancas nas brasileiras, pretas
  /// nas anglo-americanas — por isso a vez é parâmetro e não constante.
  factory Tabuleiro.inicial({int vez = brancas}) {
    final tabuleiro = Tabuleiro.vazio(vez: vez);
    for (var casa = 1; casa <= 12; casa++) {
      tabuleiro.escrever(casa, pedraPreta);
    }
    for (var casa = 21; casa <= nCasas; casa++) {
      tabuleiro.escrever(casa, pedraBranca);
    }
    return tabuleiro;
  }

  /// Lê uma posição escrita no FEN de damas: `W:W21,22,K23:B1,2,K5`.
  ///
  /// `K` antes do número marca dama (de *king*). Aceita as duas ordens de bloco
  /// e lista vazia. Lança [FormatException] em texto malformado — posição lida
  /// pela metade contamina tudo o que vem depois.
  factory Tabuleiro.deFen(String texto) {
    final partes = texto.trim().split(':').map((p) => p.trim()).toList();
    if (partes.length != 3) {
      throw FormatException('FEN de damas precisa de 3 partes: $texto');
    }

    final letraVez = partes[0].toUpperCase();
    if (letraVez != 'W' && letraVez != 'B') {
      throw FormatException('lado a jogar deve ser W ou B: $texto');
    }
    final tabuleiro = Tabuleiro.vazio(vez: letraVez == 'W' ? brancas : pretas);

    for (final bloco in partes.sublist(1)) {
      if (bloco.isEmpty) throw FormatException('bloco vazio em $texto');
      final letraCor = bloco[0].toUpperCase();
      if (letraCor != 'W' && letraCor != 'B') {
        throw FormatException('bloco deve começar com W ou B: $bloco');
      }
      final cor = letraCor == 'W' ? brancas : pretas;
      final pecaSimples = cor == brancas ? pedraBranca : pedraPreta;
      final pecaDama = cor == brancas ? damaBranca : damaPreta;

      for (final item in bloco.substring(1).split(',')) {
        final limpo = item.trim();
        if (limpo.isEmpty) continue;
        final ehDama = limpo[0].toUpperCase() == 'K';
        final numero = int.tryParse(ehDama ? limpo.substring(1) : limpo);
        if (numero == null || numero < 1 || numero > nCasas) {
          throw FormatException('casa inválida no FEN: $item');
        }
        if (tabuleiro.ler(numero) != vazia) {
          throw FormatException('casa $numero declarada duas vezes: $texto');
        }
        tabuleiro.escrever(numero, ehDama ? pecaDama : pecaSimples);
      }
    }
    return tabuleiro;
  }

  /// O que há na casa (1 a 32).
  int ler(int casa) => casas[casa - 1];

  /// Põe (ou apaga, com [vazia]) uma peça na casa (1 a 32).
  ///
  /// Dois XOR por escrita: um tira do hash o que estava lá, outro põe o que
  /// passou a estar. Como XOR é o seu próprio inverso, tirar e pôr são a mesma
  /// operação — é o que faz a atualização incremental funcionar.
  void escrever(int casa, int peca) {
    final anterior = casas[casa - 1];
    if (anterior == peca) return;
    if (anterior != vazia) _hash ^= _zobristPeca[casa][anterior];
    if (peca != vazia) _hash ^= _zobristPeca[casa][peca];
    casas[casa - 1] = peca;
  }

  /// Apaga todas as peças e define de quem é a vez, reaproveitando este objeto.
  ///
  /// Existe para a **análise retrógrada**, que reconstrói centenas de milhões de
  /// posições a partir do índice. Alocar um `Tabuleiro` por índice põe o coletor
  /// de lixo no caminho crítico; limpar e reescrever não aloca nada.
  ///
  /// O hash volta ao estado de tabuleiro vazio — não dá para "desfazer" os XOR um
  /// a um sem saber o que havia, então ele é recomposto do zero aqui.
  void limpar({int vez = brancas}) {
    casas.fillRange(0, nCasas, vazia);
    _vez = vez;
    _hash = vez == pretas ? _zobristVezDasPretas : 0;
  }

  /// Cópia independente. Mexer nela não mexe nesta.
  Tabuleiro clonar() => Tabuleiro._(Uint8List.fromList(casas), _vez, _hash);

  /// Os números das casas ocupadas por peças de uma cor, em ordem.
  List<int> casasDe(int cor) {
    final resultado = <int>[];
    final simples = cor == brancas ? pedraBranca : pedraPreta;
    final dama = cor == brancas ? damaBranca : damaPreta;
    for (var indice = 0; indice < nCasas; indice++) {
      final conteudo = casas[indice];
      if (conteudo == simples || conteudo == dama) resultado.add(indice + 1);
    }
    return resultado;
  }

  /// Escreve a posição no formato FEN de damas, em ordem crescente de casa.
  String paraFen() {
    String lista(int pecaSimples, int pecaDama) {
      final partes = <String>[];
      for (var casa = 1; casa <= nCasas; casa++) {
        final conteudo = ler(casa);
        if (conteudo == pecaSimples) {
          partes.add('$casa');
        } else if (conteudo == pecaDama) {
          partes.add('K$casa');
        }
      }
      return partes.join(',');
    }

    final letra = vez == brancas ? 'W' : 'B';
    return '$letra:W${lista(pedraBranca, damaBranca)}'
        ':B${lista(pedraPreta, damaPreta)}';
  }

  @override
  String toString() => paraFen();
}
