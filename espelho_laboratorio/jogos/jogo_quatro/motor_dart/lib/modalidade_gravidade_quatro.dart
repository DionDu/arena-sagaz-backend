// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// A regra é a de domínio público, resolvida por Victor Allis (1988); a conta
// de alinhamento por deslocamento de bits é a técnica pública do bitboard de
// coluna-maior (John Tromp). Nenhuma linha foi copiada de implementação alheia.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A regra de GRAVIDADE: a peça é solta no alto de uma coluna e cai até a
// primeira casa vazia; vence quem alinhar `alinhar` peças na horizontal, na
// vertical ou numa das duas diagonais; tabuleiro cheio sem linha é empate.
//
// É a regra da modalidade tradicional, mas este arquivo não sabe disso: ele
// recebe o id e as dimensões de quem o cria (o catálogo). Por isso uma variante
// de tabuleiro maior, com a mesma regra, reaproveita esta classe sem mudança.

import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

/// O nome do único tipo de lance da regra de gravidade.
const String tipoSoltarQuatro = 'soltar';

/// A regra de gravidade, para qualquer tamanho de tabuleiro que caiba no
/// bitboard.
final class ModalidadeGravidadeQuatro implements RegrasDaModalidadeQuatro {
  @override
  final String id;

  @override
  final DimensoesQuatro dimensoes;

  /// Uma letra só: `s` = soltar.
  @override
  Map<String, String> get tiposDeLance => const {'s': tipoSoltarQuatro};

  /// Os bits de todas as casas: máscara igual a isto = tabuleiro cheio.
  /// Calculado uma vez, na criação, porque `desfecho` pergunta a cada posição.
  final int _tabuleiroCheio;

  /// O bit de baixo de cada coluna, todos juntos (a "linha do chão").
  final int _fundos;

  /// Cria a regra com o [id] e as [dimensoes] lidos do contrato.
  ///
  /// A lista de inicialização (depois dos `:`) confere o tamanho ANTES de
  /// calcular a máscara: um tabuleiro que não cabe é recusado com a conta.
  ModalidadeGravidadeQuatro({required this.id, required this.dimensoes})
      : _tabuleiroCheio = _conferirECalcularCheio(dimensoes),
        _fundos = _calcularFundos(dimensoes);

  static int _calcularFundos(DimensoesQuatro dimensoes) {
    var fundos = 0;
    for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
      fundos |= bitDoFundo(dimensoes, coluna);
    }
    return fundos;
  }

  static int _conferirECalcularCheio(DimensoesQuatro dimensoes) {
    conferirQueCabeNoBitboard(dimensoes);
    return mascaraDoTabuleiro(dimensoes);
  }

  @override
  List<LanceQuatro> lancesLegais(PosicaoQuatro posicao) {
    final lances = <LanceQuatro>[];
    for (var coluna = 1; coluna <= dimensoes.largura; coluna++) {
      // A coluna aceita peça enquanto a casa de cima dela está vazia.
      if (posicao.mascara & bitDoTopo(dimensoes, coluna) == 0) {
        lances.add(LanceQuatro(tipoSoltarQuatro, coluna));
      }
    }
    return lances;
  }

  @override
  PosicaoQuatro aplicar(PosicaoQuatro posicao, LanceQuatro lance) {
    if (lance.tipo != tipoSoltarQuatro) {
      throw LanceIlegalQuatro('a regra de gravidade não tem o tipo '
          '"${lance.tipo}"');
    }
    if (lance.coluna > dimensoes.largura) {
      throw LanceIlegalQuatro('coluna ${lance.coluna} fora do tabuleiro de '
          '${dimensoes.largura} colunas');
    }
    if (posicao.mascara & bitDoTopo(dimensoes, lance.coluna) != 0) {
      throw LanceIlegalQuatro('coluna ${lance.coluna} cheia');
    }
    // A peça cai: somar o bit do fundo à máscara faz o "vai um" subir pela
    // coluna até a primeira casa vazia (os bits ocupados, todos 1, viram 0 e
    // a casa vazia vira 1); o "ou" com a máscara antiga devolve as ocupadas.
    // Exemplo numa coluna com 2 peças: 011 + 001 = 100, e 011 | 100 = 111.
    final novaMascara =
        posicao.mascara | (posicao.mascara + bitDoFundo(dimensoes, lance.coluna));
    // A vez passa: as peças "da vez" na posição nova são as do OUTRO jogador,
    // que são a máscara antiga sem as peças de quem acabou de jogar.
    final pecasDoOutro = posicao.pecasDaVez ^ posicao.mascara;
    // `semConferir`: o lance acabou de ser conferido acima, e a soma só
    // acende a casa livre da própria coluna.
    return PosicaoQuatro.semConferir(
      dimensoes: dimensoes,
      pecasDaVez: pecasDoOutro,
      mascara: novaMascara,
      lancesJogados: posicao.lancesJogados + 1,
    );
  }

  @override
  List<LanceQuatro> lancesQueVencem(PosicaoQuatro posicao) {
    // As casas onde uma peça cairia AGORA: somar o fundo de cada coluna à
    // máscara acende, em cada coluna, a primeira casa livre (o mesmo "vai um"
    // do `aplicar`); o `&` com o tabuleiro tira o que transbordou para a
    // sentinela de uma coluna cheia.
    final jogaveis = (posicao.mascara + _fundos) & _tabuleiroCheio;
    final vencem =
        casasQueAlinhariamQuatro(dimensoes, posicao.pecasDaVez) & jogaveis;
    if (vencem == 0) return const [];
    return [
      for (var coluna = 1; coluna <= dimensoes.largura; coluna++)
        if (vencem & mascaraDaColuna(dimensoes, coluna) != 0)
          LanceQuatro(tipoSoltarQuatro, coluna)
    ];
  }

  @override
  DesfechoQuatro? desfecho(PosicaoQuatro posicao) {
    // Quem acabou de jogar é o contrário de quem tem a vez. Na regra de
    // gravidade só ele pode ter acabado de formar linha; o outro jogador é
    // conferido também, para uma posição montada à mão não passar em branco.
    final quemJogou = -posicao.jogadorDaVez;
    for (final jogador in [quemJogou, -quemJogou]) {
      final pecas = jogador == 1 ? posicao.pecasDoJ1 : posicao.pecasDoJ2;
      final linhas = linhasAlinhadasQuatro(dimensoes, pecas);
      // Vitória ANTES de empate: a última casa do tabuleiro, quando fecha uma
      // linha, é vitória (por isso esta conta vem antes da do tabuleiro cheio).
      if (linhas.isNotEmpty) return DesfechoQuatro.vitoria(jogador, linhas);
    }
    if (posicao.mascara == _tabuleiroCheio) {
      return DesfechoQuatro.empate();
    }
    return null;
  }
}

