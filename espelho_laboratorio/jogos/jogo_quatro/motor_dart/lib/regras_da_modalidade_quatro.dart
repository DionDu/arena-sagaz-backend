// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// A regra do jogo é a de domínio público, resolvida por Victor Allis (1988).
// Nenhuma linha foi copiada de implementação alheia (ver `LEIA-ME.md`).
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A **fronteira** entre o motor e a regra do jogo. A busca, a contagem de
// posições, a tela e o servidor falam com a modalidade só por esta interface:
// nenhum deles sabe se o tabuleiro tem 7 colunas ou 9, nem se existe outro tipo
// de lance além de "soltar". É isso que deixa variantes (o Pop Out, tabuleiros
// maiores) entrarem depois sem reescrever a busca (RF-QTR-010, R-03).
//
// Aqui moram também os tipos pequenos que atravessam essa fronteira: as
// dimensões, o lance, a casa, a linha vencedora, o desfecho e a NOTAÇÃO de texto
// do lance (`s4` = soltar na coluna 4), que é como a partida viaja entre o
// aparelho, o isolate, o log e o servidor.

import 'posicao_quatro.dart';

/// As regras de UMA modalidade do Quatro em Linha.
///
/// `abstract interface class` (Dart 3) quer dizer: só declara o que uma
/// modalidade sabe fazer, e quem a implementa escreve tudo; ninguém herda código
/// daqui. A implementação de hoje é a regra de gravidade
/// (`modalidade_gravidade_quatro.dart`); quem liga um id do contrato a uma
/// implementação é `catalogo_modalidades_quatro.dart`.
abstract interface class RegrasDaModalidadeQuatro {
  /// O identificador da modalidade, como aparece no contrato do jogo.
  String get id;

  /// Largura, altura e quantas peças é preciso alinhar.
  DimensoesQuatro get dimensoes;

  /// Os tipos de lance desta modalidade: a LETRA da notação → o NOME do tipo.
  ///
  /// Na regra de gravidade é um só (`s` → `soltar`). Uma modalidade que tire
  /// peças acrescenta outra letra, e a gramática da notação não muda.
  Map<String, String> get tiposDeLance;

  /// Os lances que o jogador da vez pode fazer em [posicao], numa ordem
  /// estável (da coluna 1 para a última, e, dentro da coluna, na ordem dos
  /// tipos). Vazia quando não há casa onde jogar.
  ///
  /// ⚠️ **Não olha o desfecho**: numa posição já vencida ela ainda lista as
  /// colunas livres. Quem precisa saber se a partida acabou pergunta a
  /// [desfecho] antes. É de propósito: a busca chama esta função milhões de
  /// vezes e já conferiu o fim por conta própria.
  List<LanceQuatro> lancesLegais(PosicaoQuatro posicao);

  /// A posição que resulta de [lance] em [posicao].
  ///
  /// **Imutável:** devolve uma posição nova e não mexe na recebida. Lance que
  /// não está em [lancesLegais] lança [LanceIlegalQuatro].
  PosicaoQuatro aplicar(PosicaoQuatro posicao, LanceQuatro lance);

  /// Como a partida terminou em [posicao], ou `null` se ainda não terminou.
  DesfechoQuatro? desfecho(PosicaoQuatro posicao);

  /// Os lances que dão a vitória IMEDIATA a quem tem a vez em [posicao]
  /// (vazia quando não há), na ordem de [lancesLegais].
  ///
  /// Dá para responder com [lancesLegais], [aplicar] e [desfecho], e é isso
  /// que uma modalidade simples pode fazer. Ela está na interface porque a
  /// busca pergunta isto em TODO nó (para descartar o lance que entrega a
  /// vitória ao outro), e a regra que conhece o próprio tabuleiro responde
  /// com algumas operações de bits, sem criar posição nenhuma. A resposta tem
  /// de ser a mesma da conta pelo caminho longo: o teste da modalidade
  /// confere as duas.
  List<LanceQuatro> lancesQueVencem(PosicaoQuatro posicao);
}

/// O tamanho do tabuleiro e a regra de alinhamento.
///
/// Vem SEMPRE da modalidade (e esta, do contrato): nenhum arquivo do motor
/// escreve `7` ou `6` à mão.
final class DimensoesQuatro {
  /// Quantas colunas (na tradicional, 7).
  final int largura;

  /// Quantas casas cada coluna empilha (na tradicional, 6).
  final int altura;

  /// Quantas peças em linha vencem (na tradicional, 4).
  final int alinhar;

  /// Cria as dimensões, recusando números que não formam um jogo.
  DimensoesQuatro({
    required this.largura,
    required this.altura,
    required this.alinhar,
  }) {
    // `ArgumentError.value` guarda o valor recusado e o nome do campo, o que
    // deixa a mensagem de erro dizer exatamente o que veio errado.
    if (largura < 1) {
      throw ArgumentError.value(largura, 'largura', 'precisa ser ao menos 1');
    }
    if (altura < 1) {
      throw ArgumentError.value(altura, 'altura', 'precisa ser ao menos 1');
    }
    if (alinhar < 2) {
      throw ArgumentError.value(alinhar, 'alinhar', 'precisa ser ao menos 2');
    }
  }

