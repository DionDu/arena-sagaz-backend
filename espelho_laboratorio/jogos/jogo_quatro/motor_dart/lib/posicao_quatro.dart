// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// O bitboard de coluna-maior com uma linha de sentinela é a técnica pública
// descrita por John Tromp para o jogo resolvido por Allis (1988). Nenhuma linha
// foi copiada de implementação alheia (ver `LEIA-ME.md`).
//
// ── O bitboard, desenhado ────────────────────────────────────────────────────
//
// A posição inteira cabe em DOIS inteiros de 64 bits. Cada coluna ocupa
// `altura + 1` bits consecutivos, de baixo para cima; o bit a mais no topo de
// cada coluna é a SENTINELA, que fica sempre 0. Na tradicional (7 × 6):
//
//       col 1  col 2  col 3  ...  col 7
//        6     13     20          48     <- sentinela (sempre 0)
//        5     12     19          47     <- linha 6 (a de cima)
//        4     11     18          46
//        3     10     17          45
//        2      9     16          44
//        1      8     15          43
//        0      7     14          42     <- linha 1 (a de baixo)
//
// São 7 × 7 = 49 bits. O número do bit de uma casa é
// `(coluna - 1) × (altura + 1) + (linha - 1)`.
//
// Por que a sentinela: andar uma casa para o lado é deslocar `altura + 1` bits;
// andar na diagonal é deslocar `altura` ou `altura + 2`. Sem a linha vazia no
// topo, a diagonal que sai pelo alto de uma coluna "reapareceria" no pé da
// coluna seguinte, e a conta de alinhamento acharia linhas que não existem.
//
// Os dois inteiros:
//   - `mascara`:    1 em toda casa ocupada (das duas cores);
//   - `pecasDaVez`: 1 nas casas do jogador que joga AGORA.
// As peças do outro são `mascara ^ pecasDaVez` (o "ou exclusivo" tira da
// máscara as casas de quem joga e deixa as dele).

import 'regras_da_modalidade_quatro.dart';

/// Quantos bits o bitboard pode usar.
///
/// O inteiro do Dart tem 64 bits com sinal; o 64º é o sinal. Usando no máximo
/// 63, nenhuma conta (inclusive a chave `pecasDaVez + mascara`) fica negativa.
const int bitsDisponiveisQuatro = 63;

/// Confere se [dimensoes] cabem no bitboard; lança `ArgumentError` com a conta
/// quando não cabem.
///
/// É chamada por [PosicaoQuatro.inicial] e pelo catálogo, na leitura do
/// contrato: um tabuleiro que não cabe é recusado ANTES de alguém jogar nele.
void conferirQueCabeNoBitboard(DimensoesQuatro dimensoes) {
  final bits = (dimensoes.altura + 1) * dimensoes.largura;
  if (bits > bitsDisponiveisQuatro) {
    throw ArgumentError(
        'o tabuleiro ${dimensoes.largura} × ${dimensoes.altura} precisa de '
        '$bits bits ((altura + 1) × largura = '
        '(${dimensoes.altura} + 1) × ${dimensoes.largura}), e o bitboard tem '
        '$bitsDisponiveisQuatro');
  }
}

/// Uma posição do Quatro em Linha: as peças, de quem é a vez e quantos lances
/// já foram feitos. **Imutável**: jogar cria uma posição nova.
///
/// Os campos de bits são públicos porque a modalidade (que aplica os lances) e
/// a busca (que os lê milhões de vezes) trabalham direto neles. Quem está fora
/// do motor usa os acessos 1-based ([donoDaCasa], [alturaDaColuna]).
final class PosicaoQuatro {
  /// As dimensões do tabuleiro, vindas da modalidade.
  final DimensoesQuatro dimensoes;

  /// Bits das casas do jogador da vez.
  final int pecasDaVez;

  /// Bits de todas as casas ocupadas.
  final int mascara;

  /// Quantos lances (meios-lances) já foram feitos desde o tabuleiro vazio.
  ///
  /// É o lance, e não a contagem de peças, que decide de quem é a vez: numa
  /// modalidade que TIRA peças, o número de peças deixa de andar junto com o
  /// número de lances.
  final int lancesJogados;

  /// Construtor por dentro. Quem cria posição de fora usa [inicial],
  /// [deLances] ou [deBits].
  const PosicaoQuatro._(
      this.dimensoes, this.pecasDaVez, this.mascara, this.lancesJogados);

