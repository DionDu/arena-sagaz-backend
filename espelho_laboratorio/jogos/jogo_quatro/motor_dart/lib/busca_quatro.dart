// Motor do Quatro em Linha - escrito do zero, sem código AGPL.
// Negamax, poda alfa-beta, tabela de transposição e aprofundamento iterativo
// são técnicas públicas da literatura de jogos (Allis, 1988, para este jogo).
// Nenhum arquivo de solucionador alheio foi aberto durante a escrita.
//
// ── O que este arquivo é ─────────────────────────────────────────────────────
//
// A busca que escolhe o lance da CPU. Ela recebe as REGRAS da modalidade pela
// interface e não sabe qual modalidade joga: anda pelas posições com
// `lancesLegais`, `aplicar` e `desfecho`, e mais nada.
//
// O pedido e a resposta (`PedidoDeLanceQuatro`, `RespostaDeLanceQuatro`) são
// exatamente os de `contracts/motor-quatro.md` §3: só tipos simples, porque
// atravessam o isolate do app e o processo do servidor.
//
// No fim da visão, a posição vale o que a heurística diz
// (`heuristica_quatro.dart`, T030).
//
// ⚠️ O que é da POLÍTICA de dificuldade, e não daqui: o erro ε, a chance de
// perceber cada situação (vencer, bloquear, a casa sob ameaça), o sorteio dos empates e a abertura sorteada do Magno
// (`politica_dificuldade_quatro.dart`, T033/T034). Esta busca devolve o melhor
// lance que enxerga dentro do teto de nós; com `buscarComEmpates`, também os
// que empataram com ele, para a política sortear.

import 'dart:typed_data';

import 'heuristica_quatro.dart';
import 'posicao_quatro.dart';
import 'regras_da_modalidade_quatro.dart';

// ── O valor de uma posição ───────────────────────────────────────────────────
//
// A busca usa o NEGAMAX: o valor é sempre do ponto de vista de quem joga
// naquela posição, e o valor de um lance é o NEGATIVO do valor da posição que
// ele deixa para o outro (o que é bom para um é ruim para o outro, na mesma
// medida). Assim uma função só serve aos dois jogadores.
//
// A vitória vale MAIS quanto mais cedo ela vem: `vitoria - lancesJogados`, com
// os lances contados desde o tabuleiro vazio. Uma vitória no lance 20 vale
// 980; no lance 30, 970. E a derrota, que é o negativo, vale MENOS quanto mais
// tarde ela vem (-970 é melhor que -980). É isso que faz a CPU "adiar a
// derrota" quando não há salvação (RF-QTR-083), sem nenhum código à parte.
// Contar desde o tabuleiro vazio, e não desde a raiz da busca, deixa o valor
// de uma posição igual por qualquer caminho: é o que a tabela de transposição
// precisa para guardá-lo.

/// O valor-base da vitória. Maior que qualquer número de lances (o bitboard
/// tem no máximo 63 casas), para a vitória mais tardia ainda valer mais que
/// qualquer posição sem desfecho.
const int valorVitoriaQuatro = 1000;

/// Acima disto (em valor absoluto), o valor é de partida DECIDIDA: alguém
/// vence à força dentro do que a busca viu.
const int limiarDecididoQuatro = valorVitoriaQuatro - 64;

/// O valor de [posicao] para quem tem a vez, quando ela tem [desfecho].
///
/// Num desfecho com vencedor, quem venceu foi quem ACABOU de jogar, então
/// quem tem a vez perdeu: o valor é negativo.
int valorDoDesfecho(PosicaoQuatro posicao, DesfechoQuatro desfecho) {
  if (desfecho.empatou) return 0;
  final perda = valorVitoriaQuatro - posicao.lancesJogados;
  return desfecho.vencedor == posicao.jogadorDaVez ? perda : -perda;
}

// ── O pedido e a resposta ────────────────────────────────────────────────────

/// O que se pede à busca (`contracts/motor-quatro.md` §3).
final class PedidoDeLanceQuatro {
  /// A partida inteira até aqui, na notação (`s4s4s3`), inclusive os lances da
  /// posição publicada de um desafio.
  final String lances;

