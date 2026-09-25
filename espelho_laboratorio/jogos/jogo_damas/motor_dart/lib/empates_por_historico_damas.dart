/// Os empates que dependem do **histórico** da partida — arts. 97b e 98, e as
/// duas regras portuguesas (FPD 3.8.a e 3.8.b).
///
/// Port de `../motor/empates_por_historico_damas.py`. Leia lá a explicação
/// completa; aqui fica só o que muda por ser Dart.
///
/// Por que estas regras precisam de um objeto à parte
/// ---------------------------------------------------
/// Quase toda regra de damas se decide olhando **a posição**. Estas não —
/// perguntam *como se chegou aqui*:
///
/// - **art. 98**: a mesma posição pela terceira vez, com o mesmo lado a jogar;
/// - **art. 97b**: 20 lances de cada lado só com damas, sem captura nem
///   deslocamento de pedra;
/// - **FPD 3.8.b**: os mesmos 20 lances, mas só depois que a posição vira final
///   de ≤4 peças por lado com dama dos dois lados — a diferença é de *gatilho*;
/// - **FPD 3.8.a (a "Forçada")**: três damas que ocupam o Rio contra uma dama têm
///   12 lances para liquidá-la, e enquanto essa correlação durar a regra dos 20
///   lances **não vale** (3.8.b.4). É o único relógio que conta lances de um
///   jogador só.
///
/// Sem elas, o motor avalia como vantagem finais que o árbitro vai encerrar
/// empatados — e recusa trocas boas para "manter" uma vantagem inexistente.
///
/// A única diferença em relação ao Python
/// ---------------------------------------
/// A identidade da posição aqui é o **hash de Zobrist** (`Tabuleiro.hash`), e no
/// Python é a tupla das 32 casas mais a vez. A tupla não colide; o hash colide
/// com probabilidade ínfima. A troca é a mesma que a tabela de transposição já
/// faz, e a consequência de uma colisão aqui seria um empate declarado numa
/// posição que não repetiu — em 64 bits, algo que não se espera ver acontecer
/// uma vez sequer na vida do produto.
///
/// O hash **já inclui a vez** (ver `_zobristVezDasPretas` em
/// `tabuleiro_damas.dart`), o que é obrigatório: o art. 98 exige "com o mesmo
/// jogador a jogar", e ignorar a vez declararia empate no dobro da velocidade.
library;

import 'regras_damas.dart';
import 'tabuleiro_damas.dart';

// ⚠️ Os números NÃO moram aqui — moram no [Regulamento], e a razão é um defeito
// real encontrado em 2026-07-28. Enquanto foram constantes deste arquivo, o
// motor aplicava a regra brasileira (20 lances de cada lado) em partida
// anglo-americana, cujo regulamento manda **40** (WCDF 1.27.2). Nenhum teste
// pegava, e o `perft` também não pegaria: regra de empate não muda a contagem
// de lances legais.

/// Este lance interrompe a sequência do art. 97b (ou da WCDF 1.27.2)?
///
/// Interrompe se for **captura** ou se a peça movida for **pedra**. A consulta é
/// ao tabuleiro **antes** do lance: depois de aplicado, a peça já saiu da origem
/// e uma pedra que coroou nem pedra é mais.
bool zeraOContador(Tabuleiro antes, Lance lance) {
  if (lance.eCaptura) return true;
  final peca = antes.ler(lance.origem);
  return peca == pedraBranca || peca == pedraPreta;
}

/// Este lance interrompe a sequência da FMJD 8.5?
///
/// Só duas coisas mudam o equilíbrio: **captura** e **promoção**. Uma pedra que
/// anda sem coroar não zera este contador, e é aí que ele difere do art. 97b.
bool mudaOEquilibrio(Lance lance) => lance.eCaptura || lance.viraDama;

