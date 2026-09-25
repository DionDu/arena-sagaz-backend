/// A bancada: confere o motor em Dart e mede quantas posições ele faz por segundo.
///
/// **Uma implementação, duas frentes.** Este arquivo tem um `main()` e roda no
/// terminal; e a função [rodarBancada] é chamada tal e qual pelo app de bancada
/// que roda no celular. O número medido no PC e o medido no aparelho saem
/// exatamente do mesmo código — se fossem dois programas, a comparação entre
/// eles não valeria nada.
///
/// A ordem importa: **medir velocidade de um motor errado é medir nada.** Por
/// isso a conferência vem antes, e se ela falhar a medição nem é reportada como
/// válida.
///
/// O que é conferido
/// -----------------
/// 1. **Avaliação** — a nota de 8 posições, contra o que o motor de referência
///    em Python devolve.
/// 2. **Alfa-beta pura** — a nota da busca sem tabela de transposição e sem
///    extensão de captura, nas profundidades 1 a 4. Essa configuração é
///    escolhida de propósito: nela o valor da alfa-beta é igual ao do minimax,
///    que é uma quantidade **bem definida** — não depende de ordenação, de hash
///    nem de política de substituição. É a única comparação entre linguagens
///    que significa alguma coisa.
/// 3. **`perft`** — a contagem de posições contra o gabarito publicado por
///    terceiros para damas anglo-americanas.
/// 4. **Empates por histórico (arts. 97b e 98)** — a nota da mesma posição com e
///    sem o histórico da partida. É a conferência que pega a divergência mais
///    perigosa que existe entre as duas linguagens: um motor que enxerga o
///    empate e outro que não enxerga jogam partidas **diferentes** sem que
///    nenhum dos dois dê erro.
///
/// Como rodar no PC
/// ----------------
/// ```
/// cd ia\jogos\jogo_damas\motor_dart
/// dart compile exe bancada_damas.dart -o bancada.exe
/// .\bancada.exe
/// ```
/// ⚠️ Sempre AOT (`dart compile exe`), nunca `dart run`: o JIT gasta segundos
/// aquecendo e mede outra coisa. O app em release roda AOT.
library;

import 'avaliacao_damas.dart';
import 'busca_damas.dart';
import 'empates_por_historico_damas.dart';
// A política de ritmo entra aqui por um motivo só: ela guarda a **espera-alvo**
// de cada personagem, e é contra esse alvo que o lance completo do Magno tem de
// ser julgado. Sem ela, a bancada imprimiria milissegundos sem dizer se são
// muitos ou poucos — e o número sozinho não decide nada.
import 'politica_dificuldade_damas.dart';
import 'regras_damas.dart';
import 'tabuleiro_damas.dart';

// ---------------------------------------------------------------------------
// Valores de referência
// ---------------------------------------------------------------------------
//
// Extraídos do motor em Python, não escritos à mão. Ao mudar avaliação ou busca:
// mude no Python, rode lá, e traga o resultado para cá.

class _CasoAvaliacao {
  final String fen;
  final int notaAbsoluta;
  const _CasoAvaliacao(this.fen, this.notaAbsoluta);
}

class _CasoBusca {
  final String fen;

  /// Nota da alfa-beta pura nas profundidades 1, 2, 3 e 4.
  final List<int> notas;
  const _CasoBusca(this.fen, this.notas);
}

const List<_CasoAvaliacao> _avaliacoesDeReferencia = [
  _CasoAvaliacao(
      'W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12', 0),
  _CasoAvaliacao('W:W18,22,23,26,27,30,31:B5,6,9,10,13,14', 110),
  _CasoAvaliacao('W:W23:B10,18,19', -260),
  _CasoAvaliacao('W:WK29:B17,25,26', -88),
  _CasoAvaliacao('B:W15,23,27:BK6,10,14', -176),
  _CasoAvaliacao('W:WK15,22:BK10,K19', -164),
  _CasoAvaliacao('W:W25,26,27:B5,6,7', 4),
  _CasoAvaliacao('W:W6:B32', -6),
];

const List<_CasoBusca> _buscasDeReferencia = [
  _CasoBusca('W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12',
      [18, 0, 14, -4]),
  _CasoBusca('W:W18,22,23,26,27,30,31:B5,6,9,10,13,14', [118, 100, 124, 106]),
  _CasoBusca('W:W23:B10,18,19', [12, 6, 170, 156]),
  _CasoBusca('W:WK29:B17,25,26', [176, 158, 174, 164]),
  _CasoBusca('B:W15,23,27:BK6,10,14', [448, 442, 999997, 999997]),
  _CasoBusca('W:WK15,22:BK10,K19', [132, 120, 130, 124]),
  _CasoBusca('W:W25,26,27:B5,6,7', [22, 4, 10, 4]),
  _CasoBusca('W:W6:B32', [999999, 999999, 999999, 999999]),
];

/// Gabarito publicado por terceiros (TalkChess, gerador BikMove) para as
/// anglo-americanas. Não é número nosso — é o que dá valor à conferência.
const Map<int, int> _perftAngloPublicado = {
  1: 7, 2: 49, 3: 302, 4: 1469, 5: 7361, 6: 36768, 7: 179740,
};