  /// O id da modalidade, lido do contrato por quem chama.
  final String modalidade;

  /// O teto de nós: a busca não visita mais posições que isto.
  final int tetoDeNos;

  /// A chance de erro proposital do nível (usada pela política, fase 1b).
  final double epsilon;

  /// A chance de o personagem PERCEBER cada situação (usada pela política;
  /// §8zzzf): `vencer`, `bloquear`, `nao_jogar_sob_ameaca`, de 0 a 1. Uma
  /// situação sem chave não é sorteada nem forçada: a busca decide sozinha.
  final Map<String, double> percebe;

  /// As chances de cada coluna no 1º lance do Magno (política, fase 1b);
  /// `null` fora desse lance.
  final Map<int, double>? aberturaDoMagno;

  /// A semente DO LANCE, derivada fora do motor (`semente_da_partida.dart` no
  /// app, `job/semente.py` no servidor).
  final int semente;

  /// O limite de tempo em ms: 10.000 no app (a rede de segurança); `null` no
  /// servidor, na escada e na bancada, que jogam só pelo teto de nós.
  final int? limiteMs;

  /// Cria o pedido.
  const PedidoDeLanceQuatro({
    required this.lances,
    required this.modalidade,
    required this.tetoDeNos,
    this.epsilon = 0,
    this.percebe = const {},
    this.aberturaDoMagno,
    this.semente = 0,
    this.limiteMs,
  });
}

/// O que a busca devolve (`contracts/motor-quatro.md` §3). Os textos de
/// [acao] e [motivoParada] são EXATAMENTE os códigos das dimensões do banco
/// (`data-model.md` §2.1).
final class RespostaDeLanceQuatro {
  /// O lance escolhido, na notação (`s5`).
  final String lance;

  /// Por que este lance: `busca_melhor`, `epsilon_aleatorio`,
  /// `abertura_sorteada`, `vitoria_imediata`, `bloqueio_imediato`,
  /// `empate_sorteado`, ou um descuido do personagem (§8zzzf):
  /// `vitoria_perdida`, `bloqueio_perdido` ou `jogou_sob_ameaca`.
  final String acao;

  /// Quantas posições a busca visitou.
  final int nosVisitados;

  /// A última profundidade (em lances à frente) que a busca terminou.
  final int profundidadeAtingida;

  /// Por que a busca parou: `profundidade`, `nos`, `tempo`, `decidido` ou
  /// `lance_unico`.
  final String motivoParada;

  /// Quanto tempo a busca levou, em ms.
  final int tempoBuscaMs;

  /// O valor que a busca deu à posição, do ponto de vista do JOGADOR 1 (para o
  /// log ler sempre no mesmo referencial).
  final int avaliacaoJ1;

  /// Cria a resposta.
  const RespostaDeLanceQuatro({
    required this.lance,
    required this.acao,
    required this.nosVisitados,
    required this.profundidadeAtingida,
    required this.motivoParada,
    required this.tempoBuscaMs,
    required this.avaliacaoJ1,
  });

  @override
  String toString() => 'RespostaDeLanceQuatro($lance, $acao, nós=$nosVisitados, '
      'prof=$profundidadeAtingida, $motivoParada, aval=$avaliacaoJ1)';
}

// ── A busca ──────────────────────────────────────────────────────────────────