/// A correlação de forças da FMJD 8.3: 3 damas **ou mais** × 1 dama sozinha.
///
/// Sem pedras de nenhum dos lados. ⚠️ Ao contrário do art. 100 do CBJD, **não**
/// exige que a dama solitária esteja na grande diagonal — as duas regras
/// coexistem, e a mais apertada decide.
bool tresDamasContraUma(Tabuleiro tabuleiro) {
  var damasBrancas = 0;
  var damasPretas = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    final peca = tabuleiro.ler(casa);
    if (peca == pedraBranca || peca == pedraPreta) return false;
    if (peca == damaBranca) damasBrancas++;
    if (peca == damaPreta) damasPretas++;
  }
  return (damasBrancas >= 3 && damasPretas == 1) ||
      (damasPretas >= 3 && damasBrancas == 1);
}

/// Quantos **meios-lances** a FMJD 8.5 dá nesta posição; `null` se não vale.
///
/// Duas condições, ambas do texto: cada lado tem ao menos uma dama, e o total de
/// peças cai numa das faixas declaradas pelo regulamento.
int? limiteDeEquilibrioParado(Tabuleiro tabuleiro, Regulamento regulamento) {
  if (regulamento.lancesEquilibrioParado.isEmpty) return null;

  var damasBrancas = 0;
  var damasPretas = 0;
  var total = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    final peca = tabuleiro.ler(casa);
    if (peca == vazia) continue;
    total++;
    if (peca == damaBranca) damasBrancas++;
    if (peca == damaPreta) damasPretas++;
  }
  if (damasBrancas == 0 || damasPretas == 0) return null;

  for (final faixa in regulamento.lancesEquilibrioParado) {
    if (total >= faixa[0] && total <= faixa[1]) return 2 * faixa[2];
  }
  return null;
}

/// A posição satisfaz o **gatilho** da contagem de lances sem progresso?
///
/// Nas brasileiras e nas anglo-americanas não há gatilho: o contador anda desde o
/// primeiro lance, e isto responde sempre `true`.
///
/// Nas portuguesas há (FPD 3.8.b.1): a contagem de 20 lances só começa quando a
/// posição tem no máximo quatro peças de cada lado, com pelo menos uma dama de
/// cada lado. O número dos dois regulamentos é o mesmo; o gatilho não.
bool contadorDeProgressoEstaLigado(
    Tabuleiro tabuleiro, Regulamento regulamento) {
  final maximo = regulamento.maximoDePecasPorLadoParaContar;
  if (maximo == null && !regulamento.exigeDamaDosDoisLadosParaContar) {
    return true;
  }

  var totalBrancas = 0;
  var totalPretas = 0;
  var damasBrancas = 0;
  var damasPretas = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    final peca = tabuleiro.ler(casa);
    if (peca == pedraBranca) {
      totalBrancas++;
    } else if (peca == damaBranca) {
      totalBrancas++;
      damasBrancas++;
    } else if (peca == pedraPreta) {
      totalPretas++;
    } else if (peca == damaPreta) {
      totalPretas++;
      damasPretas++;
    }
  }

  if (maximo != null && (totalBrancas > maximo || totalPretas > maximo)) {
    return false;
  }
  if (regulamento.exigeDamaDosDoisLadosParaContar &&
      (damasBrancas == 0 || damasPretas == 0)) {
    return false;
  }
  return true;
}

/// Quem é o lado forte da **Forçada** (FPD 3.8.a), ou `null` se não é o caso.
///
/// A configuração é fechada: **sem pedras**, um lado com exatamente
/// [Regulamento.damasDaForcada] damas e o outro com exatamente uma.
///
/// Devolve a **cor** (e não um booleano) porque é isso que permite contar só os
/// lances de quem tem de ganhar — a leitura adotada dos "12 moves".
///
/// ⚠️ **Não** olha o Rio. Responde "estamos na configuração da Forçada?", que é a
/// pergunta que a FPD 3.8.b.(4) usa para desligar a regra dos 20 lances, inclusive
/// antes de o Rio ser ocupado. Quem olha o Rio é [forcadaEmCurso].
int? ladoForteDaForcada(Tabuleiro tabuleiro, Regulamento regulamento) {
  if (regulamento.lancesDaForcada == null) return null;

  var damasBrancas = 0;
  var damasPretas = 0;
  for (var casa = 1; casa <= nCasas; casa++) {
    final peca = tabuleiro.ler(casa);
    if (peca == pedraBranca || peca == pedraPreta) return null;
    if (peca == damaBranca) damasBrancas++;
    if (peca == damaPreta) damasPretas++;
  }

  if (damasBrancas == regulamento.damasDaForcada && damasPretas == 1) {
    return brancas;
  }
  if (damasPretas == regulamento.damasDaForcada && damasBrancas == 1) {
    return pretas;
  }
  return null;
}