  /// O tabuleiro vazio da modalidade, com o Jogador 1 na vez.
  factory PosicaoQuatro.inicial(RegrasDaModalidadeQuatro regras) {
    conferirQueCabeNoBitboard(regras.dimensoes);
    return PosicaoQuatro._(regras.dimensoes, 0, 0, 0);
  }

  /// A posição depois da sequência de lances [sequencia] (`s4s4s3`), jogada
  /// pela [regras] a partir do tabuleiro vazio.
  ///
  /// Recusa (com [LanceIlegalQuatro]) lance ilegal e lance depois de a partida
  /// ter terminado; recusa (com `FormatException`) texto fora da notação.
  factory PosicaoQuatro.deLances(
      RegrasDaModalidadeQuatro regras, String sequencia) {
    var posicao = PosicaoQuatro.inicial(regras);
    final lances = lerSequenciaQuatro(sequencia, regras.tiposDeLance);
    for (var i = 0; i < lances.length; i++) {
      if (regras.desfecho(posicao) != null) {
        throw LanceIlegalQuatro(
            'lance ${i + 1} (${lances[i]}) depois do fim da partida');
      }
      posicao = regras.aplicar(posicao, lances[i]);
    }
    return posicao;
  }

  /// Monta uma posição direto dos bits. É a porta das MODALIDADES: é por aqui
  /// que `aplicar` devolve a posição nova.
  ///
  /// Confere o que é barato conferir: que [pecasDaVez] está dentro de
  /// [mascara] e que nenhum bit cai fora do tabuleiro (na sentinela ou além da
  /// última coluna).
  factory PosicaoQuatro.deBits({
    required DimensoesQuatro dimensoes,
    required int pecasDaVez,
    required int mascara,
    required int lancesJogados,
  }) {
    conferirQueCabeNoBitboard(dimensoes);
    if (pecasDaVez & ~mascara != 0) {
      throw ArgumentError('peças da vez fora da máscara');
    }
    if (mascara & ~mascaraDoTabuleiro(dimensoes) != 0) {
      throw ArgumentError('bit fora do tabuleiro (sentinela ou além da largura)');
    }
    if (lancesJogados < 0) {
      throw ArgumentError.value(lancesJogados, 'lancesJogados');
    }
    return PosicaoQuatro._(dimensoes, pecasDaVez, mascara, lancesJogados);
  }

  /// Monta uma posição direto dos bits SEM conferir nada.
  ///
  /// Existe para o caminho quente: a busca aplica milhões de lances, e a
  /// conferência de [deBits] percorre o tabuleiro a cada um. Só a modalidade
  /// chama, depois de ela mesma ter garantido que o lance é legal (e, com
  /// isso, que os bits continuam dentro do tabuleiro).
  const PosicaoQuatro.semConferir({
    required this.dimensoes,
    required this.pecasDaVez,
    required this.mascara,
    required this.lancesJogados,
  });

  /// `+1` quando é a vez do Jogador 1 (azul), `-1` quando é a do Jogador 2.
  ///
  /// O Jogador 1 joga nos lances de número par (0, 2, 4...), contando do zero.
  int get jogadorDaVez => lancesJogados.isEven ? 1 : -1;

  /// Bits das peças do Jogador 1.
  int get pecasDoJ1 => jogadorDaVez == 1 ? pecasDaVez : mascara ^ pecasDaVez;

  /// Bits das peças do Jogador 2.
  int get pecasDoJ2 => jogadorDaVez == -1 ? pecasDaVez : mascara ^ pecasDaVez;

  /// A chave de 64 bits desta posição, para a tabela de transposição.
  ///
  /// `pecasDaVez + mascara` identifica a posição. Por quê, coluna a coluna:
  /// numa coluna com `k` peças empilhadas, a máscara vale `2^k - 1` (os `k`
  /// bits de baixo ligados), e as peças da vez valem entre `0` e `2^k - 1`.
  /// A soma cai entre `2^k - 1` e `2^(k+1) - 2`: intervalos que não se
  /// encostam para `k` diferentes, então a soma diz a altura E quais peças são
  /// de quem. E a soma nunca passa de `k + 1` bits, que cabem na coluna graças
  /// à sentinela: nada "vai um" para a coluna vizinha.
  ///
  /// ⚠️ A chave não guarda de quem é a vez. Duas posições com as cores
  /// trocadas E a vez trocada dão a mesma chave, e têm de fato o mesmo valor
  /// para quem joga, que é o que a busca guarda.
  int get chave => pecasDaVez + mascara;