/// O lance que a busca escolhe para o [pedido], jogando pelas [regras].
///
/// [regras] é a modalidade que quem chama carregou do contrato
/// (`carregarModalidade`); o motor não abre arquivo.
///
/// Anda por aprofundamento: busca 1 lance à frente, depois 2, depois 3... até
/// enxergar o fim da partida (`profundidade`), achar uma vitória ou derrota
/// forçada (`decidido`), ou estourar o teto de nós (`nos`). Quando o teto
/// estoura no meio de uma profundidade, a resposta é a da última profundidade
/// COMPLETA: uma busca pela metade viu só parte dos lances, e escolher entre
/// os que ela viu seria escolher às cegas.
///
/// Dois atalhos antes da busca: com uma coluna só disponível, `lance_unico` e
/// zero nós; com uma vitória na mão, ela é jogada na hora (`decidido`).
///
/// ⚠️ **O mesmo pedido dá o mesmo lance e o mesmo número de nós**, em
/// qualquer execução e em qualquer aparelho: a tabela de transposição nasce
/// vazia a cada pedido, e nada depende do relógio, a não ser o [limiteMs]
/// (que só o app usa, como rede de segurança). É disso que dependem a bancada
/// (que confere o A06 contra o PC) e o servidor (que precisa jogar o lance
/// que o aparelho jogaria).
///
/// [bitsDaTabela] é o tamanho da tabela de transposição (2 elevado a ele,
/// em entradas); `0` busca sem tabela. Existe para os testes e a bancada; o
/// padrão é o que o jogo usa.
RespostaDeLanceQuatro escolherLance(
        PedidoDeLanceQuatro pedido, RegrasDaModalidadeQuatro regras,
        {int bitsDaTabela = bitsDaTabelaQuatro}) =>
    _buscar(pedido, regras, bitsDaTabela, comEmpates: false).resposta;

/// A mesma busca de [escolherLance], que devolve também os lances que
/// EMPATARAM com o melhor: os de valor exatamente igual ao dele, na última
/// profundidade completa (sem o melhor; vazia quando não há empate).
///
/// É a porta da política de dificuldade (`politica_dificuldade_quatro.dart`),
/// que sorteia entre os empatados com a semente do lance (RF-QTR-082).
///
/// ⚠️ Os nós contados aqui podem ser um pouco mais que os de [escolherLance]
/// no mesmo pedido: para saber se um lance EMPATA, a raiz o busca com a
/// janela um ponto mais larga (ver `_Busca.raiz`), o que poda um pouco menos.
/// O teto de nós continua valendo igual, e é ele que limita o tempo. A
/// bancada mede [escolherLance], e o número dela não muda.
({RespostaDeLanceQuatro resposta, List<LanceQuatro> empatados})
    buscarComEmpates(
            PedidoDeLanceQuatro pedido, RegrasDaModalidadeQuatro regras,
            {int bitsDaTabela = bitsDaTabelaQuatro}) =>
        _buscar(pedido, regras, bitsDaTabela, comEmpates: true);