/// A Forçada já **começou a contar** aqui? Devolve o lado forte, ou `null`.
///
/// É [ladoForteDaForcada] **mais** a ocupação do Rio pelo lado forte — "3 kings
/// controlling the River". Enquanto o forte não puser uma dama na grande
/// diagonal, o relógio dos 12 lances não anda, e o lance que a põe lá "is not
/// counted among the 12 moves".
int? forcadaEmCurso(Tabuleiro tabuleiro, Regulamento regulamento) {
  final forte = ladoForteDaForcada(tabuleiro, regulamento);
  if (forte == null) return null;

  final damaDoForte = forte == brancas ? damaBranca : damaPreta;
  for (final casa in rio) {
    if (tabuleiro.ler(casa) == damaDoForte) return forte;
  }
  return null;
}

// ── O EMPATE DECLARADO, em peças ───────────────────────────────────────────
//
// ⚠️ **Os identificadores são os MESMOS que o servidor envia** — o adaptador do
// backend (`motores/damas/motor_damas.py`, `_MOTIVOS_DE_EMPATE`) já os usava,
// traduzindo a prosa deste motor para eles. Inventar um segundo vocabulário aqui
// faria o app precisar de duas tabelas de tradução para a mesma regra: uma para
// o que ele mesmo julga (a partida no aparelho) e outra para o que chega do
// Desafio do Dia. São estes, e são cinco.

/// A mesma posição pela terceira vez (art. 98 / WCDF 1.28).
const String empatePosicaoRepetida = 'empate_posicao_repetida';

/// Três damas ou mais contra uma dama sozinha, sem capturá-la (FMJD 8.3).
const String empateTresDamasContraUma = 'empate_tres_damas_contra_uma';

/// A Forçada portuguesa: 12 lances do lado forte para liquidar (FPD 3.8.a).
const String empateForcada = 'empate_forcada';

/// Lances de cada lado sem captura nem deslocamento de pedra (art. 97b).
const String empateSemProgresso = 'empate_sem_progresso';

/// Lances sem captura nem promoção, no final parado (FMJD 8.5).
const String empateEquilibrioParado = 'empate_equilibrio_parado';

/// Todos os identificadores que [HistoricoDaPartida.empateDeclarado] devolve.
///
/// Existe pelo mesmo motivo que `identificadoresDeRecusa`: um `switch` sem caso
/// padrão sobre uma `String` não avisa nada, mas um teste que percorre esta
/// lista e cobra a chave de i18n avisa. Sem ela, uma regra de empate nova
/// chegaria ao aparelho como subtítulo em branco.
const List<String> identificadoresDeEmpate = [
  empatePosicaoRepetida,
  empateTresDamasContraUma,
  empateForcada,
  empateSemProgresso,
  empateEquilibrioParado,
];

/// O empate que encerrou a partida, desmontado em identificador, número e
/// artigo.
///
/// ## Por que três campos, e não uma frase
///
/// A frase só existe em português, e sem acento — o motor é espelhado com o
/// Python do laboratório, e pôr acento em um dos lados quebraria a paridade
/// byte a byte. Uma frase assim não pode ir para a tela de um app que fala três
/// idiomas (RF-DES-019b). Com as peças separadas, cada idioma monta a sua:
/// *"Posição repetida 3 vezes (art. 98)"*, *"Position repeated 3 times"*.
///
/// É o mesmo desenho de `RecusaDeLance`, que já resolvia isto para as leis de
/// captura desde o começo do jogo.
class EmpateDeclarado {
  const EmpateDeclarado({
    required this.identificador,
    required this.numero,
    required this.artigo,
  });

