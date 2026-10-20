// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// O catálogo liga o id de uma modalidade, como ele aparece no contrato do jogo
// (`contrato_quatro.json`), à classe que implementa a regra dela. E confere o
// contrato antes de deixar alguém jogar com ele.
//
// ⚠️ É **o único arquivo de código** com o nome da modalidade de hoje escrito
// entre aspas. Todo o resto (a busca, a tela, o servidor) recebe a modalidade
// pronta e não sabe qual é. O cadeado `test/literal_tradicional_quatro_test.dart`
// (e o irmão dele no app) falha se o nome aparecer entre aspas em outro arquivo:
// é o que garante que uma variante nova entra por DADO, e não por `if`
// espalhado (R-03, RF-QTR-020).
//
// ⚠️ O motor não abre arquivo: quem chama lê o JSON (o app pelo asset, o
// servidor pelo espelho, a bancada pelo caminho) e entrega o `Map` decodificado.

import 'modalidade_gravidade_quatro.dart';
import 'politica_dificuldade_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// Um contrato que existe mas não pode ser usado (marcador no lugar de um
/// número, probabilidades que não somam 1, nível sem configuração...).
///
/// É diferente de [ModalidadeDesconhecida]: lá o id não existe; aqui o id
/// existe e o conteúdo dele está errado.
final class ContratoQuatroInvalido implements Exception {
  /// O que está errado, com o caminho do campo no JSON.
  final String mensagem;

  /// Cria a exceção com a explicação.
  ContratoQuatroInvalido(this.mensagem);

  @override
  String toString() => 'ContratoQuatroInvalido: $mensagem';
}

/// Uma fábrica de regras: recebe o id e as dimensões lidas do contrato.
///
/// `typedef` dá nome a um tipo de função, para o mapa abaixo ficar legível.
typedef _FabricaDeRegras = RegrasDaModalidadeQuatro Function(
    String id, DimensoesQuatro dimensoes);

/// Os ids que o motor sabe jogar → quem cria as regras de cada um.
///
/// Uma modalidade nova com a mesma regra e outro tamanho entra só no contrato,
/// com outro id, e uma linha aqui apontando para a mesma fábrica. Uma regra
/// nova (o Pop Out) ganha a sua classe e a sua linha.
final Map<String, _FabricaDeRegras> _fabricas = {
  'tradicional': (id, dimensoes) =>
      ModalidadeGravidadeQuatro(id: id, dimensoes: dimensoes),
};