/// A posição em que os arts. 97b e 98 são conferidos: duas damas brancas contra
/// uma preta, todas longe umas das outras.
///
/// Escolhida porque nela o **material** e a **regra** dizem coisas opostas. As
/// brancas estão claramente melhor (a busca dá +328 de nota), e mesmo assim o
/// regulamento vai declarar empate — não há captura possível, nenhuma pedra para
/// mover, e portanto nenhum jeito de zerar o contador do art. 97b.
const String _fenDosEmpatesDeclarados = 'W:WK29,K30:BK3';

/// Os três valores que o motor de referência em Python devolve nessa posição, à
/// profundidade 4, com tabela e extensão **desligadas**.
///
/// Extraídos rodando o Python, não escritos à mão — mesma disciplina das
/// avaliações e buscas de referência acima.
///
/// Os 56 empates contados são 14 lances legais × 4 profundidades do
/// aprofundamento iterativo: **todo** filho da raiz bate na regra, e por isso a
/// nota desaba de +328 para 0.
const int _notaSemHistorico = 328;
const int _notaComEmpateDeclarado = 0;
const int _empatesEsperados = 56;

/// A posição da FMJD 8.3: três damas brancas contra uma preta.
///
/// Vantagem material esmagadora (+632 de nota) e, mesmo assim, empate se o lado
/// forte não capturar em 15 lances.
const String _fenDaCorrelacao = 'W:WK29,K30,K31:BK3';
const int _notaDaCorrelacaoSemHistorico = 632;
const int _empatesEsperadosNa83 = 84;

/// A posição da FMJD 8.5: final de 4 peças com dama dos dois lados.
///
/// ⚠️ Aqui a nota sem histórico já é praticamente zero (posição equilibrada), e
/// por isso a conferência desta regra se apoia na **contagem de empates**, não
/// no contraste de nota. Sem esta observação, alguém poderia "simplificar" o
/// caso comparando notas e não estaria medindo nada.
const String _fenDoEquilibrio = 'W:WK29,30:BK3,4';
const int _empatesEsperadosNa85 = 32;

/// Posições em que a velocidade é medida: o começo de partida (árvore mais
/// larga) e um meio-jogo com material desigual (mais parecido com o que o motor
/// enfrenta de verdade).
const List<String> _posicoesDeMedicao = [
  'W:W21,22,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,11,12',
  'W:W18,22,23,26,27,30,31:B5,6,9,10,13,14',
];

// ---------------------------------------------------------------------------
// A bancada
// ---------------------------------------------------------------------------