  /// Quantos bits o bitboard desta posição usa (`(altura + 1) × largura`; na
  /// tradicional, 49).
  int get bitsUsados => (dimensoes.altura + 1) * dimensoes.largura;

  /// Quem ocupa a casa (`coluna`, `linha`), ambas 1-based: `+1`, `-1` ou
  /// `null` (vazia).
  int? donoDaCasa(int coluna, int linha) {
    final bit = 1 << indiceDoBit(dimensoes, coluna, linha);
    if (mascara & bit == 0) return null;
    return pecasDoJ1 & bit != 0 ? 1 : -1;
  }

  /// Quantas peças há na [coluna] (1-based).
  int alturaDaColuna(int coluna) {
    final bitsDaColuna = mascara & mascaraDaColuna(dimensoes, coluna);
    // `bitCount` não existe para `int` no Dart; conta-se ligando a altura até
    // achar o primeiro bit vazio (as peças estão empilhadas sem buraco).
    var altura = 0;
    while (altura < dimensoes.altura &&
        bitsDaColuna & (1 << indiceDoBit(dimensoes, coluna, altura + 1)) != 0) {
      altura++;
    }
    return altura;
  }

  @override
  bool operator ==(Object other) =>
      other is PosicaoQuatro &&
      other.dimensoes == dimensoes &&
      other.pecasDaVez == pecasDaVez &&
      other.mascara == mascara &&
      other.lancesJogados == lancesJogados;

  @override
  int get hashCode =>
      Object.hash(dimensoes, pecasDaVez, mascara, lancesJogados);

  /// O tabuleiro desenhado em texto, de cima para baixo: `X` para o J1, `O`
  /// para o J2, `.` vazia. Serve a mensagens de teste e à depuração.
  @override
  String toString() {
    final texto = StringBuffer();
    for (var linha = dimensoes.altura; linha >= 1; linha--) {
      for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
        final dono = donoDaCasa(coluna, linha);
        texto.write(dono == null ? '.' : (dono == 1 ? 'X' : 'O'));
      }
      texto.write('\n');
    }
    return texto.toString();
  }
}

// ── As máscaras de apoio (por dentro do motor) ───────────────────────────────
//
// Funções puras sobre as dimensões, usadas pelas modalidades e pela busca. É
// aqui, e só aqui, que a coluna e a linha 1-based viram o índice 0-based do bit.

/// O número do bit da casa (`coluna`, `linha`), ambas 1-based.
int indiceDoBit(DimensoesQuatro dimensoes, int coluna, int linha) =>
    (coluna - 1) * (dimensoes.altura + 1) + (linha - 1);

/// Os bits de todas as casas jogáveis da [coluna] (1-based), sem a sentinela.
int mascaraDaColuna(DimensoesQuatro dimensoes, int coluna) =>
    ((1 << dimensoes.altura) - 1) << ((coluna - 1) * (dimensoes.altura + 1));

/// O bit da casa de baixo da [coluna] (1-based).
int bitDoFundo(DimensoesQuatro dimensoes, int coluna) =>
    1 << ((coluna - 1) * (dimensoes.altura + 1));

/// O bit da casa de cima da [coluna] (1-based); ligado na máscara = coluna
/// cheia.
int bitDoTopo(DimensoesQuatro dimensoes, int coluna) =>
    1 << (dimensoes.altura - 1 + (coluna - 1) * (dimensoes.altura + 1));

/// Os bits de todas as casas do tabuleiro (sem as sentinelas). Máscara igual a
/// isto = tabuleiro cheio.
int mascaraDoTabuleiro(DimensoesQuatro dimensoes) {
  var todas = 0;
  for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
    todas |= mascaraDaColuna(dimensoes, coluna);
  }
  return todas;
}

/// A casa 1-based de um número de bit (o inverso de [indiceDoBit]).
CasaQuatro casaDoBit(DimensoesQuatro dimensoes, int indice) => CasaQuatro(
    indice ~/ (dimensoes.altura + 1) + 1, indice % (dimensoes.altura + 1) + 1);