/// As regras da modalidade [id] do [contrato], conferido por inteiro.
///
/// Lança [ModalidadeDesconhecida] quando o id não está no contrato ou o motor
/// não sabe jogá-lo; lança [ContratoQuatroInvalido] quando a entrada dele está
/// errada. Recusa, entre outros:
///   - `teto_de_nos` zero ou negativo (o zero é o MARCADOR de "ainda não
///     medido"; um contrato com marcador não carrega);
///   - `abertura_do_magno` que não soma 1;
///   - `percebe` sem uma das três situações, com uma que o motor não
///     conhece, ou com chance fora de 0 a 1;
///   - nível em `niveis` que não está em `niveis_disponiveis`, e o contrário;
///   - dimensões que não cabem nos 63 bits do bitboard;
///   - `tipos_de_lance` diferente do que a regra implementada declara.
RegrasDaModalidadeQuatro carregarModalidade(
    Map<String, Object?> contrato, String id) {
  final porModalidade = contrato['por_modalidade'];
  if (porModalidade is! Map<String, Object?>) {
    throw ContratoQuatroInvalido('falta o objeto "por_modalidade"');
  }
  final entrada = porModalidade[id];
  final fabrica = _fabricas[id];
  if (entrada == null || fabrica == null) {
    throw ModalidadeDesconhecida(entrada == null
        ? 'o contrato não tem a modalidade "$id"'
        : 'o motor não sabe jogar a modalidade "$id"');
  }
  if (entrada is! Map<String, Object?>) {
    throw ContratoQuatroInvalido('"por_modalidade.$id" não é um objeto');
  }
  final caminho = 'por_modalidade.$id';

  // ── As dimensões ──
  final dimensoes = DimensoesQuatro(
    largura: _inteiro(entrada, 'largura', caminho),
    altura: _inteiro(entrada, 'altura', caminho),
    alinhar: _inteiro(entrada, 'alinhar', caminho),
  );
  try {
    conferirQueCabeNoBitboard(dimensoes);
  } on ArgumentError catch (erro) {
    throw ContratoQuatroInvalido('$caminho: ${erro.message}');
  }
  final regras = fabrica(id, dimensoes);

  // ── Os tipos de lance têm de ser os que a regra implementa ──
  final tipos = entrada['tipos_de_lance'];
  if (tipos is! Map<String, Object?> ||
      tipos.length != regras.tiposDeLance.length ||
      tipos.entries.any((t) => regras.tiposDeLance[t.key] != t.value)) {
    throw ContratoQuatroInvalido('$caminho.tipos_de_lance ($tipos) diferente '
        'do que a regra implementa (${regras.tiposDeLance})');
  }

  // ── Os níveis ──
  final disponiveis = entrada['niveis_disponiveis'];
  final niveis = entrada['niveis'];
  if (disponiveis is! List<Object?> || niveis is! Map<String, Object?>) {
    throw ContratoQuatroInvalido(
        '$caminho precisa de "niveis_disponiveis" (lista) e "niveis" (objeto)');
  }
  for (final nome in niveis.keys) {
    if (!disponiveis.contains(nome)) {
      throw ContratoQuatroInvalido('$caminho.niveis.$nome não está em '
          'niveis_disponiveis $disponiveis');
    }
  }
  for (final nome in disponiveis) {
    final nivel = niveis[nome];
    if (nivel is! Map<String, Object?>) {
      throw ContratoQuatroInvalido(
          '$caminho.niveis_disponiveis tem "$nome", sem configuração em niveis');
    }
    final teto = _inteiro(nivel, 'teto_de_nos', '$caminho.niveis.$nome');
    if (teto <= 0) {
      throw ContratoQuatroInvalido('$caminho.niveis.$nome.teto_de_nos = $teto: '
          'o zero é o marcador de "ainda não medido" (fase 1a/1b)');
    }
    final epsilon = nivel['epsilon'];
    if (epsilon is! num || epsilon < 0 || epsilon > 1) {
      throw ContratoQuatroInvalido(
          '$caminho.niveis.$nome.epsilon = $epsilon: precisa estar entre 0 e 1');
    }
    // A chance de perceber cada situação (§8zzzf; até 14/10/2026 era a
    // lista "nunca erra"): as TRÊS que o motor conhece, nem uma a mais nem uma
    // a menos, cada uma de 0 a 1. Uma chave faltando faria a política tratar
    // a situação como "sem filtro", e um erro de digitação viraria, em
    // silêncio, um personagem que erra o que não devia.
    final percebe = nivel['percebe'];
    if (percebe is! Map<String, Object?> ||
        percebe.length != filtrosConhecidosQuatro.length ||
        !filtrosConhecidosQuatro.every(percebe.containsKey) ||
        percebe.values.any((p) => p is! num || p < 0 || p > 1)) {
      throw ContratoQuatroInvalido('$caminho.niveis.$nome.percebe = '
          '$percebe: precisa ter as chances (de 0 a 1) de '
          '$filtrosConhecidosQuatro, e só elas');
    }
  }

  // ── A abertura do Magno: colunas válidas, probabilidades que somam 1 ──
  final abertura = entrada['abertura_do_magno'];
  if (abertura is! Map<String, Object?>) {
    throw ContratoQuatroInvalido('$caminho.abertura_do_magno não é um objeto');
  }
  var soma = 0.0;
  for (final parte in abertura.entries) {
    final coluna = int.tryParse(parte.key);
    final peso = parte.value;
    if (coluna == null || coluna < 1 || coluna > dimensoes.largura) {
      throw ContratoQuatroInvalido(
          '$caminho.abertura_do_magno: coluna "${parte.key}" fora do tabuleiro');
    }
    if (peso is! num || peso < 0) {
      throw ContratoQuatroInvalido(
          '$caminho.abertura_do_magno."${parte.key}" = $peso');
    }
    soma += peso;
  }
  // Tolerância de um bilionésimo: somar decimais em ponto flutuante raramente
  // dá 1 exato (0,1 + 0,2 = 0,30000000000000004).
  if ((soma - 1).abs() > 1e-9) {
    throw ContratoQuatroInvalido(
        '$caminho.abertura_do_magno soma $soma, e não 1');
  }

  return regras;
}

/// Lê o campo inteiro [campo] de [objeto], ou recusa com o caminho no JSON.
int _inteiro(Map<String, Object?> objeto, String campo, String caminho) {
  final valor = objeto[campo];
  if (valor is! int) {
    throw ContratoQuatroInvalido('$caminho.$campo = $valor: precisa ser inteiro');
  }
  return valor;
}