/// Roda conferência e medição, e devolve o relatório linha a linha.
///
/// Função de argumento único e retorno simples de propósito: é o formato que o
/// `compute()` do Flutter aceita, o que permite rodá-la numa *isolate* e manter
/// a tela do app respondendo enquanto o celular pensa.
///
/// [orcamentoEmSegundos] é o tempo que o motor tem por lance — 2 s é o que o
/// plano supõe para o nível Sagaz. Medir por TEMPO, e não por profundidade fixa,
/// é o que torna o número comparável entre aparelhos diferentes: o que se
/// compara passa a ser "quão fundo cada um chega no mesmo tempo", que é
/// exatamente a pergunta do produto.
List<String> rodarBancada([double orcamentoEmSegundos = 2.0]) {
  final linhas = <String>[];
  var tudoBem = true;

  // --- 1. avaliação -------------------------------------------------------
  linhas.add('CONFERENCIA 1/6 — avaliacao contra o motor de referencia');
  var errosDeAvaliacao = 0;
  for (final caso in _avaliacoesDeReferencia) {
    final obtido = avaliarAbsoluto(Tabuleiro.deFen(caso.fen));
    if (obtido != caso.notaAbsoluta) {
      errosDeAvaliacao++;
      linhas.add('  ERRO  ${caso.fen}');
      linhas.add('        obtido $obtido, esperado ${caso.notaAbsoluta}');
    }
  }
  tudoBem &= errosDeAvaliacao == 0;
  linhas.add('  ${errosDeAvaliacao == 0 ? "OK" : "FALHOU"} — '
      '${_avaliacoesDeReferencia.length - errosDeAvaliacao} de '
      '${_avaliacoesDeReferencia.length} posicoes conferem');

  // --- 2. alfa-beta pura --------------------------------------------------
  linhas.add('');
  linhas.add('CONFERENCIA 2/6 — alfa-beta pura (sem tabela, sem extensao)');
  var errosDeBusca = 0;
  var totalDeBuscas = 0;
  for (final caso in _buscasDeReferencia) {
    for (var profundidade = 1; profundidade <= caso.notas.length; profundidade++) {
      totalDeBuscas++;
      final buscador = Buscador(
          usarTabela: false, extensaoDeCaptura: false, semente: 1);
      final obtido =
          buscador.buscar(Tabuleiro.deFen(caso.fen), profundidade: profundidade).nota;
      if (obtido != caso.notas[profundidade - 1]) {
        errosDeBusca++;
        linhas.add('  ERRO  ${caso.fen}  prof $profundidade');
        linhas.add('        obtido $obtido, esperado ${caso.notas[profundidade - 1]}');
      }
    }
  }
  tudoBem &= errosDeBusca == 0;
  linhas.add('  ${errosDeBusca == 0 ? "OK" : "FALHOU"} — '
      '${totalDeBuscas - errosDeBusca} de $totalDeBuscas buscas conferem');

  // --- 3. perft contra gabarito publicado ---------------------------------
  linhas.add('');
  linhas.add('CONFERENCIA 3/6 — perft anglo contra gabarito PUBLICADO');
  var errosDePerft = 0;
  final inicialAnglo = Tabuleiro.inicial(vez: angloAmericanas.quemComeca);
  for (final entrada in _perftAngloPublicado.entries) {
    final obtido = contarPosicoes(inicialAnglo, entrada.key, angloAmericanas);
    if (obtido != entrada.value) {
      errosDePerft++;
      linhas.add('  ERRO  prof ${entrada.key}: obtido $obtido, '
          'esperado ${entrada.value}');
    }
  }
  tudoBem &= errosDePerft == 0;
  linhas.add('  ${errosDePerft == 0 ? "OK" : "FALHOU"} — '
      'profundidades 1 a ${_perftAngloPublicado.length} conferem');

  // --- 4. empates por histórico (arts. 97b e 98) --------------------------
  linhas.add('');
  linhas.add('CONFERENCIA 4/6 — empates por historico (arts. 97b e 98)');
  final errosDeEmpate = _conferirEmpatesPorHistorico(linhas);
  tudoBem &= errosDeEmpate == 0;
  linhas.add('  ${errosDeEmpate == 0 ? "OK" : "FALHOU"} — '
      '${6 - errosDeEmpate} de 6 casos conferem');

  // --- 5. a terceira família: portuguesas / espanholas --------------------
  linhas.add('');
  linhas.add('CONFERENCIA 5/6 — portuguesas/espanholas '
      '(Qualidade, Forcada e o gatilho dos 20 lances)');
  final errosPortugueses = _conferirPortuguesas(linhas);
  final casosPortugueses = _perftPortugues.length + 1 + _casosDeEmpatePortugues;
  tudoBem &= errosPortugueses == 0;
  linhas.add('  ${errosPortugueses == 0 ? "OK" : "FALHOU"} — '
      '${casosPortugueses - errosPortugueses} de '
      '$casosPortugueses casos conferem');

  // --- 6. a variante de casa: as brasileiras SEM a Lei da Maioria ---------
  linhas.add('');
  linhas.add('CONFERENCIA 6/6 — damas de casa (sem a Lei da Maioria)');
  final errosDeCasa = _conferirDamasDeCasa(linhas);
  tudoBem &= errosDeCasa == 0;
  linhas.add('  ${errosDeCasa == 0 ? "OK" : "FALHOU"} — '
      '${_perftDeCasa.length + 1 - errosDeCasa} de '
      '${_perftDeCasa.length + 1} casos conferem');

  // --- medição ------------------------------------------------------------
  linhas.add('');
  if (!tudoBem) {
    linhas.add('*** NAO MEDIDO: o motor divergiu da referencia. ***');
    linhas.add('Medir velocidade de motor errado nao significa nada.');
    return linhas;
  }

  linhas.add('MEDICAO — busca com orcamento de '
      '${orcamentoEmSegundos.toStringAsFixed(0)}s por lance');
  linhas.add('(tabela de transposicao e extensao de captura LIGADAS, que e a');
  linhas.add(' configuracao com que o motor de fato joga)');
  linhas.add('');

  var somaDeNos = 0;
  var somaDeSegundos = 0.0;
  var menorProfundidade = 99;

  for (var indice = 0; indice < _posicoesDeMedicao.length; indice++) {
    final tabuleiro = Tabuleiro.deFen(_posicoesDeMedicao[indice]);
    final buscador = Buscador(semente: 1);
    // Profundidade 64 é um teto que nunca se alcança: quem manda aqui é o
    // relógio, e é o relógio que o jogador percebe.
    final resultado = buscador.buscar(tabuleiro,
        profundidade: 64, tempoMaximo: orcamentoEmSegundos);
    final estatisticas = resultado.estatisticas;
    somaDeNos += estatisticas.nos;
    somaDeSegundos += estatisticas.tempoSegundos;
    if (estatisticas.profundidadeAtingida < menorProfundidade) {
      menorProfundidade = estatisticas.profundidadeAtingida;
    }

    linhas.add('  posicao ${indice + 1}: lance ${resultado.lance}  '
        'nota ${(resultado.nota / 100).toStringAsFixed(2)}');
    linhas.add('    profundidade ${estatisticas.profundidadeAtingida} ply  ·  '
        '${_comSeparador(estatisticas.nos)} posicoes  ·  '
        '${_comSeparador(estatisticas.nosPorSegundo.round())} nos/s');
  }

  final media = somaDeSegundos > 0 ? somaDeNos / somaDeSegundos : 0.0;
  linhas.add('');
  linhas.add('>>> ${_comSeparador(media.round())} NOS DE BUSCA POR SEGUNDO');
  linhas.add('>>> $menorProfundidade PLY em '
      '${orcamentoEmSegundos.toStringAsFixed(0)}s (a pior das posicoes)');
  linhas.add('');
  linhas.add(_veredito(media));

  linhas.addAll(_impressaoDigitalDoSagaz());
  return linhas;
}