/// O corpo das duas funções acima. [comEmpates] liga a procura de empates
/// na raiz; desligada, a busca é exatamente a de antes.
({RespostaDeLanceQuatro resposta, List<LanceQuatro> empatados}) _buscar(
    PedidoDeLanceQuatro pedido,
    RegrasDaModalidadeQuatro regras,
    int bitsDaTabela,
    {required bool comEmpates}) {
  final relogio = Stopwatch()..start();
  final raiz = PosicaoQuatro.deLances(regras, pedido.lances);
  if (regras.desfecho(raiz) != null) {
    throw ArgumentError('a partida "${pedido.lances}" já terminou');
  }
  final ordem = ordemDoCentroQuatro(raiz.dimensoes.largura);
  final lances = _ordenar(regras.lancesLegais(raiz), ordem);
  if (lances.isEmpty) {
    throw ArgumentError('não há lance legal em "${pedido.lances}"');
  }

  /// Monta a resposta (o mesmo formato nos quatro caminhos de saída).
  RespostaDeLanceQuatro responder(LanceQuatro lance, int valor, int nos,
          int profundidade, String motivo) =>
      RespostaDeLanceQuatro(
        lance: escreverLanceQuatro(lance, regras.tiposDeLance),
        acao: 'busca_melhor',
        nosVisitados: nos,
        profundidadeAtingida: profundidade,
        motivoParada: motivo,
        tempoBuscaMs: relogio.elapsedMilliseconds,
        // O valor é de quem joga; vezes `jogadorDaVez` (+1 ou -1) ele passa
        // para o referencial do Jogador 1.
        avaliacaoJ1: valor * raiz.jogadorDaVez,
      );

  // Os atalhos não têm empate a sortear: um lance só, ou a vitória na mão
  // (qualquer coluna que vença serve, e fica a primeira na ordem).
  const semEmpate = <LanceQuatro>[];
  if (lances.length == 1) {
    return (
      resposta: responder(lances.single, 0, 0, 0, 'lance_unico'),
      empatados: semEmpate
    );
  }
  final vencem = _ordenar(regras.lancesQueVencem(raiz), ordem);
  if (vencem.isNotEmpty) {
    return (
      resposta: responder(vencem.first,
          valorVitoriaQuatro - (raiz.lancesJogados + 1), 0, 1, 'decidido'),
      empatados: semEmpate
    );
  }

  final busca = _Busca(
    regras,
    ordem,
    _ContadorDeNos(pedido.tetoDeNos,
        relogio: relogio, limiteMs: pedido.limiteMs),
    HeuristicaQuatro(raiz.dimensoes),
    bitsDaTabela > 0 ? _TabelaDeTransposicao(bitsDaTabela) : null,
  );
  var melhor = lances.first;
  var melhorValor = 0;
  var empatados = semEmpate;
  var profundidadeCompleta = 0;
  var motivo = 'profundidade';
  // A ordem da raiz muda a cada profundidade: o melhor lance da anterior
  // vai para a frente (a "variante principal"), porque costuma continuar
  // sendo o melhor, e o alfa-beta poda mais quando o melhor vem primeiro.
  var ordemDaRaiz = lances;

  // Até onde aprofundar não sai do número de casas livres: numa modalidade
  // que TIRA peças, a partida passa disso. A busca para quando uma
  // profundidade termina sem cortar caminho nenhum no horizonte (aí ela viu
  // o fim de todos os caminhos), quando decide, ou quando o teto acaba. O
  // limite de [profundidadeMaximaQuatro] só existe contra partida sem fim.
  for (var profundidade = 1;
      profundidade <= profundidadeMaximaQuatro;
      profundidade++) {
    busca.cortes = 0;
    try {
      final (lance, valor, iguais) = busca.raiz(raiz, ordemDaRaiz, profundidade,
          comEmpates: comEmpates);
      melhor = lance;
      melhorValor = valor;
      empatados = iguais;
      profundidadeCompleta = profundidade;
      ordemDaRaiz = [lance, ...ordemDaRaiz.where((l) => l != lance)];
    } on _BuscaInterrompida catch (parada) {
      motivo = parada.motivo;
      break;
    }
    if (melhorValor.abs() > limiarDecididoQuatro) {
      motivo = 'decidido';
      break;
    }
    // Nenhum caminho cortado no horizonte: a busca viu o fim de todos, e
    // olhar mais fundo não mudaria nada.
    if (busca.cortes == 0) break;
  }
  // Se nem a profundidade 1 coube no teto, fica o primeiro lance da ordem
  // (e sem empates: nenhuma profundidade terminou para compará-los).
  return (
    resposta: responder(melhor, melhorValor, busca.contador.nos,
        profundidadeCompleta, motivo),
    empatados: empatados
  );
}

/// As colunas da [largura] do centro para as bordas: `4, 3, 5, 2, 6, 1, 7`
/// na largura 7; `3, 4, 2, 5, 1, 6` na 6.
///
/// É a ordem em que a busca experimenta os lances: a coluna do meio entra em
/// mais linhas possíveis, então costuma ser a melhor, e o alfa-beta poda mais
/// quando o melhor lance vem primeiro. Sai da LARGURA, e não de uma lista
/// escrita à mão, para valer em qualquer tabuleiro.
List<int> ordemDoCentroQuatro(int largura) {
  final colunas = [for (var c = 1; c <= largura; c++) c];
  // `(2c - (largura + 1)).abs()` é o dobro da distância ao centro (o dobro,
  // para o centro de largura par, que cai entre duas colunas, ficar inteiro).
  // Empate de distância: a coluna da esquerda primeiro.
  colunas.sort((a, b) {
    final da = (2 * a - (largura + 1)).abs();
    final db = (2 * b - (largura + 1)).abs();
    return da != db ? da - db : a - b;
  });
  return colunas;
}