  /// Quantas casas o tabuleiro tem (na tradicional, 42).
  int get casas => largura * altura;

  @override
  bool operator ==(Object other) =>
      other is DimensoesQuatro &&
      other.largura == largura &&
      other.altura == altura &&
      other.alinhar == alinhar;

  @override
  int get hashCode => Object.hash(largura, altura, alinhar);

  @override
  String toString() => '$largura × $altura, alinhar $alinhar';
}

/// Um lance: o TIPO (o nome, como `soltar`) e a COLUNA.
///
/// ⚠️ A coluna é **1-based** (a coluna 1 é a da esquerda), porque é assim que
/// ela aparece na notação, no log e para quem joga. O índice 0-based do
/// bitboard existe só dentro de `posicao_quatro.dart`.
final class LanceQuatro {
  /// O nome do tipo do lance (`soltar`).
  final String tipo;

  /// A coluna, de 1 até a largura.
  final int coluna;

  /// Cria o lance. A coluna precisa ser positiva; se ela cabe no tabuleiro, é
  /// a modalidade quem diz (ela conhece a largura).
  LanceQuatro(this.tipo, this.coluna) {
    if (coluna < 1) {
      throw ArgumentError.value(coluna, 'coluna', 'a coluna começa em 1');
    }
  }

  @override
  bool operator ==(Object other) =>
      other is LanceQuatro && other.tipo == tipo && other.coluna == coluna;

  @override
  int get hashCode => Object.hash(tipo, coluna);

  @override
  String toString() => '$tipo@$coluna';
}

/// Uma casa do tabuleiro, **1-based**: coluna 1 à esquerda, linha 1 embaixo.
final class CasaQuatro {
  /// A coluna, de 1 até a largura.
  final int coluna;

  /// A linha, de 1 (a de baixo) até a altura.
  final int linha;

  /// Cria a casa.
  const CasaQuatro(this.coluna, this.linha);

  @override
  bool operator ==(Object other) =>
      other is CasaQuatro && other.coluna == coluna && other.linha == linha;

  @override
  int get hashCode => Object.hash(coluna, linha);

  @override
  String toString() => '($coluna,$linha)';
}

/// Uma linha vencedora: as casas alinhadas, em ordem ao longo da direção.
///
/// Cinco (ou mais) em linha na mesma direção são UMA linha só, com todas as
/// casas, e não duas linhas sobrepostas de quatro: é o que a tela desenha como
/// um traço único.
final class LinhaQuatro {
  /// As casas da linha, da primeira à última ao longo da direção.
  final List<CasaQuatro> casas;

  /// Cria a linha. A lista é guardada como não modificável.
  LinhaQuatro(List<CasaQuatro> casas) : casas = List.unmodifiable(casas);

  @override
  bool operator ==(Object other) {
    if (other is! LinhaQuatro || other.casas.length != casas.length) {
      return false;
    }
    for (var i = 0; i < casas.length; i++) {
      if (other.casas[i] != casas[i]) return false;
    }
    return true;
  }

  // `Object.hashAll` combina o hash de todos os itens de uma lista.
  @override
  int get hashCode => Object.hashAll(casas);

  @override
  String toString() => 'Linha$casas';
}

/// Como a partida terminou.
///
/// `vencedor` é `+1` (Jogador 1, o azul), `-1` (Jogador 2, o vermelho) ou
/// `null` para empate. Na vitória, `linhas` traz TODAS as linhas formadas (um
/// mesmo lance pode fechar duas); no empate, vem vazia.
final class DesfechoQuatro {
  /// `+1`, `-1`, ou `null` no empate.
  final int? vencedor;

  /// As linhas vencedoras (vazia no empate).
  final List<LinhaQuatro> linhas;

  /// Vitória de [vencedor] (`+1` ou `-1`) com as [linhas] que a formaram.
  DesfechoQuatro.vitoria(int this.vencedor, List<LinhaQuatro> linhas)
      : linhas = List.unmodifiable(linhas) {
    if (vencedor != 1 && vencedor != -1) {
      throw ArgumentError.value(vencedor, 'vencedor', 'só +1 ou -1');
    }
    if (linhas.isEmpty) {
      throw ArgumentError('vitória sem linha vencedora');
    }
  }

  /// Empate: o tabuleiro encheu sem linha.
  DesfechoQuatro.empate()
      : vencedor = null,
        linhas = const [];

  /// Atalho de leitura.
  bool get empatou => vencedor == null;

  @override
  String toString() =>
      empatou ? 'empate' : 'vitória de ${vencedor! > 0 ? 'J1' : 'J2'} $linhas';
}