  /// A regra que encerrou, em `snake_case`. **É isto que o app consome.**
  ///
  /// Os valores possíveis estão em [identificadoresDeEmpate].
  final String identificador;

  /// O número que a regra cita, **na unidade em que o regulamento a escreve**.
  ///
  /// ⚠️ Não é sempre a mesma unidade, e isso é do regulamento, não do código:
  /// na repetição são **ocorrências da posição** (3); no art. 97b e na FMJD 8.5,
  /// **lances de cada lado** (20, 30); na Forçada, **lances do lado forte** (12).
  /// Quem já converteu foi este motor — a tela só escreve.
  final int numero;

  /// O artigo do regulamento, como se cita: `art. 98`, `FMJD 8.3`, `FPD 3.8.a`.
  ///
  /// Fica **fora** do `.arb` de propósito, e entra na frase por parâmetro: é
  /// citação de regulamento, igual nos três idiomas, e mantê-la em três arquivos
  /// só criaria três lugares para alguém trocar um número sem querer. A grafia
  /// vem do [Regulamento], que é quem sabe de qual família é esta partida.
  final String artigo;

  /// A frase em português, com os números concretos — a de sempre, byte a byte.
  ///
  /// ⛔ **Não é string de produção.** Serve ao registro da partida (o PDN), ao
  /// laboratório e como referência para quem escreve as traduções. O cadeado
  /// `ia/jogos/jogo_damas/testes/test_paridade_empates_damas.py` compara este
  /// texto com o do motor Python a cada meio-lance — mexer numa vírgula aqui
  /// derruba os dois motores de acordo.
  String get mensagem => switch (identificador) {
    empatePosicaoRepetida => 'posicao repetida $numero vezes ($artigo)',
    empateTresDamasContraUma =>
      '$numero lances sem capturar a dama solitaria ($artigo)',
    empateForcada =>
      '$numero lances sem liquidar a dama solitaria na Forcada ($artigo)',
    empateSemProgresso => '$numero lances de cada lado sem progresso ($artigo)',
    empateEquilibrioParado => '$numero lances sem captura nem promocao ($artigo)',
    // ⛔ Estourar, e nao devolver uma das frases acima: um identificador que
    // ninguem escreveu aqui sairia no PDN com o texto do artigo errado, e o
    // registro errado e pior que o registro ausente.
    _ => throw ArgumentError('identificador de empate desconhecido: '
        '"$identificador". Acrescente-o a identificadoresDeEmpate, a esta '
        'frase e as tres chaves .arb.'),
  };

  @override
  String toString() => '$identificador: $mensagem';
}

/// O que a partida acumulou e que a posição sozinha não conta.
///
/// São só dois números — e são os dois que faltavam para o motor conhecer o fim
/// da partida tão bem quanto o árbitro.
class HistoricoDaPartida {
  /// Quantas vezes cada posição já ocorreu, **incluindo a atual**.
  final Map<int, int> repeticoes = {};

  /// Há quantos meios-lances só se movem damas, sem captura e sem mexer pedra.
  int meiosLancesSemProgresso = 0;

  /// O segundo relógio, o da FMJD 8.5: zera com captura ou promoção, e **não**
  /// com movimento de pedra.
  int meiosLancesSemMudarOEquilibrio = 0;

  /// O terceiro relógio, o da **Forçada** portuguesa (FPD 3.8.a).
  ///
  /// Conta em **lances do lado forte**, não em meios-lances — é a única das
  /// contagens que não é "de cada lado" no texto, e misturar as unidades daria ao
  /// lado forte metade do prazo que o regulamento manda.
  int lancesDeForcada = 0;

  /// De qual regulamento saem os limites. O padrão é o brasileiro porque é o do
  /// primeiro jogo a entrar na loja — mas passar o certo **não é opcional**: nas
  /// anglo-americanas o limite de progresso é o dobro.
  final Regulamento regulamento;