/// O `perft` das portuguesas a partir da posição inicial, do motor de referência.
///
/// **Não há gabarito publicado** para esta variante — estes números são nossos,
/// tirados do Python. O que lhes dá sentido é o padrão: até a profundidade 5
/// batem **exatamente** com o anglo-americano (nessa faixa o que decide é a
/// pedra não capturar de recuo, e nisso os dois concordam), e da 6 em diante
/// ficam **abaixo**, porque a Lei da Maioria passa a eliminar capturas menores.
const Map<int, int> _perftPortugues = {
  1: 7, 2: 49, 3: 302, 4: 1469, 5: 7361, 6: 36473, 7: 177532,
};

/// A posição da Lei da Qualidade, e o único lance que ela deixa legal.
///
/// Dama branca em 20, com duas capturas de **uma peça cada**: a de 27 é dama, a
/// de 9 é pedra. A quantidade empata, então a qualidade decide (FPD 3.7.b). Nas
/// brasileiras as duas seriam legais.
const String _fenDaLeiDaQualidade = 'W:WK20:B6,7,9,K27';
const int _capturadaObrigatoriaNasPortuguesas = 27;

/// Confere a terceira família contra o motor de referência. Devolve os erros.
///
/// Esta conferência pega o defeito que seria mais fácil de introduzir no port: o
/// Dart filtra a lista de capturas **no lugar**, compactando-a, e o filtro de
/// qualidade foi encaixado depois do de quantidade nessa mesma lista. Trocar a
/// ordem dos dois, ou compactar errado, não dá erro — dá lance ilegal.
int _conferirPortuguesas(List<String> linhas) {
  var erros = 0;

  final inicial = Tabuleiro.inicial(vez: portuguesas.quemComeca);
  for (final entrada in _perftPortugues.entries) {
    final obtido = contarPosicoes(inicial, entrada.key, portuguesas);
    if (obtido != entrada.value) {
      erros++;
      linhas.add('  ERRO  perft portugues prof ${entrada.key}: '
          'obtido $obtido, esperado ${entrada.value}');
    }
  }

  final lances = gerarLances(Tabuleiro.deFen(_fenDaLeiDaQualidade), portuguesas);
  if (lances.length != 1 ||
      lances.first.capturadas.length != 1 ||
      lances.first.capturadas.first != _capturadaObrigatoriaNasPortuguesas) {
    erros++;
    linhas.add('  ERRO  Lei da Qualidade em $_fenDaLeiDaQualidade');
    linhas.add('        esperado um lance so, tomando a dama de '
        '$_capturadaObrigatoriaNasPortuguesas; obtido '
        '${lances.map((l) => l.toString()).join(", ")}');
  }

  erros += _conferirRegrasDeEmpatePortuguesas(linhas);
  return erros;
}

/// Três damas brancas contra uma preta, nenhuma no Rio (que é a grande diagonal,
/// `{4, 8, 11, 15, 18, 22, 25, 29}`). A Forçada existe, mas ainda não conta.
const String _fenDaForcadaForaDoRio = 'W:WK30,K31,K32:BK1';

/// A mesma correlação, com uma dama branca em 25 — dentro do Rio. Conta.
const String _fenDaForcadaNoRio = 'B:WK25,K31,K32:BK1';

/// Cinco peças de cada lado com dama dos dois: **não** dispara o gatilho da FPD
/// 3.8.b, que exige no máximo quatro. Nas brasileiras o contador andaria.
const String _fenDeMeioJogoComDamas = 'W:WK29,21,22,23,24:BK3,9,10,11,12';

/// Quantos casos a conferência das regras de empate portuguesas cobre.
const int _casosDeEmpatePortugues = 4;