/// [lances] na [ordem] das colunas; dentro da mesma coluna, a ordem em que
/// vieram (a dos tipos da modalidade).
List<LanceQuatro> _ordenar(List<LanceQuatro> lances, List<int> ordem) {
  // A posição de cada coluna na ordem (índice 0 = experimentada primeiro).
  final lugar = List<int>.filled(ordem.length + 1, 0);
  for (var i = 0; i < ordem.length; i++) {
    lugar[ordem[i]] = i;
  }
  // O índice original desempata, para a ordem nunca depender de como o
  // `sort` do Dart (que não é estável) trata os iguais.
  final indices = [for (var i = 0; i < lances.length; i++) i];
  indices.sort((a, b) {
    final porColuna = lugar[lances[a].coluna] - lugar[lances[b].coluna];
    return porColuna != 0 ? porColuna : a - b;
  });
  return [for (final i in indices) lances[i]];
}

/// O estado de UMA busca: as regras, a ordem das colunas, o contador, a
/// heurística e a tabela de transposição (`null` = sem tabela).
class _Busca {
  final RegrasDaModalidadeQuatro regras;
  final List<int> ordem;
  final _ContadorDeNos contador;

  /// O valor das posições em que a visão acaba (T030).
  final HeuristicaQuatro heuristica;
  final _TabelaDeTransposicao? tabela;

  /// Quantas vezes a busca parou um caminho no horizonte (profundidade 0
  /// numa posição sem desfecho). Zero ao fim de uma profundidade = a busca
  /// viu o fim de todos os caminhos.
  int cortes = 0;

  _Busca(this.regras, this.ordem, this.contador, this.heuristica,
      [this.tabela]);

  /// Aplica [lance] e conta o nó (o teto de nós conta posições criadas).
  PosicaoQuatro _jogar(PosicaoQuatro posicao, LanceQuatro lance) {
    contador.contar();
    return regras.aplicar(posicao, lance);
  }

  /// A raiz: o melhor lance e o valor dele, olhando [profundidade] lances, e
  /// os lances que EMPATARAM com ele (vazia sem [comEmpates]).
  ///
  /// Pede que [raiz] não tenha desfecho nem vitória na mão (o chamador já
  /// tratou os dois). Empate de valor: fica o PRIMEIRO na ordem; o sorteio
  /// entre lances de mesmo valor é da política, que lê a lista de empatados.
  ///
  /// Como se acha um empate sem buscar tudo de novo: a poda alfa-beta só
  /// devolve o valor EXATO de um lance quando ele cai dentro da janela
  /// (`alfa`, `beta`); um lance que não passa de `alfa` volta só com um teto
  /// ("vale no máximo isto"). Com [comEmpates], a janela de cada lance depois
  /// do primeiro começa em `alfa - 1`: um lance de valor IGUAL ao melhor cai
  /// dentro dela e volta exato, e um lance pior volta com um teto de no
  /// máximo `alfa - 1`, que nunca se confunde com o empate.
  (LanceQuatro, int, List<LanceQuatro>) raiz(
      PosicaoQuatro raiz, List<LanceQuatro> lances, int profundidade,
      {bool comEmpates = false}) {
    LanceQuatro? melhor;
    var alfa = -_infinito;
    final empatados = <LanceQuatro>[];
    for (final lance in lances) {
      final piso = comEmpates && melhor != null ? alfa - 1 : alfa;
      final valor = _valorDoLance(raiz, lance, profundidade, piso, _infinito);
      // `null` = o lance entrega a vitória ao outro; fica de lado.
      if (valor == null) continue;
      if (valor > alfa) {
        alfa = valor;
        melhor = lance;
        // Um melhor novo desfaz os empates com o melhor antigo.
        empatados.clear();
      } else if (comEmpates && melhor != null && valor == alfa) {
        empatados.add(lance);
      }
    }
    // Todos entregam: a derrota vem no lance seguinte, qualquer que seja.
    if (melhor == null) {
      return (lances.first, _perdaNoLanceSeguinte(raiz), const <LanceQuatro>[]);
    }
    return (melhor, alfa, empatados);
  }