  HistoricoDaPartida({this.regulamento = brasileiras});

  /// Um histórico começando numa posição, que já conta como ocorrida uma vez.
  ///
  /// Esquecer de contar a posição inicial faria o art. 98 precisar de **quatro**
  /// ocorrências — um erro de um, silencioso, que apareceria só como "o motor às
  /// vezes não vê o empate".
  factory HistoricoDaPartida.desde(Tabuleiro posicaoInicial,
      [Regulamento regulamento = brasileiras]) {
    final historico = HistoricoDaPartida(regulamento: regulamento);
    historico.repeticoes[posicaoInicial.hash] = 1;
    return historico;
  }

  /// Anota um lance jogado de verdade na partida.
  ///
  /// Recebe as duas posições porque cada uma responde a uma das regras: a de
  /// **antes** diz se o contador do art. 97b zera, e a de **depois** é a que
  /// passa a contar para o art. 98.
  void registrar(Tabuleiro antes, Lance lance, Tabuleiro depois) {
    meiosLancesSemProgresso =
        zeraOContador(antes, lance) ? 0 : meiosLancesSemProgresso + 1;
    // FPD 3.8.b.(1): fora do gatilho o contador não anda **nem guarda o que já
    // andou**. A contagem "begins immediately" quando a posição de final surge —
    // logo, some quando ela deixa de existir.
    if (!contadorDeProgressoEstaLigado(depois, regulamento)) {
      meiosLancesSemProgresso = 0;
    }
    meiosLancesSemMudarOEquilibrio =
        mudaOEquilibrio(lance) ? 0 : meiosLancesSemMudarOEquilibrio + 1;
    _registrarAForcada(antes, depois);
    repeticoes[depois.hash] = (repeticoes[depois.hash] ?? 0) + 1;
  }

  /// O relógio dos 12 lances da Forçada (FPD 3.8.a), só para as portuguesas.
  ///
  /// Três decisões, cada uma de uma frase do artigo:
  ///
  /// 1. **Conta-se pelo tabuleiro de ANTES** — o lance que ocupa o Rio não entra
  ///    na conta, e em `antes` o Rio ainda não estava ocupado.
  /// 2. **Só os lances do lado forte contam** (`antes.vez == forte`).
  /// 3. **Sair da configuração zera**; sair do Rio, não — senão bastaria sair e
  ///    voltar para ganhar mais doze lances.
  void _registrarAForcada(Tabuleiro antes, Tabuleiro depois) {
    if (regulamento.lancesDaForcada == null) return;

    if (ladoForteDaForcada(depois, regulamento) == null) {
      lancesDeForcada = 0;
      return;
    }

    final forte = forcadaEmCurso(antes, regulamento);
    if (forte != null && antes.vez == forte) lancesDeForcada++;
  }