/// Confere a Forçada (FPD 3.8.a) e o gatilho dos 20 lances (3.8.b) no port.
///
/// Estas duas regras são exatamente do tipo que o `perft` **não** pega: não mudam
/// a contagem de lances legais, só o momento em que a partida termina. Um port
/// que as esquecesse passaria em todas as outras cinco conferências desta
/// bancada, e o aparelho jogaria as portuguesas com as regras brasileiras.
///
/// Os quatro casos, e o que cada um pega:
///
/// 1. **a configuração da Forçada** — três damas contra uma, e de quem é a força;
/// 2. **o Rio** — a contagem não começa antes de o forte ocupá-lo;
/// 3. **o gatilho dos 20 lances** — cinco peças por lado ainda não é final aqui;
/// 4. **a exclusão da 3.8.b.(4)** — na Forçada, o relógio dos 20 lances não vale
///    nem estourado, e quem fecha a partida é o dos 12.
int _conferirRegrasDeEmpatePortuguesas(List<String> linhas) {
  var erros = 0;

  void conferir(String rotulo, bool condicao) {
    if (condicao) return;
    erros++;
    linhas.add('  ERRO  $rotulo');
  }

  final foraDoRio = Tabuleiro.deFen(_fenDaForcadaForaDoRio);
  final noRio = Tabuleiro.deFen(_fenDaForcadaNoRio);

  conferir(
      'configuracao da Forcada nao reconhecida (FPD 3.8.a)',
      ladoForteDaForcada(foraDoRio, portuguesas) == brancas &&
          ladoForteDaForcada(foraDoRio, brasileiras) == null);

  conferir(
      'a Forcada comecou a contar antes de o Rio ser ocupado (3.8.a.2)',
      forcadaEmCurso(foraDoRio, portuguesas) == null &&
          forcadaEmCurso(noRio, portuguesas) == brancas);

  final meioJogo = Tabuleiro.deFen(_fenDeMeioJogoComDamas);
  conferir(
      'gatilho dos 20 lances errado (3.8.b.1)',
      contadorDeProgressoEstaLigado(meioJogo, brasileiras) &&
          !contadorDeProgressoEstaLigado(meioJogo, portuguesas));

  // O relógio dos 20 lances muito além do limite, e mesmo assim quem decide na
  // Forçada é o dos 12: com 11 lances a partida segue; com 12, empata.
  final historico = HistoricoDaPartida.desde(noRio, portuguesas)
    ..meiosLancesSemProgresso = 60
    ..lancesDeForcada = portuguesas.lancesDaForcada! - 1;
  final antesDoLimite = historico.motivoDeEmpate(noRio);
  historico.lancesDeForcada = portuguesas.lancesDaForcada!;
  final noLimite = historico.motivoDeEmpate(noRio);
  conferir(
      'a exclusao da 3.8.b.(4) nao foi aplicada '
      '(antes do limite: $antesDoLimite; no limite: $noLimite)',
      antesDoLimite == null && (noLimite?.contains('3.8.a') ?? false));

  return erros;
}

/// A posição da Lei da Maioria: pedra branca em 23, com duas capturas possíveis.
///
/// Uma toma **duas** peças (`23x14x7`), a outra toma **uma** (`23x16`). Nas
/// brasileiras só a primeira é legal; na variante de casa, as duas.
const String _fenDaLeiDaMaioria = 'W:W23:B10,18,19';

/// O `perft` da variante de casa, do motor de referência em Python.
///
/// **A assinatura da única regra que muda.** Estes números são idênticos aos das
/// brasileiras até a profundidade 4 — até ali ainda não existe posição em que
/// duas capturas de tamanhos diferentes concorram — e ficam **maiores** da 5 em
/// diante, que é onde a Lei da Maioria começa a cortar.
///
/// Se um dia passarem a bater com o brasileiro em toda a faixa, o campo
/// `capturaMaximaObrigatoria` parou de ser lido no Dart — e a "Damas de Casa"
/// virou brasileira sem ninguém perceber. O jogador sentiria isso como um lance
/// travado sem explicação, na modalidade que ele escolheu justamente para não
/// ter essa regra.
const Map<int, int> _perftDeCasa = {
  1: 7, 2: 49, 3: 302, 4: 1469, 5: 7482, 6: 37986, 7: 190146,
};

/// Confere a variante de casa contra o motor de referência. Devolve os erros.
///
/// Além do `perft`, o caso concreto: na posição da Lei da Maioria as brasileiras
/// deixam **um** lance legal e a de casa deixa mais de um — e todos continuam
/// sendo capturas, porque comer segue obrigatório. É o par de asserções que
/// separa "tirei a Lei da Maioria" de "tirei a captura obrigatória", que seria
/// outro jogo.
int _conferirDamasDeCasa(List<String> linhas) {
  var erros = 0;

  final inicial = Tabuleiro.inicial(vez: damasDeCasa.quemComeca);
  for (final entrada in _perftDeCasa.entries) {
    final obtido = contarPosicoes(inicial, entrada.key, damasDeCasa);
    if (obtido != entrada.value) {
      erros++;
      linhas.add('  ERRO  perft de casa prof ${entrada.key}: '
          'obtido $obtido, esperado ${entrada.value}');
    }
  }

  final tabuleiro = Tabuleiro.deFen(_fenDaLeiDaMaioria);
  final nasBrasileiras = gerarLances(tabuleiro, brasileiras);
  final emCasa = gerarLances(tabuleiro, damasDeCasa);
  final todasCapturas = emCasa.every((l) => l.capturadas.isNotEmpty);
  if (nasBrasileiras.length != 1 || emCasa.length <= 1 || !todasCapturas) {
    erros++;
    linhas.add('  ERRO  Lei da Maioria em $_fenDaLeiDaMaioria');
    linhas.add('        esperado 1 lance nas brasileiras e mais de um (todos '
        'capturas) na de casa;');
    linhas.add('        obtido ${nasBrasileiras.length} e ${emCasa.length}');
  }

  return erros;
}