  /// O valor de [posicao] para quem tem a vez, olhando [profundidade] lances
  /// à frente, na janela alfa-beta (`alfa`, `beta`).
  ///
  /// Pede (e é o que o pai garante) que [posicao] não tenha desfecho e que
  /// quem tem a vez NÃO tenha vitória na mão: os filhos que dariam isso ao
  /// outro são descartados antes de a busca descer neles.
  ///
  /// A poda alfa-beta, em uma frase: `alfa` é o que quem joga já garantiu em
  /// outro lance, `beta` é o que o adversário já garantiu acima; quando um
  /// lance alcança `beta`, o adversário nunca deixaria a partida chegar aqui,
  /// e os lances restantes não precisam ser olhados.
  ///
  /// Com a tabela de transposição: a mesma posição, alcançada por outra ordem
  /// de lances, não é buscada de novo se a tabela já tem o valor dela olhado
  /// pelo menos tão fundo. A tabela guarda também o melhor lance achado, que
  /// passa a ser experimentado primeiro.
  int alfaBeta(PosicaoQuatro posicao, int profundidade, int alfa, int beta) {
    // No fim da visão, a posição sem desfecho vale o que a heurística diz
    // (ameaças com a paridade de linha, e a posição das peças; T030). O valor
    // é limitado bem abaixo do de uma partida decidida.
    if (profundidade == 0) {
      cortes++;
      return heuristica.avaliar(posicao);
    }
    final alfaOriginal = alfa;
    // Para saber se ESTA subárvore cortou algum caminho (e guardar isso na
    // tabela): compara o contador antes e depois.
    final cortesAntes = cortes;
    final tabela = this.tabela;
    var primeiro = -1; // o índice do lance que a tabela manda tentar antes
    if (tabela != null) {
      final i = tabela.procurar(posicao);
      if (i >= 0) {
        primeiro = tabela.melhores[i];
        if (tabela.profundidades[i] >= profundidade) {
          final valor = tabela.valores[i];
          // A resposta da tabela carrega o corte da busca que a guardou: sem
          // isto, um valor reaproveitado esconderia um horizonte, e a busca
          // pararia achando que viu o fim.
          if (tabela.cortou[i] != 0) cortes++;
          // O que a tabela sabe é um valor EXATO, um piso (a posição vale
          // pelo menos isto: houve poda por cima) ou um teto (vale no
          // máximo isto: nenhum lance passou de alfa).
          switch (tabela.tipos[i]) {
            case _exato:
              return valor;
            case _piso:
              if (valor > alfa) alfa = valor;
            case _teto:
              if (valor < beta) beta = valor;
          }
          if (alfa >= beta) return valor;
        }
      }
    }
    final lances = _ordenar(regras.lancesLegais(posicao), ordem);
    var melhor = -_infinito;
    var melhorIndice = -1;
    // Percorre os lances com o da tabela na frente; `indice` é a posição na
    // lista ordenada, que é o que a tabela guarda.
    for (var k = 0; k < lances.length; k++) {
      final indice = primeiro < 0
          ? k
          : (k == 0 ? primeiro : (k <= primeiro ? k - 1 : k));
      final valor =
          _valorDoLance(posicao, lances[indice], profundidade, alfa, beta);
      if (valor == null) continue;
      if (valor > melhor) {
        melhor = valor;
        melhorIndice = indice;
      }
      if (valor > alfa) alfa = valor;
      if (alfa >= beta) break; // poda
    }
    // Nenhum lance sobrou: todos entregam a vitória ao outro.
    if (melhor == -_infinito) return _perdaNoLanceSeguinte(posicao);
    tabela?.guardar(
      posicao,
      profundidade,
      melhor,
      melhor <= alfaOriginal ? _teto : (melhor >= beta ? _piso : _exato),
      melhorIndice,
      cortou: cortes != cortesAntes,
    );
    return melhor;
  }

  /// O valor de jogar [lance] em [posicao], ou `null` quando ele ENTREGA a
  /// vitória imediata ao outro (a casa de cima vence para ele).
  int? _valorDoLance(PosicaoQuatro posicao, LanceQuatro lance,
      int profundidade, int alfa, int beta) {
    final filho = _jogar(posicao, lance);
    final desfecho = regras.desfecho(filho);
    if (desfecho != null) return -valorDoDesfecho(filho, desfecho);
    if (regras.lancesQueVencem(filho).isNotEmpty) return null;
    // Negamax: o valor para mim é o oposto do valor para o outro, e a janela
    // dele é a minha invertida.
    return -alfaBeta(filho, profundidade - 1, -beta, -alfa);
  }