  /// Quantas vezes esta posição já apareceu na partida.
  int ocorrencias(int hash) => repeticoes[hash] ?? 0;
  /// O empate que encerra a partida aqui, **em peças**, ou `null` se nenhum.
  ///
  /// ## Por que existe, e por que a prosa saiu daqui
  ///
  /// Até 2026-09-16 este método só devolvia a frase pronta em português, e ela
  /// ia direto para o subtítulo da tela de resultado — o único texto visível do
  /// jogo de damas fora do `l10n`. Quem jogava em inglês ou espanhol lia
  /// *"posicao repetida 3 vezes (art. 98)"*, sem acento e em português
  /// (RF-DES-019b; o achado está em `specs/008-jogo-das-damas/tasks.md`).
  ///
  /// Agora o motor devolve as **peças** — identificador, número e artigo — e
  /// quem monta a frase é quem sabe o idioma de quem está lendo. É o mesmo
  /// formato de [RecusaDeLance], e por isso a ponte no app já existia.
  ///
  /// ⚠️ **A prosa não morreu**: [motivoDeEmpate] continua devolvendo exatamente
  /// o mesmo texto, agora derivado daqui. Ela é o registro do PDN e a referência
  /// da tradução, e é o que `test_paridade_empates_damas.py` compara byte a byte
  /// entre este motor e o Python.
  EmpateDeclarado? empateDeclarado(Tabuleiro tabuleiro) {
    // O nome do artigo muda com a família, e isso não é preciosismo: o motivo
    // vai para o registro da partida, e citar o artigo brasileiro numa partida
    // anglo-americana é registro errado.
    // Até 2026-07-29 a escolha era um `if identificador == 'brasileira'`, o que
    // jogava toda modalidade nova no rótulo do WCDF.
    if (ocorrencias(tabuleiro.hash) >= regulamento.repeticoesParaEmpate) {
      return EmpateDeclarado(
        identificador: empatePosicaoRepetida,
        numero: regulamento.repeticoesParaEmpate,
        artigo: regulamento.artigoDaRepeticao,
      );
    }
    // FMJD 8.3 vem ANTES do art. 97b: na correlação de três damas contra uma ela
    // é mais apertada (15 lances contra 20), e a mais apertada decide.
    final limiteDaCorrelacao = regulamento.lancesTresDamasContraUma;
    if (limiteDaCorrelacao != null &&
        meiosLancesSemProgresso >= 2 * limiteDaCorrelacao &&
        tresDamasContraUma(tabuleiro)) {
      return EmpateDeclarado(
        identificador: empateTresDamasContraUma,
        numero: limiteDaCorrelacao,
        artigo: 'FMJD 8.3',
      );
    }

    // FPD 3.8.a — a Forçada. Vem antes da regra dos lances sem progresso, e não
    // por ser mais apertada: por **excluí-la**. O art. 3.8.b.(4) diz que "the
    // 20-move rule does not apply to the Forçada", então na configuração de três
    // damas contra uma o único relógio que vale é este.
    if (ladoForteDaForcada(tabuleiro, regulamento) != null) {
      final limite = regulamento.lancesDaForcada!;
      if (lancesDeForcada >= limite) {
        return EmpateDeclarado(
          identificador: empateForcada,
          numero: limite,
          artigo: regulamento.artigoDaForcada,
        );
      }
      return null;
    }

    if (meiosLancesSemProgresso >=
        regulamento.meiosLancesSemProgressoParaEmpate) {
      return EmpateDeclarado(
        identificador: empateSemProgresso,
        numero: regulamento.lancesSemProgressoParaEmpate,
        artigo: regulamento.artigoDosLancesSemProgresso,
      );
    }

    // FMJD 8.5 por último: mais frouxa em número, e no outro relógio.
    final limiteDoEquilibrio = limiteDeEquilibrioParado(tabuleiro, regulamento);
    if (limiteDoEquilibrio != null &&
        meiosLancesSemMudarOEquilibrio >= limiteDoEquilibrio) {
      // ⚠️ O campo conta **meios-lances**, e o artigo fala em lances de cada
      // lado — daí a divisão. É a mesma conversão que `relogios_de_empate.dart`
      // faz para a tela, e errá-la mostraria o dobro do prazo.
      return EmpateDeclarado(
        identificador: empateEquilibrioParado,
        numero: limiteDoEquilibrio ~/ 2,
        artigo: 'FMJD 8.5',
      );
    }

    return null;
  }

  /// O texto do artigo que encerra a partida aqui, ou `null` se nenhum.
  ///
  /// Devolve **texto** e não booleano por rastreabilidade: o motivo vai para o
  /// registro da partida, e "empatou" sem dizer por qual artigo é exatamente o
  /// que não deixa auditar depois.
  ///
  /// ⛔ **Não use isto na tela.** É português sem acento, e a tela tem três
  /// idiomas — chame [empateDeclarado] e traduza pelo identificador. Este texto
  /// serve ao registro da partida (o PDN), ao laboratório e à referência de
  /// tradução.
  String? motivoDeEmpate(Tabuleiro tabuleiro) =>
      empateDeclarado(tabuleiro)?.mensagem;
}