/// Confere os arts. 97b e 98 contra o motor de referência. Devolve os erros.
///
/// São três casos, e os três usam a **mesma posição** — o que muda é só o
/// histórico. Isso é de propósito: se a nota mudasse por causa da posição, o
/// teste não estaria medindo o que diz medir.
///
/// 1. **sem histórico** — o motor vê duas damas contra uma e diz "estou
///    ganhando" (+328). É o controle: sem ele, uma nota 0 nos outros dois casos
///    poderia ser simplesmente um motor quebrado que devolve zero para tudo.
/// 2. **art. 97b** — o contador a um meio-lance do limite. Todo lance daqui
///    completa os 20 de cada lado, e a nota tem de ir a **zero**.
/// 3. **art. 98** — todos os filhos já ocorridos duas vezes na partida. Qualquer
///    lance completa a terceira, e a nota tem de ir a **zero** de novo.
///
/// Tabela e extensão desligadas, como na conferência 2: é a configuração em que
/// a nota é uma quantidade bem definida, que não depende de ordenação nem de
/// política de substituição da tabela.
int _conferirEmpatesPorHistorico(List<String> linhas) {
  var erros = 0;

  void conferir(String rotulo, String fen, HistoricoDaPartida? historico,
      int notaEsperada, int empatesEsperados) {
    final buscador = Buscador(
        usarTabela: false,
        extensaoDeCaptura: false,
        semente: 1);
    final resultado = buscador.buscar(Tabuleiro.deFen(fen),
        profundidade: 4, historico: historico);
    final empates = resultado.estatisticas.empatesPorHistorico;

    if (resultado.nota != notaEsperada || empates != empatesEsperados) {
      erros++;
      linhas.add('  ERRO  $rotulo');
      linhas.add('        nota ${resultado.nota} (esperado $notaEsperada), '
          '$empates empates (esperado $empatesEsperados)');
    }
  }

  final tabuleiro = Tabuleiro.deFen(_fenDosEmpatesDeclarados);

  conferir('sem historico', _fenDosEmpatesDeclarados, null,
      _notaSemHistorico, 0);

  final art97b = HistoricoDaPartida.desde(tabuleiro);
  art97b.meiosLancesSemProgresso = brasileiras.meiosLancesSemProgressoParaEmpate - 1;
  conferir('art. 97b (contador a um meio-lance do limite)',
      _fenDosEmpatesDeclarados, art97b, _notaComEmpateDeclarado,
      _empatesEsperados);

  final art98 = HistoricoDaPartida.desde(tabuleiro);
  for (final lance in gerarLances(tabuleiro, brasileiras)) {
    art98.repeticoes[aplicarLance(tabuleiro, lance).hash] = 2;
  }
  conferir('art. 98 (todos os filhos ja vistos 2x)', _fenDosEmpatesDeclarados,
      art98, _notaComEmpateDeclarado, _empatesEsperados);

  // --- as duas regras da FMJD, com posições próprias ----------------------
  //
  // Elas precisam de outras posições: a 8.3 exige a correlação de três damas
  // contra uma, e a 8.5 exige damas dos dois lados num final de 4 a 7 peças.

  // 8.3 — três damas contra uma, com o contador a um meio-lance dos 15 lances.
  final art83 = HistoricoDaPartida.desde(Tabuleiro.deFen(_fenDaCorrelacao));
  art83.meiosLancesSemProgresso = 2 * brasileiras.lancesTresDamasContraUma! - 1;
  conferir('sem historico (tres damas contra uma)', _fenDaCorrelacao, null,
      _notaDaCorrelacaoSemHistorico, 0);
  conferir('FMJD 8.3 (15 lances sem capturar a dama solitaria)',
      _fenDaCorrelacao, art83, 0, _empatesEsperadosNa83);

  // 8.5 — final de 4 peças com dama dos dois lados, contador a um meio-lance
  // dos 30 lances. ⚠️ Aqui a NOTA sem histórico já é quase zero (é uma posição
  // equilibrada), então quem prova a regra é a CONTAGEM de empates, não a nota.
  final art85 = HistoricoDaPartida.desde(Tabuleiro.deFen(_fenDoEquilibrio));
  art85.meiosLancesSemMudarOEquilibrio = 2 * 30 - 1;
  conferir('FMJD 8.5 (30 lances sem captura nem promocao)', _fenDoEquilibrio,
      art85, 0, _empatesEsperadosNa85);

  return erros;
}