  /// O valor (negativo) de perder no lance seguinte ao de quem tem a vez.
  int _perdaNoLanceSeguinte(PosicaoQuatro posicao) =>
      -(valorVitoriaQuatro - (posicao.lancesJogados + 2));
}

/// Maior que qualquer valor de posição: o "menos infinito" de onde parte a
/// procura do melhor.
const int _infinito = valorVitoriaQuatro * 2;

/// O valor de [posicao] pela busca alfa-beta, até [profundidade] lances à
/// frente, e quantos nós ela visitou.
///
/// Não joga: serve aos testes, que comparam com [negamaxPuro]. Os dois têm de
/// dar o mesmo valor; a poda, com menos nós.
(int valor, int nos) valorAlfaBeta(
    RegrasDaModalidadeQuatro regras, PosicaoQuatro posicao, int profundidade) {
  final busca = _Busca(regras, ordemDoCentroQuatro(posicao.dimensoes.largura),
      _ContadorDeNos(null), HeuristicaQuatro(posicao.dimensoes));
  final desfecho = regras.desfecho(posicao);
  if (desfecho != null) return (valorDoDesfecho(posicao, desfecho), 0);
  if (profundidade > 0 && regras.lancesQueVencem(posicao).isNotEmpty) {
    return (valorVitoriaQuatro - (posicao.lancesJogados + 1), 0);
  }
  final valor = busca.alfaBeta(posicao, profundidade, -_infinito, _infinito);
  return (valor, busca.contador.nos);
}

/// O valor de [posicao] para quem tem a vez, olhando [profundidade] lances à
/// frente. Negamax puro: visita TODOS os lances, sem poda. No fim da visão,
/// a mesma [heuristica] da busca de verdade.
int _negamax(RegrasDaModalidadeQuatro regras, PosicaoQuatro posicao,
    int profundidade, _ContadorDeNos contador, HeuristicaQuatro heuristica) {
  contador.contar();
  final desfecho = regras.desfecho(posicao);
  if (desfecho != null) return valorDoDesfecho(posicao, desfecho);
  if (profundidade == 0) return heuristica.avaliar(posicao);
  var melhor = -_infinito;
  for (final lance in regras.lancesLegais(posicao)) {
    final valor = -_negamax(regras, regras.aplicar(posicao, lance),
        profundidade - 1, contador, heuristica);
    if (valor > melhor) melhor = valor;
  }
  return melhor;
}

/// O valor exato de [posicao] pelo negamax PURO (sem poda, sem atalho e sem
/// teto) até [profundidade] lances à frente, e quantos nós ele visitou.
///
/// Não joga: é a RÉGUA dos testes. A busca de verdade tem de dar o mesmo
/// valor que esta, com menos nós.
(int valor, int nos) negamaxPuro(
    RegrasDaModalidadeQuatro regras, PosicaoQuatro posicao, int profundidade) {
  final contador = _ContadorDeNos(null);
  final valor = _negamax(regras, posicao, profundidade, contador,
      HeuristicaQuatro(posicao.dimensoes));
  return (valor, contador.nos);
}

/// Conta os nós visitados e interrompe a busca quando passariam do teto, ou
/// quando o relógio passa do limite (só se houver limite).
class _ContadorDeNos {
  /// O teto (`null` = sem teto, só para as réguas dos testes).
  final int? teto;

  /// O relógio da busca e o limite em ms (`null` = sem limite de tempo).
  final Stopwatch? relogio;
  final int? limiteMs;

  /// Quantos nós já foram visitados.
  int nos = 0;

  _ContadorDeNos(this.teto, {this.relogio, this.limiteMs});

  /// Conta mais um nó; interrompe a busca se ele passaria do teto, ou se o
  /// tempo acabou.
  void contar() {
    if (teto != null && nos >= teto!) throw const _BuscaInterrompida('nos');
    nos++;
    // O relógio é lido a cada 1.024 nós, e não a cada nó: ler a hora custa
    // mais que visitar um nó. `nos & 1023 == 0` é "nos é múltiplo de 1024"
    // (os 10 bits de baixo zerados).
    if (limiteMs != null &&
        nos & 1023 == 0 &&
        relogio!.elapsedMilliseconds >= limiteMs!) {
      throw const _BuscaInterrompida('tempo');
    }
  }
}