/// A modalidade pedida não existe no catálogo (ou o contrato é inválido para
/// ela). É uma exceção, e não um `null`, de propósito: um id desconhecido que
/// caísse em silêncio na modalidade padrão faria o aparelho jogar uma regra
/// diferente da que o servidor julga.
final class ModalidadeDesconhecida implements Exception {
  /// O id pedido (ou o problema encontrado no contrato).
  final String mensagem;

  /// Cria a exceção com a explicação.
  ModalidadeDesconhecida(this.mensagem);

  @override
  String toString() => 'ModalidadeDesconhecida: $mensagem';
}

/// Um lance que a modalidade não aceita na posição (coluna cheia, coluna fora
/// do tabuleiro, tipo que ela não tem, ou partida já terminada).
final class LanceIlegalQuatro implements Exception {
  /// O que estava errado.
  final String mensagem;

  /// Cria a exceção com a explicação.
  LanceIlegalQuatro(this.mensagem);

  @override
  String toString() => 'LanceIlegalQuatro: $mensagem';
}

// ── A notação de texto ───────────────────────────────────────────────────────
//
// Um lance é `<letra do tipo><coluna 1-based>`: `s4` = soltar na coluna 4. A
// partida é a concatenação: `s4s4s3`. A coluna pode ter mais de um dígito
// (`s12`, num tabuleiro largo): como a letra é sempre uma letra e a coluna só
// dígitos, a leitura nunca fica ambígua.

/// Um lance na notação: uma letra minúscula e a coluna sem zero à esquerda.
///
/// Expressão regular, peça a peça: `^` e `$` prendem o texto inteiro;
/// `([a-z])` captura a letra; `([1-9][0-9]*)` captura a coluna, começando por
/// um dígito de 1 a 9 (isso recusa `s0` e `s04`).
final RegExp _lanceUnico = RegExp(r'^([a-z])([1-9][0-9]*)$');

/// Um "pedaço" da sequência: uma letra seguida de dígitos. Serve para fatiar
/// `s4s12t3` em `s4`, `s12`, `t3`; cada pedaço passa depois por [_lanceUnico].
final RegExp _pedacoDaSequencia = RegExp(r'[a-z][0-9]*');

/// Lê UM lance na notação (`s4`), com as letras de [tiposDeLance].
///
/// Lança `FormatException` com a explicação quando o texto não é um lance ou a
/// letra não é de um tipo que a modalidade tem.
LanceQuatro lerLanceQuatro(String texto, Map<String, String> tiposDeLance) {
  final achado = _lanceUnico.firstMatch(texto);
  if (achado == null) {
    throw FormatException(
        'lance fora da notação (letra + coluna a partir de 1): "$texto"');
  }
  // `group(1)` é o que a 1ª parte entre parênteses capturou (a letra); o `!`
  // afirma que não é nulo, o que a expressão garante quando casou.
  final letra = achado.group(1)!;
  final tipo = tiposDeLance[letra];
  if (tipo == null) {
    throw FormatException('tipo de lance desconhecido: "$letra" em "$texto"');
  }
  return LanceQuatro(tipo, int.parse(achado.group(2)!));
}

/// Escreve [lance] na notação, com as letras de [tiposDeLance].
String escreverLanceQuatro(LanceQuatro lance, Map<String, String> tiposDeLance) {
  // Procura a letra cujo nome é o tipo do lance (o mapa vai da letra ao nome).
  for (final entrada in tiposDeLance.entries) {
    if (entrada.value == lance.tipo) return '${entrada.key}${lance.coluna}';
  }
  throw ArgumentError.value(lance.tipo, 'tipo', 'sem letra nesta modalidade');
}

/// Lê uma partida inteira (`s4s4s3`). Texto vazio é a partida sem lances.
///
/// Recusa (com `FormatException`) qualquer caractere que não forme um lance:
/// a sequência tem de ser consumida inteira, sem sobra.
List<LanceQuatro> lerSequenciaQuatro(
    String sequencia, Map<String, String> tiposDeLance) {
  final lances = <LanceQuatro>[];
  var consumido = 0;
  for (final pedaco in _pedacoDaSequencia.allMatches(sequencia)) {
    // Um pedaço que não começa onde o anterior terminou quer dizer que havia
    // lixo entre os dois (um espaço, um dígito solto no começo...).
    if (pedaco.start != consumido) break;
    lances.add(lerLanceQuatro(pedaco.group(0)!, tiposDeLance));
    consumido = pedaco.end;
  }
  if (consumido != sequencia.length) {
    throw FormatException(
        'sequência de lances com trecho fora da notação', sequencia, consumido);
  }
  return lances;
}

/// Escreve uma partida inteira (a concatenação dos lances).
String escreverSequenciaQuatro(
        Iterable<LanceQuatro> lances, Map<String, String> tiposDeLance) =>
    lances.map((l) => escreverLanceQuatro(l, tiposDeLance)).join();