/// As linhas de pelo menos `alinhar` peças em [pecas], nas quatro direções.
///
/// Pública porque toda modalidade alinha do mesmo jeito, qualquer que seja o
/// jeito de pôr ou tirar peças (a modalidade-sonda dos testes a usa).
///
/// Como funciona, para uma direção com deslocamento `d` (quantos bits separam
/// uma casa da vizinha naquela direção):
///   `inicios = pecas & (pecas >> d) & (pecas >> 2d) & ... & (pecas >> (n-1)d)`
/// Um bit `p` sobra em `inicios` só se `p`, `p + d`, ..., `p + (n-1)d` são
/// todas peças: `p` é o INÍCIO de uma linha de `n`. A sentinela (sempre 0)
/// corta a linha que tentaria passar de uma coluna para a outra.
///
/// Cinco em linha deixam DOIS inícios seguidos (`p` e `p + d`); eles são
/// juntados numa linha só, do primeiro início ao fim do último.
List<LinhaQuatro> linhasAlinhadasQuatro(DimensoesQuatro dimensoes, int pecas) {
  final altura = dimensoes.altura;
  final n = dimensoes.alinhar;
  // Os quatro deslocamentos: vertical (sobe 1 bit), horizontal (pula uma
  // coluna inteira, `altura + 1` bits), diagonal que sobe (`altura + 2`) e
  // diagonal que desce (`altura`) para a direita.
  final deslocamentos = [1, altura + 1, altura + 2, altura];
  final linhas = <LinhaQuatro>[];
  for (final d in deslocamentos) {
    var inicios = pecas;
    for (var k = 1; k < n; k++) {
      inicios &= pecas >> (k * d);
    }
    // Percorre os inícios do menor bit para o maior.
    while (inicios != 0) {
      // `inicios & -inicios` isola o bit ligado mais baixo (truque do
      // complemento de dois); `bitLength - 1` dá o número dele.
      final menor = inicios & -inicios;
      final primeiro = menor.bitLength - 1;
      var ultimo = primeiro;
      // Junta os inícios seguidos na mesma direção (5 ou mais em linha).
      while (inicios & (1 << (ultimo + d)) != 0) {
        ultimo += d;
        inicios &= ~(1 << ultimo);
      }
      inicios &= ~menor;
      final casas = <CasaQuatro>[];
      for (var bit = primeiro; bit <= ultimo + (n - 1) * d; bit += d) {
        casas.add(casaDoBit(dimensoes, bit));
      }
      linhas.add(LinhaQuatro(casas));
    }
  }
  return linhas;
}

/// As casas (vazias ou não) onde UMA peça a mais de quem tem [pecas] formaria
/// uma linha de `alinhar`. Quem chama faz o `&` com as casas que interessam
/// (as jogáveis agora, ou as vazias).
///
/// Para cada direção `d` e cada lugar `j` que a casa nova ocuparia dentro da
/// linha (a 1ª, a 2ª... a última), a casa `x` vence se todas as outras casas
/// da linha (`x + i·d`, com `i` de `-j` a `alinhar - 1 - j`, menos o 0) são
/// peças. "A casa `x + i·d` é peça" vira um deslocamento: `pecas >> (i·d)`
/// traz o bit de `x + i·d` para o lugar de `x` (e `<<` para `i` negativo). A
/// sentinela, sempre vazia, corta a linha que passaria de uma coluna à outra.
int casasQueAlinhariamQuatro(DimensoesQuatro dimensoes, int pecas) {
  final altura = dimensoes.altura;
  final n = dimensoes.alinhar;
  var vencem = 0;
  for (final d in [1, altura + 1, altura + 2, altura]) {
    for (var j = 0; j < n; j++) {
      // `-1` tem todos os bits ligados: o ponto de partida do "e" acumulado.
      var casas = -1;
      for (var i = -j; i <= n - 1 - j; i++) {
        if (i == 0) continue;
        casas &= i > 0 ? pecas >> (i * d) : pecas << (-i * d);
      }
      vencem |= casas;
    }
  }
  return vencem;
}