/// Sinal interno de "a busca tem de parar": a exceção desfaz a recursão
/// inteira de uma vez, sem cada nível precisar conferir um retorno especial.
/// O [motivo] é o código que vai para a resposta (`nos` ou `tempo`).
class _BuscaInterrompida {
  final String motivo;
  const _BuscaInterrompida(this.motivo);
}

// ── A tabela de transposição ─────────────────────────────────────────────────

/// Até que profundidade o aprofundamento vai, no máximo. Só morde numa
/// modalidade em que a partida pode não ter fim (tirar e pôr a mesma peça);
/// cabe nos 7 bits da profundidade guardada na tabela.
const int profundidadeMaximaQuatro = 100;

/// O tamanho padrão da tabela: 2^20 entradas (pouco mais de um milhão), uns
/// 15 MB. Cabe com folga num aparelho de entrada, e é medido na bancada.
const int bitsDaTabelaQuatro = 20;

/// Os três tipos de valor que a tabela guarda (ver `alfaBeta`).
const int _exato = 1;
const int _piso = 2;
const int _teto = 3;

/// A memória da busca: posição → valor já calculado, até que profundidade, e
/// o melhor lance achado.
///
/// Tamanho FIXO (potência de 2), em listas tipadas paralelas (uma lista por
/// campo, a entrada `i` de cada uma é a mesma entrada), o que gasta poucos
/// bytes por entrada e nenhum objeto. Duas posições que caem na mesma gaveta
/// disputam o lugar: fica a olhada mais fundo (ela custou mais para achar).
class _TabelaDeTransposicao {
  final int _bits;
  final Int64List chaves;
  final Int8List lancesJogados;
  final Int8List profundidades; // 0 = gaveta vazia (nunca se guarda o 0)
  final Int8List tipos;
  final Int16List valores;
  final Int8List melhores;
  final Int8List cortou; // 1 = a busca que guardou cortou no horizonte

  _TabelaDeTransposicao(this._bits)
      : chaves = Int64List(1 << _bits),
        lancesJogados = Int8List(1 << _bits),
        profundidades = Int8List(1 << _bits),
        tipos = Int8List(1 << _bits),
        valores = Int16List(1 << _bits),
        melhores = Int8List(1 << _bits),
        cortou = Int8List(1 << _bits);

  /// A gaveta da posição: a chave misturada (multiplicada pela constante da
  /// razão áurea, o "hash de Fibonacci"), e os bits de cima do produto.
  int _gaveta(PosicaoQuatro posicao) =>
      ((posicao.chave + posicao.lancesJogados) * 0x9E3779B97F4A7C15) >>>
      (64 - _bits);

  /// O índice da entrada desta posição, ou -1 se a tabela não a tem.
  ///
  /// Confere a chave E os lances jogados: a chave identifica as peças, e o
  /// número de lances completa a identidade numa modalidade que tire peças
  /// (o valor da posição depende dele, pela distância da vitória).
  int procurar(PosicaoQuatro posicao) {
    final i = _gaveta(posicao);
    if (profundidades[i] != 0 &&
        chaves[i] == posicao.chave &&
        lancesJogados[i] == posicao.lancesJogados) {
      return i;
    }
    return -1;
  }

  /// Guarda o que a busca achou, se a gaveta está vazia ou tem uma olhada
  /// menos funda (ou igual: a mais recente é a da iteração atual).
  void guardar(PosicaoQuatro posicao, int profundidade, int valor, int tipo,
      int melhor, {required bool cortou}) {
    final i = _gaveta(posicao);
    if (profundidades[i] > profundidade) return;
    chaves[i] = posicao.chave;
    lancesJogados[i] = posicao.lancesJogados;
    profundidades[i] = profundidade;
    tipos[i] = tipo;
    valores[i] = valor;
    melhores[i] = melhor;
    this.cortou[i] = cortou ? 1 : 0;
  }
}