/// A "impressão digital" do nível Sagaz: o que ele decide com orçamento de NÓS.
///
/// Este bloco existe para uma conferência que nenhum teste automatizado
/// consegue fazer sozinho — **rodar a bancada em dois aparelhos diferentes e
/// comparar as duas saídas**. Com orçamento de nós, todas as linhas abaixo têm
/// de sair idênticas: mesmo lance, mesma nota, mesma profundidade, mesmo número
/// de posições visitadas. É a etapa 8 provando, no aparelho de verdade, o que o
/// teste em Python prova na bancada do PC.
///
/// O que **pode** variar legitimamente entre aparelhos é só o tempo — e é por
/// isso que ele é impresso ao lado, separado do resto.
List<String> _impressaoDigitalDoSagaz() {
  final linhas = <String>[
    '',
    'IMPRESSAO DIGITAL — orcamento de NOS do nivel ${sagaz.nome} '
        '(${_comSeparador(sagaz.tetoDeNos ?? 0)} nos)',
    '(rode isto em dois aparelhos: as linhas TEM de sair identicas, menos o tempo)',
    '',
  ];

  // ⚠️ Duas contas de tempo, e a diferença entre elas é o ponto cego que esta
  // bancada teve até 21/08/2026.
  //
  // `estatisticas.tempoSegundos` é o relógio de dentro de `buscar()`: começa
  // quando a busca começa. Era o único número impresso aqui — e os 160.593 nós/s
  // do Galaxy A35, que sustentam o teto de 96 mil nós e a conta de ritmo
  // inteira, saíram dele. **Construir o `Buscador` ficava de fora da medição.**
  //
  // Só que o app constrói um `Buscador` **por lance** (`pedirLanceDamas` usa
  // `compute`, e cada isolate começa do zero), e até a T191 essa construção
  // alocava um milhão de objetos — 38 ms no PC, e provavelmente bem mais num
  // celular. Ou seja: o instrumento **não olhava** onde estava boa parte da
  // espera, e por isso o Magno podia estar estourando o alvo de ritmo sem que
  // nenhuma medição acusasse.
  //
  // O relógio de parede abaixo mede o que o **jogador** espera: construir mais
  // buscar. É este que responde se há folga para subir o orçamento de nós.
  var somaDoLanceMs = 0.0;
  var piorLanceMs = 0.0;
  var somaDaConstrucaoMs = 0.0;
  var pararamPorTempo = 0;

  for (var indice = 0; indice < _posicoesDeMedicao.length; indice++) {
    final tabuleiro = Tabuleiro.deFen(_posicoesDeMedicao[indice]);

    final relogioDaConstrucao = Stopwatch()..start();
    final buscador = Buscador(semente: 1);
    relogioDaConstrucao.stop();

    final relogioDoLance = Stopwatch()..start();
    final resultado = buscador.jogar(tabuleiro, sagaz);
    relogioDoLance.stop();

    final estatisticas = resultado.estatisticas;
    final construcaoMs = relogioDaConstrucao.elapsedMicroseconds / 1000.0;
    final lanceMs = construcaoMs + relogioDoLance.elapsedMicroseconds / 1000.0;

    somaDaConstrucaoMs += construcaoMs;
    somaDoLanceMs += lanceMs;
    if (lanceMs > piorLanceMs) piorLanceMs = lanceMs;
    if (estatisticas.motivoDaParada == 'tempo') pararamPorTempo++;

    linhas.add('  posicao ${indice + 1}: lance ${resultado.lance}  '
        'nota ${resultado.nota}  '
        'prof ${estatisticas.profundidadeAtingida}  '
        'nos ${_comSeparador(estatisticas.nos)}  '
        'parou por ${estatisticas.motivoDaParada}');
    linhas.add('    (lance completo: ${lanceMs.toStringAsFixed(0)} ms, sendo '
        '${construcaoMs.toStringAsFixed(1)} ms de construcao — so o tempo '
        'varia de aparelho para aparelho)');
  }

  linhas.addAll(_folgaDeRitmoDoMagno(
    lanceMedioMs: somaDoLanceMs / _posicoesDeMedicao.length,
    piorLanceMs: piorLanceMs,
    construcaoMediaMs: somaDaConstrucaoMs / _posicoesDeMedicao.length,
    pararamPorTempo: pararamPorTempo,
  ));

  return linhas;
}

/// **A conta que decide se dá para subir o orçamento de nós (T182).**
///
/// O raciocínio, em uma frase: o jogador espera um intervalo **alvo** entre o
/// lance dele e o da CPU; se a busca couber com folga dentro desse alvo, a folga
/// pode ser gasta em **mais nós** — e mais nós é mais força, sem que ninguém
/// espere um milissegundo a mais.
///
/// Isso funciona porque a espera é `max(0, alvo - busca)`: a pausa de encenação
/// encolhe exatamente na medida em que a busca cresce, e o intervalo total
/// continua sendo o alvo. Ver [pausaDeEncenacaoMs].
///
/// ⚠️ **Por que isto não contradiz a recusa do dono em 20/08.** Ele recusou
/// subir o teto **ao custo por nó de então**, porque castigaria o aparelho
/// fraco. A pergunta aqui é outra, e mais honesta: *neste aparelho, quanto
/// sobra?* Se sobrar zero, o veredito é não subir — e isso também é resposta.
///
/// ⚠️ **A regra de três é aproximada, e de propósito conservadora.** Nós e tempo
/// não são exatamente proporcionais: o aprofundamento iterativo cresce em
/// degraus, e a última profundidade tentada pode ser abandonada no meio. Por
/// isso a sugestão sai do **pior** caso, nunca da média, e arredonda para baixo.
List<String> _folgaDeRitmoDoMagno({
  required double lanceMedioMs,
  required double piorLanceMs,
  required double construcaoMediaMs,
  required int pararamPorTempo,
}) {
  final alvoMs = esperaAlvoMs(sagaz.identificador).toDouble();
  final tetoAtual = sagaz.tetoDeNos ?? 0;
  final linhas = <String>[
    '',
    'FOLGA DE RITMO DO MAGNO — sobra orcamento neste aparelho?',
    '',
    '  espera-alvo do ${sagaz.nome}: ${alvoMs.toStringAsFixed(0)} ms '
        '(o intervalo INTEIRO entre o lance do humano e o da CPU)',
    '  lance completo, medio: ${lanceMedioMs.toStringAsFixed(0)} ms '
        '(${construcaoMediaMs.toStringAsFixed(1)} ms de construcao)',
    // O "pior" sai de apenas duas posicoes, e isso e dito em voz alta de
    // proposito: com duas, o pior caso medido e uma estimativa fraca do pior
    // caso real. Ampliar a lista tornaria o numero mais confiavel, mas
    // quebraria a comparacao com os 160.593 nos/s do A35, que sustentam a
    // calibracao inteira - a troca nao vale hoje.
    '  lance completo, PIOR:  ${piorLanceMs.toStringAsFixed(0)} ms '
        '(pior de apenas ${_posicoesDeMedicao.length} posicoes)',
  ];

  if (pararamPorTempo > 0) {
    linhas
      ..add('')
      ..add('  *** $pararamPorTempo posicao(oes) pararam por TEMPO, e nao por nos. ***')
      ..add('  Este aparelho nao completa os ${_comSeparador(tetoAtual)} nos dentro')
      ..add('  da rede de seguranca: quem joga aqui enfrenta um Magno MAIS FRACO')
      ..add('  do que o nivel promete, e nada na tela diz isso.')
      ..add('  NAO subir o orcamento enquanto esta linha aparecer.');
    return linhas;
  }

  final folgaMs = alvoMs - piorLanceMs;
  if (folgaMs <= 0) {
    linhas
      ..add('')
      ..add('  >>> SEM FOLGA: o pior lance ja passa do alvo em '
          '${(-folgaMs).toStringAsFixed(0)} ms.')
      ..add('  A pausa de encenacao ja esta zerada, e o Magno e o personagem')
      ..add('  mais lento da tela neste aparelho — o oposto do que foi pedido.')
      ..add('  NAO subir o orcamento. O caminho aqui e chegar mais fundo pelos')
      ..add('  mesmos nos (T192), e nao pedir mais nos.');
    return linhas;
  }

  // Regra de três sobre o PIOR caso: se `piorLanceMs` compra `tetoAtual` nós,
  // quantos nós cabem em `alvoMs`? Arredondado para baixo, ao milhar.
  final tetoQueCabe = ((tetoAtual * alvoMs / piorLanceMs) / 1000).floor() * 1000;
  final fator = tetoAtual == 0 ? 0.0 : tetoQueCabe / tetoAtual;

  linhas
    ..add('  folga sobre o pior caso: ${folgaMs.toStringAsFixed(0)} ms')
    ..add('')
    ..add('  >>> CABERIA ATE ${_comSeparador(tetoQueCabe)} NOS no alvo de '
        '${alvoMs.toStringAsFixed(0)} ms')
    ..add('  >>> ou seja, ${fator.toStringAsFixed(2)}x o teto atual de '
        '${_comSeparador(tetoAtual)} nos')
    ..add('')
    ..add('  Como ler: subir o teto ate esse valor NAO faz ninguem esperar mais,')
    ..add('  porque a pausa de encenacao encolhe na mesma medida (a espera total')
    ..add('  e o alvo, nao a busca). O que muda e a forca do Magno.')
    ..add('  Rode isto no PIOR aparelho que houver, e nao no melhor: o')
    ..add('  compromisso e com quem tem o celular ruim.')
    ..add('  E confirme na arena que a forca subiu de fato — mais nos deveria')
    ..add('  sempre ajudar, mas "deveria" nao e medida.');

  return linhas;
}

/// Traduz o número medido nos limiares do plano (etapa 3).
///
/// ⚠️ **O texto do limiar superior foi corrigido em 2026-07-24.** Ele dizia
/// "acima de 150 mil: profundidade 14+ em segundos", e isso **é falso**. Os 150
/// mil vieram de uma conta que supunha ramificação efetiva 2,5; a medida é ~3,5,
/// e a essa ramificação 150 mil nós/s compram 10 a 13 ply, não 14+. Ganhar um
/// ply exige ~3,5× mais nós — 14 ply exigiria uns 150× o que se mede hoje, o que
/// nenhuma otimização entrega.
///
/// A profundidade real vai impressa acima deste veredito. **Olhe para ela**, não
/// para o rótulo: quem decide se o motor é forte o bastante é a arena da etapa
/// 9, jogando — não uma contagem de nós.
String _veredito(double nosPorSegundo) {
  if (nosPorSegundo >= 150000) {
    return 'SEGUE — acima de 150 mil nos/s. Busca viavel no aparelho.\n'
        'Atencao: a profundidade impressa acima e o que vale. O limiar NAO\n'
        'garante 14 ply — ver a nota em _veredito() e a etapa 3 do plano.';
  }
  if (nosPorSegundo >= 50000) {
    return 'DESVIA — entre 50 e 150 mil: gastar as otimizacoes que faltam em '
        'Dart antes de considerar Rust ou C via dart:ffi.';
  }
  return 'PARA — abaixo de 50 mil: nao ha Sagaz por busca neste aparelho. '
      'Reabre a discussao de rede neural, com dado na mao.';
}

String _comSeparador(int numero) {
  final texto = numero.toString();
  final saida = StringBuffer();
  for (var i = 0; i < texto.length; i++) {
    if (i > 0 && (texto.length - i) % 3 == 0) saida.write('.');
    saida.write(texto[i]);
  }
  return saida.toString();
}
