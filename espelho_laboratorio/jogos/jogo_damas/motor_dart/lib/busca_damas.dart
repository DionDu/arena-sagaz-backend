/// Busca alfa-beta em Dart — o motor escolhendo o lance, no aparelho.
///
/// Port de `../motor/busca_damas.py`. Mesma estrutura, mesmas decisões de regra;
/// o que muda é o que precisa mudar para caber num celular.
///
/// As duas diferenças em relação ao motor de referência
/// -----------------------------------------------------
/// 1. **Tabela de transposição com hash de Zobrist e tamanho fixo**, em vez de
///    um dicionário indexado pela tupla das casas. O dicionário é *obviamente
///    correto* (tupla não colide) e por isso é o que o Python usa; aqui a
///    memória é limitada e a velocidade é o objetivo, e a troca aceita é a mesma
///    que todo motor de tabuleiro faz há trinta anos: uma chance ínfima de
///    colisão em troca de consulta em tempo constante e memória fechada.
/// 2. **Substituição sempre**: registro novo sobrescreve o antigo no mesmo
///    balde. É a política mais simples e, num motor sem *pondering*, das mais
///    eficazes.
///
/// A conferência contra o Python roda com a tabela **desligada** — aí o valor da
/// alfa-beta é o mesmo do minimax, que é uma quantidade bem definida e
/// independente de ordenação, hash e política de substituição.
library;

import 'dart:math';
import 'dart:typed_data';

import 'avaliacao_damas.dart';

// ⚠️ Import COM PREFIXO, e é obrigatório. Os dois módulos de avaliação exportam
// nomes parecidos, e o Dart — ao contrário do Python — recusa dois `avaliar` no
// mesmo escopo em vez de deixar um vencer em silêncio. O prefixo torna a escolha
// visível em cada chamada: `treinada.avaliarTreinado(...)` não se confunde com
// `avaliar(...)`.
import 'avaliacao_treinada_damas.dart' as treinada;
import 'empates_por_historico_damas.dart';

// ⚠️ Prefixo de novo, e aqui o motivo é pior que o de cima: os três vereditos da
// base de finais se chamam `derrota`, `empate` e `vitoria` — e `vitoria` **já
// existe neste arquivo**, vindo de `avaliacao_damas.dart`. Lá ela vale
// 1.000.000 (a nota de mate); na base vale 2 (o terceiro dos três estados de um
// final resolvido). São grandezas sem nenhuma relação, com o mesmo nome.
//
// Os dois arquivos dividem o **mesmo** prefixo de propósito: quem lê `finais.`
// não precisa saber em qual dos dois cada constante foi declarada. Dart permite
// isso — vários `import` podem apontar para o mesmo prefixo.
import 'indice_damas.dart' as finais;
import 'oraculo_de_finais_damas.dart';
import 'regras_damas.dart';
import 'retrograda_damas.dart' as finais;
import 'tabuleiro_damas.dart';

/// Teto de extensões de captura, para a quiescência não descer para sempre.
const int maxExtensao = 12;

const int exato = 0;
const int limiteInferior = 1;
const int limiteSuperior = 2;

/// O que aconteceu durante uma busca.
class Estatisticas {
  int nos = 0;
  int cortes = 0;
  int acertosNaTabela = 0;
  int profundidadeAtingida = 0;
  double tempoSegundos = 0;

  /// Quantas vezes a busca declarou empate pelos arts. 97b ou 98.
  ///
  /// Zero numa abertura é o esperado. Número alto num final de damas contra
  /// damas é o sinal de que o recurso está funcionando: cada um desses é um ramo
  /// em que o motor antes enxergava vantagem e agora enxerga o empate.
  int empatesPorHistorico = 0;

  /// Quantas vezes a busca **perguntou** à base de finais (T185 parte 2b).
  ///
  /// Zero quando não há base ligada — é o estado de todo nível que não seja o
  /// Sagaz, e o de qualquer busca do laboratório que não passe um oráculo.
  int consultasBase = 0;

  /// Quantas dessas perguntas **tiveram resposta** aproveitável.
  ///
  /// ⚠️ **As duas, e não uma só.** É a razão entre elas que diz se o *probing*
  /// valeu a pena: muitas consultas com poucos acertos significa que a árvore
  /// quase nunca alcança finais de 4 peças naquele tipo de partida, e o esforço
  /// de perguntar está custando mais do que rende. Com um contador só esse
  /// diagnóstico não existe.
  ///
  /// "Aproveitável" exclui dois casos em que a base responde e a busca não pode
  /// usar — o empate declarado pelo regulamento e a vitória sem distância. Ver
  /// [Buscador._consultarABase].
  int acertosBase = 0;

  /// Por que o aprofundamento parou: `profundidade`, `nos`, `tempo` ou
  /// `decidido` (achou vitória ou derrota forçada).
  ///
  /// Numa partida do Sagaz isto tem de dizer `nos` quase sempre. Se disser
  /// `tempo`, o aparelho é lento demais para o orçamento configurado e o
  /// jogador está enfrentando um adversário mais fraco do que o nível promete.
  String motivoDaParada = 'profundidade';

  /// O número que a etapa 3 do plano mede. Zero se a busca não durou nada.
  double get nosPorSegundo => tempoSegundos > 0 ? nos / tempoSegundos : 0;
}

/// O que a busca devolve.
class Resultado {
  final Lance? lance;
  final int nota;
  final List<Lance> variantePrincipal;
  final Estatisticas estatisticas;

  const Resultado(this.lance, this.nota, this.variantePrincipal, this.estatisticas);
}

/// Quão pior o lance sorteado pode ser, em centésimos de pedra.
///
/// Espelho de `MARGEM_DO_ERRO` no Python — 200 = duas pedras. É o freio de
/// sanidade que separa "adversário fraco" de "adversário quebrado": dar **uma**
/// pedra é o engano clássico de quem aprende; entregar uma dama de graça, ou
/// entrar numa perda forçada, parece defeito e não dificuldade baixa.
const int margemDoErroPadrao = 200;

/// Um nível de dificuldade, definido por **orçamento de busca**.
///
/// Os quatro níveis do app não são quatro motores: são o mesmo motor com mais ou
/// menos permissão para pensar.
///
/// Os freios, em ordem de força — e a ordem surpreendeu quando foi medida em
/// 2026-08-14, ver o diário do plano:
///
/// 1. **[extensaoDeCaptura]** é o mais forte de todos. Com a quiescência ligada,
///    mesmo profundidade 2 enxerga toda troca até o fim e nunca deixa peça
///    pendurada — que é o jogo inteiro contra quem está aprendendo. Em damas a
///    captura é obrigatória, então estender pelo ramo de captura equivale a ver
///    a resposta do adversário.
/// 2. **[profundidade]**, pelo mesmo motivo: 1 não vê a resposta, 2 vê.
/// 3. **[chanceDeErrar]** e **[margemDoErro]**, que sorteiam um lance pior na
///    raiz. A margem decide o *tamanho* do erro; a chance, só a frequência.
/// 4. **[ruido]** — o mais fraco, e por muito. Ele entra na avaliação de cada
///    folha, e o minimax é um filtro de ruído: sorteios independentes se
///    cancelam ao subir pela árvore.
///
/// ⚠️ Os freios 1 e 2 só funcionam **juntos**. Medido: profundidade 2 sem
/// quiescência e profundidade 1 com quiescência dão os dois 0% de derrota; só
/// profundidade 1 **sem** quiescência afrouxa de fato.
///
/// O [tetoDeNos] é o orçamento **de verdade** desde 2026-07-28: contar posições
/// visitadas, e não segundos, é o que faz o nível ser o mesmo nível no celular
/// de entrada e no topo de linha. O [tempoMaximo] virou **rede de segurança** —
/// existe para o aparelho muito lento não travar a interface, e quando dispara
/// [Estatisticas.motivoDaParada] registra que aquilo não era mais o nível.
///
/// ⚠️ **A rede é FOLGADA de propósito: 10 s nos quatro níveis** (2026-08-26,
/// decisão do dono). O raciocínio é o contrário do intuitivo:
///
/// > toda vez que a rede morde, a promessa do teto de nós se quebra — o nível
/// > deixa de ser o mesmo nível naquele aparelho, e o log grava
/// > `motivo_parada = tempo`, que é o motor dizendo "aqui eu não fui o Magno".
///
/// Logo, **quanto mais alta a rede, mais fiel o nível**. Com 3 s ela era a
/// primeira a morder num aparelho ruim ou ocupado com tarefas em segundo plano;
/// com 10 s quem termina o trabalho é o orçamento de nós, e a rede volta a ser o
/// que o nome diz: o que se aciona quando tudo já deu errado.
///
/// ⚠️ **É um número só para os quatro, e isso é a decisão.** Uma rede por nível
/// (20/15/10, acompanhando o relógio de cada personagem) a transformaria em
/// parâmetro de dificuldade, e ela não é: ela não desenha nível nenhum. O valor
/// único diz a verdade — *nenhum lance da CPU passa de 10 s, em nível nenhum*.
///
/// ⚠️ **Não confundir com as outras duas grandezas de tempo das damas**, que
/// esta mudança NÃO tocou:
///
/// | grandeza | quanto | onde |
/// |---|---|---|
/// | espera-alvo (encenação) | 5,0·4,0·3,0·2,0 × base do Remote Config | `politica_dificuldade_damas.dart` |
/// | relógio da jogada | sem · 30 · 25 · 20 s | `logica/dificuldade_damas.dart` (app) |
/// | **rede de segurança** | **10 s nos quatro** | aqui, [tempoMaximo] |
///
/// Os 10 s cabem folgados no **menor** relógio da tela (os 20 s do Magno), com
/// 10 s de sobra para a animação da peça, o tique de 1 s do cronômetro e
/// qualquer engasgo — e por isso continuam valendo no dia em que o cronômetro do
/// personagem aparecer na tela (T198).
///
/// ⚠️ Cortar por tempo **nunca devolve lance ruim**: o laço é de aprofundamento
/// iterativo, e o `break` mantém o melhor lance da última profundidade
/// **completa**. O que se perde é profundidade, não legalidade.
class Nivel {
  final String identificador;
  final String nome;
  final int profundidade;
  final int ruido;
  final int? tetoDeNos;
  final double? tempoMaximo;
  final bool extensaoDeCaptura;
  final double chanceDeErrar;
  final int margemDoErro;

  const Nivel(this.identificador, this.nome, this.profundidade,
      {this.ruido = 0,
      this.tetoDeNos,
      this.tempoMaximo,
      this.extensaoDeCaptura = true,
      this.chanceDeErrar = 0,
      this.margemDoErro = margemDoErroPadrao});

  /// Uma cópia com alguns campos trocados — é o que a bancada usa para o dono
  /// mexer nos freios sem precisar de um `Nivel` novo por tentativa.
  ///
  /// `copyWith` é o nome consagrado em Dart para isto; mantido em inglês porque
  /// é idioma da linguagem, como `toString`.
  Nivel copyWith({
    String? nome,
    int? profundidade,
    int? ruido,
    bool? extensaoDeCaptura,
    double? chanceDeErrar,
    int? margemDoErro,
  }) =>
      Nivel(
        identificador,
        nome ?? this.nome,
        profundidade ?? this.profundidade,
        ruido: ruido ?? this.ruido,
        tetoDeNos: tetoDeNos,
        tempoMaximo: tempoMaximo,
        extensaoDeCaptura: extensaoDeCaptura ?? this.extensaoDeCaptura,
        chanceDeErrar: chanceDeErrar ?? this.chanceDeErrar,
        margemDoErro: margemDoErro ?? this.margemDoErro,
      );
}

/// Aparelho de referência: Galaxy A35 5G, **160.593 nós/s** medidos na etapa 3c.
/// Os tetos abaixo são "quanto o A35 pensaria naquele tempo", arredondados ao
/// milhar. ⚠️ São provisórios — a calibração de verdade é a etapa 9.
///
/// Os mesmos números vivem em `../motor/busca_damas.py`; a escrituração é dupla
/// de propósito, e o contrato da etapa C é quem vai travar os dois num arquivo só.
const int nosPorSegundoNoAparelhoDeReferencia = 160593;

// ⚠️ ESCRITURAÇÃO DUPLA — estes quatro níveis existem também em
// `../motor/busca_damas.py`, e as justificativas completas de cada número estão
// lá. Mudou um lado, muda o outro na mesma resposta.
//
// Não os altere por intuição: foi intuição que os deixou intocáveis por três
// semanas enquanto nem a Cacau era vencível.

/// A rede de segurança dos quatro níveis, em segundos.
///
/// **Um número só, e de propósito** — ver a seção da rede em [Nivel]. Ela não é
/// parâmetro de dificuldade: é o limite acima do qual desistir é melhor que
/// insistir, e esse limite não tem por que mudar de personagem para personagem.
///
/// Os 10 s cobrem o caso que o dono descreveu em 2026-08-26: *"telefone ruim que
/// esteja com muitas tarefas em segundo plano"*. Ali o aparelho não está lento
/// por ser fraco — está lento porque o sistema tirou dele a CPU no meio da
/// busca, e nenhum orçamento de nós prevê isso.
const double redeDeSeguranca = 10.0;

/// Validada **jogando**, em 2026-08-14: o dono ganhou 3 de 4 partidas na bancada
/// com exatamente esta configuração. É o único nível cujo número veio de partida
/// contra gente.
const Nivel cacau = Nivel('cacau', 'Cacau', 1,
    ruido: 90,
    tetoDeNos: 24000,
    tempoMaximo: redeDeSeguranca,
    extensaoDeCaptura: false,
    chanceDeErrar: 0.35,
    margemDoErro: 200);

/// Um degrau só acima da Cacau — e é o mais brusco da escala: a Pita **enxerga
/// a resposta** do adversário, mas não segue as trocas até o fim.
const Nivel pita = Nivel('pita', 'Pita', 2,
    ruido: 40,
    tetoDeNos: 24000,
    tempoMaximo: redeDeSeguranca,
    extensaoDeCaptura: false,
    chanceDeErrar: 0.25,
    margemDoErro: 150);

/// Aqui entra a **quiescência**: o Tex deixa de cair em troca simples.
///
/// ⚠️ Profundidade 3, e não 4, por observação do dono de que o vão entre Pita e
/// Tex ficaria grande demais — a primeira proposta pulava dois degraus da escada
/// medida de uma vez.
const Nivel tex = Nivel('tex', 'Tex', 3,
    tetoDeNos: 48000,
    tempoMaximo: redeDeSeguranca,
    chanceDeErrar: 0.08,
    margemDoErro: 80);

/// ⚠️ **288 mil nós desde 2026-08-26, e o número saiu de ARM real.** Decisão do
/// dono. A conta é a espera-alvo do Magno (0,80 s, `politica_dificuldade_damas`)
/// vezes o que o aparelho de entrada faz por segundo **com o motor nativo**:
///
/// | aparelho | motor | nós/s | 288.000 nós custam |
/// |---|---|---|---|
/// | Galaxy A04 | **Rust** | ~390.000 | **0,74 s** |
/// | Galaxy A04 | Dart | ~39.400 | 7,3 s ⛔ |
/// | iPhone A15 | Rust | 1,92 M | 0,15 s |
///
/// Medido na bancada do aparelho em 25/08/2026 (Galaxy A04, `arm64-v8a`,
/// Android 14). O ganho de força medido em arena: −220 Elo contra o juiz em
/// 96.000, −85 em 300.000 — cerca de **+91 Elo** só por este número.
///
/// ⚠️ **O teto é o mesmo para os DOIS motores**, e é assim de propósito: o
/// nível tem de ser o mesmo nível em qualquer aparelho, e um teto por motor
/// faria a mesma partida valer coisas diferentes. A consequência é a linha ⛔
/// acima: em Dart, 288.000 nós custam 7,3 s no aparelho de entrada.
///
/// ⚠️ **É por isso que a T199 existe.** Onde o motor nativo não carregou, o
/// nível Sagaz **não é ofertado** — em vez de ser ofertado e jogado em 7 s por
/// lance, que não é o mesmo produto. A [redeDeSeguranca] de 10 s **não** reabre
/// essa questão, e a aritmética de que 7,3 s cabem em 10 s não é argumento: o
/// A04 é o pior aparelho **que medimos**, não o pior que existe. Reabrir a T199
/// pede medida nova.
///
/// Com a rede em 10 s, ela só dispara no caso patológico — o nativo morreu no
/// meio da partida, ou o sistema tirou a CPU do app —, e aí
/// `Estatisticas.motivoDaParada` grava `tempo`, que é o motor dizendo que
/// aquilo não era mais o nível.
///
/// ✅ **O Magno está confirmado** — decisão do dono em 2026-08-14, depois de
/// jogar contra o motor. O alvo dele é menos de 1% de derrota **contra um
/// adulto**, e não contra jogo perfeito; a regra do nível Sagaz continua
/// respeitada.
///
/// Histórico do número: 321 mil → **96 mil** em 2026-08-14 (corte medido: em 10
/// posições muda 2 lances, perda de 0,05 pedra em média; ver
/// `../bin/medir_orcamento_damas.dart`) → **288 mil** em 2026-08-26, quando o
/// motor Rust passou a caber nele.
const Nivel sagaz =
    Nivel('sagaz', 'Sagaz', 64, tetoDeNos: 288000, tempoMaximo: redeDeSeguranca);

const Map<String, Nivel> niveis = {
  'cacau': cacau, 'pita': pita, 'tex': tex, 'sagaz': sagaz,
};

// ⚠️ AQUI HAVIA UMA CLASSE `_Registro`, E APAGÁ-LA VALEU 38 ms POR LANCE.
//
// A tabela era `List<_Registro>`: com 20 bits, **1.048.576 objetos**, criados um
// a um no construtor do [Buscador]. Medido em 21/08/2026, neste PC:
//
//   bits 20 → 37,9 ms só para construir a tabela
//   bits 17 →  3,3 ms
//   bits 14 →  0,5 ms
//
// Trinta e oito milissegundos **antes do primeiro nó**. E o app paga isso a
// **cada lance**, porque `pedirLanceDamas` roda num isolate novo por lance
// (`compute`) e cada isolate constrói o seu buscador do zero: num lance de
// ~160 ms, quase um quarto era alocação — mais o trabalho do coletor de lixo
// depois, que não aparece no relógio mas aparece na bateria e no calor. O dono
// relatou o iPhone esquentando nas damas, e não no Jogo dos Pontinhos; o
// Pontinhos não tem tabela de transposição nenhuma.
//
// A troca: em vez de um objeto por casa, **uma coluna por campo**. Cinco
// alocações no lugar de um milhão — e listas de tipo fixo (`Int64List` e
// companhia) são blocos contínuos de memória, em que o processador lê vizinhos
// de graça; um milhão de objetos espalhados pelo montão não permite isso.
//
// ⚠️ **Isto não muda um lance sequer, e é essa a propriedade que importa.**
// Mesmo tamanho, mesmo índice (`hash & _mascara`), mesma política de
// substituição, mesmas colisões. É refatoração de *armazenamento*, não de busca
// — ao contrário de encolher a tabela, que muda quais posições colidem e por
// isso precisa passar pela arena antes de entrar (T189).
//
// Os campos ficam direto no [Buscador], e não numa classe "tabela": a busca os
// consulta milhões de vezes por lance, e cada indireção no caminho quente custa.
// O preço é ler `_ttNota[i]` em vez de `balde.nota`.

/// Base das duas paradas por orçamento — ver [_TempoEsgotado] e [_NosEsgotados].
class _OrcamentoEsgotado implements Exception {
  const _OrcamentoEsgotado();
}

/// O relógio estourou. Rede de segurança, ver [Nivel.tempoMaximo].
class _TempoEsgotado extends _OrcamentoEsgotado {
  const _TempoEsgotado();
}

/// O teto de posições visitadas estourou. É o critério normal de parada.
class _NosEsgotados extends _OrcamentoEsgotado {
  const _NosEsgotados();
}

// ---------------------------------------------------------------------------
// O buscador
// ---------------------------------------------------------------------------

class Buscador {
  final Regulamento regulamento;
  final PesosAvaliacao pesos;

  /// As tabelas de padrões treinadas. Quando presentes, **substituem** a
  /// avaliação escrita à mão — [pesos] passa a ser ignorado.
  ///
  /// Por que é um campo e não uma função injetada
  /// --------------------------------------------
  /// Receber a avaliação como `int Function(Tabuleiro)` seria mais flexível e
  /// custaria caro no lugar errado: a avaliação é a folha da árvore, chamada
  /// centenas de milhares de vezes por lance. Uma chamada por ponteiro ali não
  /// pode ser embutida pelo compilador AOT; um `if` num campo `final`, sim.
  ///
  /// Por que o padrão é `null`
  /// -------------------------
  /// O arquivo de pesos é um *asset* do app, carregado por `rootBundle`. O motor
  /// tem de funcionar sem ele — e funciona: sem tabelas treinadas, joga com a
  /// avaliação manual, que é a que sempre jogou.
  ///
  /// ⚠️ Quem decide se a treinada substitui a manual em produção é a **arena da
  /// etapa 9**. Enquanto ela não rodar, este campo fica desligado por padrão.
  final treinada.PesosDosPadroes? pesosTreinados;

  /// A base de finais que a busca consulta **dentro** da árvore, ou `null`.
  ///
  /// ── O que ela compra ───────────────────────────────────────────────────
  ///
  /// Sem ela, numa posição de 8 peças a busca gasta nós explorando finais de 4
  /// peças cuja resposta já está gravada — e no fim ainda **estima** o valor
  /// deles com a avaliação estática. Com ela, o ramo termina na verdade exata e
  /// o orçamento que sobra desce em outro lugar. O ganho é duplo: menos nós
  /// desperdiçados e certeza onde antes havia palpite.
  ///
  /// ── ⚠️ `null` é o padrão, e isso não é timidez ─────────────────────────
  ///
  /// Um [Buscador] sem oráculo joga **exatamente** como jogava antes de
  /// 2026-08-27, nó por nó. É o que mantém reprodutível toda a arena já medida
  /// (os −263, −220 e −85 Elo contra o juiz), e é o que permite montar as três
  /// arenas — Magno com base contra juiz sem base, e as outras duas — sem uma
  /// linha de código por arena.
  ///
  /// ⚠️ **E é o que separa este passo do cadeado de equivalência.** Enquanto o
  /// motor Rust não tiver a base, ligá-la só do lado Dart faria os dois motores
  /// escolherem lances diferentes em todo final de 4 peças, e
  /// `conferir_equivalencia_com_rust.dart` cairia — com razão. Desligada, a
  /// capacidade entra sem que nada mude.
  final OraculoDeFinais? baseDeFinais;

  /// Ligar/desligar a tabela de transposição.
  ///
  /// Desligável por causa da conferência contra o Python: a tabela faz uma
  /// posição alcançada por dois caminhos devolver o valor da busca mais funda —
  /// melhor para jogar, e diferente do minimax de profundidade fixa.
  final bool usarTabela;

  /// Ligar/desligar a quiescência, pelo mesmo motivo.
  ///
  /// ⚠️ Desde 2026-08-14 este campo é só o **padrão**: [buscar] aceita o seu
  /// próprio, e [Nivel.extensaoDeCaptura] o usa para afrouxar os níveis fracos.
  /// Quem manda durante a busca é [_extensaoAtiva].
  final bool extensaoDeCaptura;

  /// Ligar/desligar os arts. 97b e 98 **dentro** da busca.
  ///
  /// Mesma motivação das duas chaves acima: a conferência contra o Python roda
  /// com um minimax que não conhece histórico nenhum, e comparar contra um motor
  /// que conhece acusaria a poda de mentir quando ela está certa.
  ///
  /// Fora da conferência, **deixe ligada**. Desligá-la devolve o motor de antes
  /// de 2026-07-28, que achava estar ganhando finais empatados.
  final bool usarEmpatesPorHistorico;

  /// As posições já ocorridas na partida de verdade, vindas do `historico` de
  /// [buscar]. Vazio quando ninguém passa nada.
  Map<int, int> _repeticoesNaPartida = const {};

  /// As posições do caminho da raiz até o nó atual, com quantas vezes cada uma
  /// aparece **neste ramo**. É o que permite ver a repetição que ainda não
  /// aconteceu, mas que o motor pode forçar.
  final Map<int, int> _noCaminho = {};

  /// O limite do art. 97b (ou WCDF 1.27.2) em meios-lances, lido do regulamento
  /// uma vez só: é consultado a cada nó, e resolver a propriedade um milhão de
  /// vezes por busca custaria sem comprar nada.
  late final int _meiosLancesParaEmpate =
      regulamento.meiosLancesSemProgressoParaEmpate;

  /// O limite da FMJD 8.3 em meios-lances, ou -1 se o regulamento não a tem.
  /// Serve de **porteiro**: só quando o contador o alcança é que vale a pena
  /// varrer o tabuleiro para saber se a correlação de forças vale.
  late final int _meiosLancesDaCorrelacao =
      regulamento.lancesTresDamasContraUma == null
          ? -1
          : 2 * regulamento.lancesTresDamasContraUma!;

  /// O **menor** dos limites da FMJD 8.5, em meios-lances; -1 se a regra não
  /// existe. Mesmo papel de porteiro: abaixo dele nenhuma faixa pode ter
  /// disparado, então nem se conta as peças.
  late final int _menorLimiteDeEquilibrio =
      regulamento.lancesEquilibrioParado.isEmpty
          ? -1
          : 2 *
              regulamento.lancesEquilibrioParado
                  .map((faixa) => faixa[2])
                  .reduce((a, b) => a < b ? a : b);

  // ── A tabela de transposição, em colunas ─────────────────────────────────
  //
  // Cinco listas paralelas: a casa `i` de cada uma descreve o mesmo registro.
  // Ver o bloco longo onde a classe `_Registro` morava.

  /// O hash de Zobrist da posição guardada nesta casa. `Int64List` porque o
  /// hash usa os 64 bits do inteiro — um `Int32List` truncaria e faria posições
  /// diferentes parecerem a mesma.
  late final Int64List _ttChave;

  /// A que profundidade a nota foi calculada. **`-1` significa casa vazia**, e é
  /// por isso que esta coluna é preenchida à mão no construtor: uma lista de
  /// tipo fixo nasce zerada, e `0` aqui quer dizer "avaliada na folha", que é
  /// coisa bem diferente de "nunca escrita".
  late final Int32List _ttProfundidade;

  /// A avaliação guardada, em centésimos de pedra.
  late final Int32List _ttNota;

  /// Se a nota é [exato], [limiteInferior] ou [limiteSuperior]. `Uint8List`
  /// basta para três valores, e quanto menor a coluna mais dela cabe no cache.
  /// O zero natural da lista **é** `exato`, que era o padrão do campo antigo.
  late final Uint8List _ttMarcador;

  /// O melhor lance encontrado naquela posição — o que faz a ordenação começar
  /// pelo candidato certo. Não cabe em lista de tipo fixo (é um objeto), mas
  /// `List.filled` aloca **um** vetor de referências nulas, e não um milhão de
  /// objetos: o custo é o do vetor, não o dos lances.
  late final List<Lance?> _ttLance;

  final int _mascara;

  /// Heurística de histórico: quanto cada par (origem, destino) já causou de
  /// corte. Vetor plano em vez de `Map` — a ordenação consulta isto a cada
  /// comparação, e o custo do hash aparecia na medição.
  final Int32List _historico = Int32List(33 * 33);

  /// Um registro de desfazer por nível de profundidade, alocado uma vez só.
  /// 128 cobre profundidade 64 mais as extensões de captura com folga.
  final List<DesfazerLance> _pilhaDeDesfazer =
      List.generate(128, (_) => DesfazerLance());

  final Random _aleatorio;

  Estatisticas _estatisticas = Estatisticas();
  int _prazoEmMicros = -1;

  /// Teto de posições visitadas na profundidade em curso; -1 = sem teto.
  int _tetoDeNos = -1;
  int _ruido = 0;

  /// A quiescência **desta busca** — ver [extensaoDeCaptura] e [buscar].
  late bool _extensaoAtiva = extensaoDeCaptura;

  /// A chance de sortear um lance pior **desta busca** — ver
  /// [Nivel.chanceDeErrar].
  double _chanceDeErrar = 0;

  /// Quão pior o lance sorteado pode ser — ver [Nivel.margemDoErro].
  int _margemDoErro = margemDoErroPadrao;

  final Stopwatch _relogio = Stopwatch();

  /// [bitsDaTabela] define o tamanho: 2^bits registros. 20 bits ≈ 1 milhão de
  /// entradas, que numa busca de celular é folgado e cabe em poucos MB.
  ///
  /// ⚠️ **Construir um [Buscador] não é grátis** — ele aloca a tabela inteira.
  /// Com 20 bits são **4,3 ms** neste PC depois da mudança para colunas — eram
  /// **37,9 ms** quando cada casa era um objeto.
  /// Reaproveite o mesmo buscador ao longo de uma partida quando puder; criar um
  /// por lance é o que o app faz hoje, e é o que a T190 discute.
  Buscador({
    this.regulamento = brasileiras,
    this.pesos = pesosPadrao,
    this.pesosTreinados,
    this.baseDeFinais,
    this.usarTabela = true,
    this.extensaoDeCaptura = true,
    this.usarEmpatesPorHistorico = true,
    int? semente,
    int bitsDaTabela = 20,
  })  : _mascara = (1 << bitsDaTabela) - 1,
        _aleatorio = Random(semente ?? DateTime.now().microsecondsSinceEpoch) {
    final casas = 1 << bitsDaTabela;
    _ttChave = Int64List(casas);
    _ttProfundidade = Int32List(casas)
      // `-1` = casa vazia. Ver o comentário do campo: sem esta passada, o zero
      // natural da lista faria toda casa nunca escrita parecer uma avaliação de
      // folha guardada — e a busca leria lixo como se fosse nota.
      ..fillRange(0, casas, -1);
    _ttNota = Int32List(casas);
    _ttMarcador = Uint8List(casas);
    _ttLance = List<Lance?>.filled(casas, null);

    // ⚠️ Pesos de uma modalidade não valem em outra, e o erro é MUDO.
    //
    // Cada modalidade tem seu auto-jogo e seu treino: o modelo das brasileiras
    // aprendeu num jogo em que a dama voa e a pedra captura para trás. Usá-lo
    // nas anglo-americanas produz notas plausíveis e erradas — a busca roda, a
    // partida termina, e o resultado não vale nada.
    //
    // No app isto importa mais que no laboratório: quem escolhe a modalidade é o
    // jogador, na tela, e carregar o asset errado é um `if` de distância.
    // Descoberto em 2026-08-12 — ver a entrada do plano.
    final treino = pesosTreinados;
    if (treino != null && treino.regulamento != regulamento.identificador) {
      throw ArgumentError(
        "os pesos treinados são da modalidade '${treino.regulamento}', mas o "
        "buscador joga '${regulamento.identificador}'. Cada modalidade precisa "
        'do seu próprio treino.',
      );
    }
  }

  /// Até quantas peças a base sabe responder — 4, hoje. `-1` quando não há base,
  /// e aí a comparação `pecas <= _pecasNaBase` é falsa em todo nó.
  ///
  /// `late final` = calculado na primeira leitura e guardado. Sem isso, a busca
  /// perguntaria o mesmo número ao oráculo milhões de vezes por lance.
  late final int _pecasNaBase = baseDeFinais?.maximoDePecas ?? -1;

  /// O [finais.Indexador] das consultas à base — **um só, para a busca inteira**.
  ///
  /// Ele carrega sete vetores de trabalho, e criar um por consulta jogaria fora
  /// o trabalho de montá-los a cada nó de final. `late` porque um buscador sem
  /// base nunca o constrói.
  late final finais.Indexador _indexadorDaBase = finais.Indexador();

  /// O que a base tem a dizer sobre esta posição, **já na escala da busca** — ou
  /// `null` quando ela não tem o que dizer, e aí a busca segue normalmente.
  ///
  /// ── A tradução de escala, que é onde mora o perigo ─────────────────────
  ///
  /// A base fala em três estados (`finais.derrota`, `finais.empate`,
  /// `finais.vitoria`) mais uma **distância em meios-lances**. A busca fala em
  /// centésimos de pedra, com [vitoria] = 1.000.000 reservado ao mate. Traduzir
  /// errado tem duas consequências, e as duas são silenciosas:
  ///
  /// 1. **Se o veredito não dominar a avaliação estática**, a busca troca uma
  ///    vitória certa por uma posição de nota alta. Por isso a nota sai da faixa
  ///    do mate, e não de uma soma com [_avaliarComRuido].
  /// 2. **Se a distância não entrar**, toda vitória vale igual e o motor fica
  ///    dando voltas numa posição ganha até os arts. 97-100 declararem empate.
  ///    Por isso ela é subtraída: ganhar em 10 vale mais que ganhar em 40.
  ///
  /// A conta é a **mesma** que o motor já usa para o afogamento
  /// (`-vitoria + ply`): o desfecho acontece no meio-lance `ply + distancia`,
  /// então a nota é `vitoria - (ply + distancia)` para quem ganha, e o simétrico
  /// para quem perde. Isso a mantém comparável com os mates que a própria busca
  /// encontra — que é o que faz `nota.abs() > vitoria - 1000` continuar valendo
  /// em [buscar], sem uma linha nova lá.
  ///
  /// ── Os dois casos em que a base responde e a busca NÃO usa ─────────────
  ///
  /// **1. O empate declarado pelo regulamento.** A base foi construída com
  /// `regras_de_empate_aplicadas: true`: os arts. 97-100 converteram em empate
  /// as vitórias que o lado forte não conclui dentro do limite de lances. Só que
  /// ela conta esse limite **a partir da posição avaliada**, como se o contador
  /// estivesse zerado ali — e dentro da árvore ele quase nunca está. O
  /// discriminador é exato e barato: um empate de verdade não tem distância
  /// (ninguém "empata em 12"), então **empate COM distância ⇒ empate
  /// declarado**. Medido nas 41 fatias da base real em 25/08/2026, sem uma
  /// divergência. Ver `_ehEmpateDeclarado` em `consulta_base_finais_damas.dart`,
  /// que aplica a mesma regra na raiz.
  ///
  /// **2. A vitória sem distância**, que acontece quando a base foi carregada
  /// com `comDistancias: false`. Sem distância não há como pontuar a vitória sem
  /// achatar todas num valor só — ver o item 2 acima.
  ///
  /// ── ⚠️ A aproximação que fica, e o sentido dela ────────────────────────
  ///
  /// A base continua otimista para o lado forte: pode dizer "ganha em 15" onde o
  /// contador do art. 97b da mesa só permite 5, e a partida terminará empatada.
  /// O erro tem **um só sentido** — ela nunca promete empate numa posição que se
  /// perde —, e é a mesma aproximação que a consulta da raiz já aceita em
  /// produção desde a T185 parte 2a. Uma trava por contador (recusar a vitória
  /// quando `semProgresso + distancia` estoura o limite) é possível e cabe aqui,
  /// mas ela **muda lances** e por isso precisa passar pela arena antes de
  /// entrar — não é conserto de bug, é decisão de força.
  int? _consultarABase(Tabuleiro tabuleiro, int ply) {
    final base = baseDeFinais!;
    _estatisticas.consultasBase++;

    final valor = base.consultar(tabuleiro, indexador: _indexadorDaBase);
    // ⚠️ `foraDaBase` é "não sei", e `empate` é "sei, e é empate". Confundi-los
    // faria a busca declarar equilíbrio em todo ramo que a base não cobre.
    if (valor == finais.foraDaBase) return null;

    final distancia = base.distanciaDe(tabuleiro, indexador: _indexadorDaBase);

    if (valor == finais.empate) {
      // Empate com distância = empate declarado. Ver a nota longa acima.
      if (distancia != finais.semDistancia) return null;
      _estatisticas.acertosBase++;
      return 0;
    }

    if (distancia == finais.semDistancia) return null;
    _estatisticas.acertosBase++;
    return valor == finais.vitoria
        ? vitoria - ply - distancia
        : -vitoria + ply + distancia;
  }

  /// A nota da folha, do ponto de vista de quem tem a vez.
  ///
  /// **É o único lugar do motor que escolhe entre as duas avaliações.** Ter um só
  /// ponto de escolha é o que permite trocá-las na arena sem que nada mais na
  /// busca precise saber qual está valendo.
  ///
  /// A ordem dos argumentos é **diferente** entre as duas (`(tabuleiro, pesos)`
  /// na manual, `(pesos, tabuleiro)` na treinada) — herança de terem nascido em
  /// momentos diferentes, e igual no Python. Uniformizar agora quebraria os
  /// chamadores dos dois lados sem comprar nada.
  int _avaliarComRuido(Tabuleiro tabuleiro) {
    final treino = pesosTreinados;
    final nota = treino == null
        ? avaliar(tabuleiro, pesos)
        : treinada.avaliarTreinado(treino, tabuleiro);
    if (_ruido == 0) return nota;
    return nota + _aleatorio.nextInt(2 * _ruido + 1) - _ruido;
  }

  /// Põe na frente os lances com mais chance de causar corte.
  ///
  /// Ordenação **não muda a resposta** — muda quanto trabalho custa chegar nela.
  /// Com a ordem certa a poda corta cedo; com a errada o motor busca a mesma
  /// coisa e demora dezenas de vezes mais.
  void _ordenar(List<Lance> lances, Lance? lanceDaTabela) {
    lances.sort((a, b) {
      if (a == lanceDaTabela) return -1;
      if (b == lanceDaTabela) return 1;
      final pesoA = _historico[a.origem * 33 + a.destino];
      final pesoB = _historico[b.origem * 33 + b.destino];
      return pesoB - pesoA;
    });
  }

  /// A nota da posição, do ponto de vista de quem tem a vez.
  ///
  /// [semProgresso] é o contador do art. 97b: há quantos meios-lances só se
  /// movem damas, contando desde a partida de verdade e continuando pelo caminho
  /// imaginado. Ele **desce** pela recursão em vez de morar no buscador porque
  /// cada ramo tem o seu — um ramo que captura zera, o vizinho que não captura
  /// continua contando.
  ///
  /// [pecas] é quantas peças estão no tabuleiro, e desce pelo mesmo motivo — mas
  /// por uma conta muito mais barata: **uma subtração por lance**. Em damas, ou
  /// o lance não tira peça nenhuma, ou tira exatamente as que capturou; promover
  /// a dama não muda o total. Ver [contarPecas], que é chamada **uma vez por
  /// busca**, na raiz.
  ///
  /// ⚠️ **Sem esta contagem, o *probing* seria caro em vez de barato.** A busca
  /// teria de perguntar à base em todo nó só para descobrir se ela sabe de
  /// alguma coisa, e a resposta seria `foraDaBase` milhões de vezes por lance —
  /// cada uma delas varrendo as 32 casas em `codigoDaPosicao`.
  int _negamax(Tabuleiro tabuleiro, int profundidade, int alfa, int beta,
      int ply, int extensoes, int semProgresso, int semMudarEquilibrio,
      int pecas) {
    _estatisticas.nos++;

    // O teto de nós é conferido a CADA nó, e não de 2048 em 2048 como o relógio.
    // Não é capricho: se o corte caísse num múltiplo de 2048, o ponto exato de
    // parada dependeria de quantos nós a extensão de captura gastou antes, e o
    // resultado deixaria de ser idêntico entre aparelhos — que é a única razão
    // de o teto existir.
    if (_tetoDeNos >= 0 && _estatisticas.nos > _tetoDeNos) {
      throw const _NosEsgotados();
    }

    // Conferir o relógio a cada nó custaria caro; a cada 2048 basta. Aqui a
    // imprecisão é aceitável porque o relógio é rede de segurança, não critério.
    if (_prazoEmMicros >= 0 && (_estatisticas.nos & 2047) == 0) {
      if (_relogio.elapsedMicroseconds > _prazoEmMicros) {
        throw const _TempoEsgotado();
      }
    }

    final alfaOriginal = alfa;
    final hash = tabuleiro.hash;

    // --- os empates que o regulamento declara (arts. 97b e 98) --------------
    //
    // Vêm ANTES da tabela de transposição, e a ordem importa: a tabela responde
    // pela posição, e estas duas regras não dependem só da posição. Um valor
    // guardado por um caminho sem repetição diria "vantagem" numa posição que,
    // por ESTE caminho, é empate.
    //
    // Nunca na raiz (`ply == 0`): se a partida de verdade já bateu numa dessas
    // regras, quem encerra é o árbitro — e a raiz tem de devolver um lance, não
    // uma sentença.
    if (ply > 0 && usarEmpatesPorHistorico) {
      // `+ 1` porque a ocorrência atual ainda não foi contada em lugar nenhum:
      // `_noCaminho` só recebe a posição adiante, quando a recursão desce.
      final jaVistas = (_repeticoesNaPartida[hash] ?? 0) +
          (_noCaminho[hash] ?? 0) +
          1;
      if (jaVistas >= regulamento.repeticoesParaEmpate ||
          semProgresso >= _meiosLancesParaEmpate) {
        _estatisticas.empatesPorHistorico++;
        // Empate vale 0 — literalmente. E este nó **não** vai para a tabela: o
        // valor é do caminho, não da posição, e guardá-lo envenenaria toda busca
        // futura que passasse aqui por outro caminho.
        return 0;
      }

      // As duas regras da FMJD (8.3 e 8.5) precisam olhar a COMPOSIÇÃO do
      // tabuleiro, e varrer 32 casas por nó seria caro. O truque que torna isso
      // de graça: só varrer quando o relógio correspondente já passou do limite.
      // Numa abertura nenhum dos dois chega perto.
      if (_meiosLancesDaCorrelacao >= 0 &&
          semProgresso >= _meiosLancesDaCorrelacao &&
          tresDamasContraUma(tabuleiro)) {
        _estatisticas.empatesPorHistorico++;
        return 0;
      }

      if (_menorLimiteDeEquilibrio >= 0 &&
          semMudarEquilibrio >= _menorLimiteDeEquilibrio) {
        final limite = limiteDeEquilibrioParado(tabuleiro, regulamento);
        if (limite != null && semMudarEquilibrio >= limite) {
          _estatisticas.empatesPorHistorico++;
          return 0;
        }
      }
    }

    // ── A BASE DE FINAIS, DENTRO DA ÁRVORE (T185 parte 2b) ─────────────────
    //
    // Quando o ramo desce até um final que a base cobre, não há o que estimar: o
    // resultado está gravado. A busca devolve a verdade e **não desce mais**, e
    // o orçamento de nós que sobra vai para outro lugar da árvore.
    //
    // ⚠️ **Nunca na raiz** (`ply == 0`), e por um motivo que quebraria o jogo:
    // este caminho devolve uma NOTA, não um lance. Respondendo na raiz, a busca
    // terminaria sem escrever `_ttLance`, [buscar] devolveria `null` e a partida
    // travaria esperando um lance que não vem. Quem decide a raiz pela base é o
    // app, **antes** de chamar o motor (`consultarBaseDeFinais`, T185 parte 2a).
    //
    // ⚠️ **Depois dos empates do regulamento, e antes da tabela.** Depois,
    // porque os arts. 97b/98 dependem do CAMINHO e a base não o conhece: uma
    // posição que ela dá como ganha pode já estar empatada por repetição nesta
    // linha, e quem manda é a partida em curso. Antes da tabela, porque um valor
    // guardado é o que uma busca rasa achou, e a base é exata.
    //
    // ⚠️ **E o resultado NÃO vai para a tabela de transposição** — a função
    // retorna aqui mesmo. A nota carrega `ply` (a distância até o desfecho é
    // contada a partir da raiz), e a tabela guarda notas por posição, sem
    // corrigir a distância de mate. Guardá-la faria uma busca que chegasse à
    // mesma posição por outro caminho, a outra profundidade, ler uma distância
    // medida de outro lugar. Mesmo motivo pelo qual os empates por histórico,
    // logo acima, também não são guardados.
    if (baseDeFinais != null && ply > 0 && pecas <= _pecasNaBase) {
      final notaDaBase = _consultarABase(tabuleiro, ply);
      if (notaDaBase != null) return notaDaBase;
    }

    // A casa desta posição na tabela. Calculada uma vez e reusada na escrita lá
    // embaixo: `hash` não muda ao longo do nó (a busca muta o tabuleiro e o
    // desfaz, mas esta variável guarda o valor de entrada).
    final casa = hash & _mascara;
    Lance? lanceDaTabela;

    if (usarTabela && _ttChave[casa] == hash && _ttProfundidade[casa] >= 0) {
      lanceDaTabela = _ttLance[casa];
      if (_ttProfundidade[casa] >= profundidade) {
        _estatisticas.acertosNaTabela++;
        // Lidas uma vez para variável local: cada `[]` numa lista de tipo fixo
        // é uma leitura de memória com conferência de limite, e este é o
        // caminho mais quente do motor.
        final notaGuardada = _ttNota[casa];
        final marcador = _ttMarcador[casa];
        if (marcador == exato) return notaGuardada;
        if (marcador == limiteInferior) {
          alfa = alfa > notaGuardada ? alfa : notaGuardada;
        } else if (marcador == limiteSuperior) {
          beta = beta < notaGuardada ? beta : notaGuardada;
        }
        if (alfa >= beta) return notaGuardada;
      }
    }

    final lances = gerarLances(tabuleiro, regulamento);

    // Sem lance legal = derrota de quem tem a vez. O `+ ply` faz o motor
    // preferir a derrota mais LONGA e a vitória mais CURTA.
    if (lances.isEmpty) return -vitoria + ply;

    // Extensão de captura. Parar com capturas na mesa é o erro clássico: o motor
    // "vê" que ganhou uma peça e não vê que ela é retomada no lance seguinte.
    if (profundidade <= 0) {
      // `_extensaoAtiva`, e não `extensaoDeCaptura`: o nível pode desligar a
      // quiescência só para esta busca — é o que faz a Cacau parar de contar no
      // meio da troca, como um iniciante.
      if (!_extensaoAtiva ||
          !lances.first.eCaptura ||
          extensoes >= maxExtensao) {
        return _avaliarComRuido(tabuleiro);
      }
      profundidade = 1;
      extensoes++;
    }

    _ordenar(lances, lanceDaTabela);

    var melhor = -vitoria * 2;
    Lance? melhorLance;

    // A posição entra no caminho só agora, quando a recursão vai de fato descer
    // por ela. A raiz fica de fora porque já está contada no histórico da
    // partida — contá-la duas vezes faria o art. 98 disparar uma repetição cedo.
    final contaNoCaminho = ply > 0 && usarEmpatesPorHistorico;
    if (contaNoCaminho) {
      _noCaminho[hash] = (_noCaminho[hash] ?? 0) + 1;
    }

    final desfazer = _pilhaDeDesfazer[ply < 128 ? ply : 127];
    for (final lance in lances) {
      // ⚠️ Antes do `aplicarNoLugar`: aqui a busca MUTA o tabuleiro, e depois de
      // aplicado a peça já saiu da origem — a pergunta "era pedra?" só tem
      // resposta certa agora.
      final semProgressoDoFilho =
          zeraOContador(tabuleiro, lance) ? 0 : semProgresso + 1;
      // O relógio da FMJD 8.5 zera na captura e na promoção — o lance já sabe se
      // promoveu, então este não precisa consultar tabuleiro nenhum.
      final semEquilibrioDoFilho =
          mudaOEquilibrio(lance) ? 0 : semMudarEquilibrio + 1;
      aplicarNoLugar(tabuleiro, lance, desfazer);
      // `pecas - lance.quantasCapturas`: a única coisa que tira peça do
      // tabuleiro é a captura, e o lance já sabe quantas comeu.
      final nota = -_negamax(tabuleiro, profundidade - 1, -beta, -alfa, ply + 1,
          extensoes, semProgressoDoFilho, semEquilibrioDoFilho,
          pecas - lance.quantasCapturas);
      desfazerNoLugar(tabuleiro, desfazer);
      if (nota > melhor) {
        melhor = nota;
        melhorLance = lance;
      }
      if (nota > alfa) alfa = nota;
      if (alfa >= beta) {
        _estatisticas.cortes++;
        // Corte fundo vale mais que corte raso — daí o peso por profundidade².
        _historico[lance.origem * 33 + lance.destino] +=
            profundidade * profundidade;
        break;
      }
    }

    // Saindo deste ramo, a posição deixa de estar no caminho. Sem o decremento o
    // contador só cresceria, e a busca declararia empate por repetição em ramos
    // que nunca repetiram nada — o motor jogaria para o empate desde a abertura.
    if (contaNoCaminho) {
      _noCaminho[hash] = _noCaminho[hash]! - 1;
    }

    // Substituição sempre: o registro novo sobrescreve o que estava na casa.
    _ttChave[casa] = hash;
    _ttProfundidade[casa] = profundidade;
    _ttNota[casa] = melhor;
    _ttMarcador[casa] = melhor <= alfaOriginal
        ? limiteSuperior
        : (melhor >= beta ? limiteInferior : exato);
    _ttLance[casa] = melhorLance;

    return melhor;
  }

  List<Lance> _variantePrincipal(Tabuleiro tabuleiro, {int limite = 12}) {
    final linha = <Lance>[];
    final vistas = <int>{};
    var atual = tabuleiro;
    for (var i = 0; i < limite; i++) {
      final hash = atual.hash;
      if (!vistas.add(hash)) break; // a linha entrou em ciclo
      final casa = hash & _mascara;
      final lance = _ttLance[casa];
      if (_ttChave[casa] != hash || lance == null) break;
      linha.add(lance);
      atual = aplicarLance(atual, lance);
    }
    return linha;
  }

  /// Procura o melhor lance, aprofundando um nível de cada vez.
  ///
  /// **Aprofundamento iterativo:** parece desperdício refazer tudo a cada nível,
  /// e não é — a árvore cresce tão rápido que o último nível domina o custo, e
  /// cada rodada deixa na tabela a ordenação que faz a seguinte podar melhor. De
  /// quebra, é o que permite ter uma resposta pronta a qualquer instante, que é
  /// o que torna o orçamento por tempo possível.
  ///
  /// Ao estourar o orçamento devolve-se o resultado da **última profundidade que
  /// terminou inteira** — uma varredura pela metade é pior que a anterior
  /// completa.
  ///
  /// [tetoDeNos] é o orçamento em **posições visitadas**, o critério que faz o
  /// mesmo nível jogar igual em qualquer aparelho; [tempoMaximo] é rede de
  /// segurança.
  ///
  /// [historico] é o que a partida já acumulou — posições repetidas e o contador
  /// do art. 97b. Sem ele o motor busca como se a posição tivesse acabado de
  /// surgir do nada, e **não enxerga** que mais uma volta no mesmo ciclo encerra
  /// o jogo empatado. Quem joga partida de verdade deve sempre passá-lo; quem
  /// analisa uma posição solta pode omitir.
  /// Todos os lances da raiz com a nota de cada um, do melhor para o pior.
  ///
  /// Por que isto existe, se o negamax já devolve o melhor lance: porque ele
  /// devolve **só** o melhor. A alfa-beta corta assim que sabe que um lance não
  /// vence o campeão atual, e o que sobra dos outros é um limite superior, não
  /// uma nota comparável. Para escolher entre os candidatos é preciso buscar
  /// cada um com **janela cheia**, sem deixar um irmão podar o outro.
  ///
  /// Custa mais nós que a busca normal — e é custo aceitável porque este caminho
  /// só roda quando `chanceDeErrar > 0`, ou seja, nos níveis fracos, onde gastar
  /// orçamento e chegar menos fundo é o objetivo. Tex e Sagaz seguem pelo
  /// caminho de sempre, **nó por nó idênticos** ao de antes de 2026-08-14 — o
  /// que preserva a impressão digital que a bancada compara entre aparelhos.
  List<(int, Lance)> _raizComNotas(Tabuleiro tabuleiro, int profundidade,
      int semProgresso, int semEquilibrio, int pecas) {
    final avaliados = <(int, Lance)>[];
    final desfazer = _pilhaDeDesfazer[0];
    for (final lance in gerarLances(tabuleiro, regulamento)) {
      // Antes do `aplicarNoLugar`: depois de aplicado a peça já saiu da origem,
      // e "era pedra?" deixaria de ter resposta certa.
      final semProgressoDoFilho =
          zeraOContador(tabuleiro, lance) ? 0 : semProgresso + 1;
      final semEquilibrioDoFilho =
          mudaOEquilibrio(lance) ? 0 : semEquilibrio + 1;
      aplicarNoLugar(tabuleiro, lance, desfazer);
      final nota = -_negamax(tabuleiro, profundidade - 1, -vitoria * 2,
          vitoria * 2, 1, 0, semProgressoDoFilho, semEquilibrioDoFilho,
          pecas - lance.quantasCapturas);
      desfazerNoLugar(tabuleiro, desfazer);
      avaliados.add((nota, lance));
    }
    // `sort` do Dart NÃO é estável, ao contrário do Python. Para a partida com
    // semente fixa se repetir lance a lance, o desempate precisa ser explícito —
    // daí comparar origem e destino quando as notas empatam.
    avaliados.sort((a, b) {
      if (a.$1 != b.$1) return b.$1 - a.$1;
      if (a.$2.origem != b.$2.origem) return a.$2.origem - b.$2.origem;
      return a.$2.destino - b.$2.destino;
    });
    return avaliados;
  }

  /// O lance que o nível fraco vai jogar: o melhor, ou um dos aceitáveis.
  ///
  /// O erro é sorteado **entre os lances dentro da margem**, e não entre todos.
  /// É essa restrição que separa "adversário fraco" de "adversário quebrado":
  /// um lance que entrega uma dama, ou que entra numa perda forçada, nunca entra
  /// no sorteio, por mais alta que seja a chance de errar.
  (int, Lance) _escolherErrando(List<(int, Lance)> avaliados) {
    final melhor = avaliados.first;
    if (avaliados.length == 1) return melhor;
    if (_aleatorio.nextDouble() >= _chanceDeErrar) return melhor;

    // `avaliados` já vem ordenado, então basta ficar com os que perdem no
    // máximo `_margemDoErro` para o melhor. O índice 0 sempre cabe.
    final limite = melhor.$1 - _margemDoErro;
    final aceitaveis =
        avaliados.where((par) => par.$1 >= limite).toList(growable: false);
    if (aceitaveis.length == 1) return melhor;
    // O melhor sai do sorteio: mantê-lo dentro faria a chance efetiva de errar
    // ser menor que a pedida, e de um jeito que varia com quantos lances a
    // posição tem — ou seja, incalibrável.
    return aceitaveis[1 + _aleatorio.nextInt(aceitaveis.length - 1)];
  }

  Resultado buscar(Tabuleiro tabuleiro,
      {int profundidade = 8,
      int? tetoDeNos,
      double? tempoMaximo,
      int ruido = 0,
      HistoricoDaPartida? historico,
      bool? extensaoDeCaptura,
      double chanceDeErrar = 0,
      int margemDoErro = margemDoErroPadrao}) {
    _estatisticas = Estatisticas();
    _ruido = ruido;
    _extensaoAtiva = extensaoDeCaptura ?? this.extensaoDeCaptura;
    _chanceDeErrar = chanceDeErrar;
    _margemDoErro = margemDoErro;
    _tetoDeNos = -1;

    // O histórico é lido, nunca alterado — a busca imagina lances, não os joga.
    _repeticoesNaPartida = historico?.repeticoes ?? const {};
    final semProgressoInicial = historico?.meiosLancesSemProgresso ?? 0;
    final semEquilibrioInicial =
        historico?.meiosLancesSemMudarOEquilibrio ?? 0;
    _relogio
      ..reset()
      ..start();
    _prazoEmMicros =
        tempoMaximo == null ? -1 : (tempoMaximo * 1000000).round();

    // A busca MUTA o tabuleiro (make/unmake) e o devolve ao estado original ao
    // fim de cada ramo. Ainda assim trabalhamos numa cópia: quem chama não deve
    // precisar confiar nisso, e uma exceção de tempo esgotado no meio da
    // recursão deixaria o original a meio caminho.
    final trabalho = tabuleiro.clonar();

    // As 32 casas varridas **uma vez por busca**. Daqui para baixo a contagem
    // desce pela recursão por subtração — ver [_negamax].
    final pecasNaRaiz = contarPecas(trabalho);

    var melhor = Resultado(null, 0, const [], _estatisticas);

    for (var nivelDeProfundidade = 1;
        nivelDeProfundidade <= profundidade;
        nivelDeProfundidade++) {
      // A profundidade 1 nunca é interrompida: é ela que garante que existe
      // ALGUM lance para devolver. Teto minúsculo tem de produzir motor fraco,
      // nunca motor que não joga — `null` chegando na interface trava a partida.
      _tetoDeNos = nivelDeProfundidade == 1 ? -1 : (tetoDeNos ?? -1);

      // Zerado a cada profundidade porque uma varredura interrompida pelo
      // orçamento sobe por exceção, sem passar pelos decrementos do laço — e
      // deixaria posições marcadas como "no caminho" para sempre.
      _noCaminho.clear();

      int nota;
      Lance? lance;
      try {
        if (chanceDeErrar > 0) {
          // Caminho dos níveis fracos: avalia cada lance da raiz com janela
          // cheia para poder escolher entre os candidatos aceitáveis.
          final avaliados = _raizComNotas(trabalho, nivelDeProfundidade,
              semProgressoInicial, semEquilibrioInicial, pecasNaRaiz);
          (nota, lance) = _escolherErrando(avaliados);
          // A raiz é gravada com o lance ESCOLHIDO, não com o melhor. Sem isto
          // a variante principal começaria por um lance que o motor não vai
          // jogar, e o relatório da partida mentiria sobre o que ele pensou.
          final casaDaRaiz = tabuleiro.hash & _mascara;
          _ttChave[casaDaRaiz] = tabuleiro.hash;
          _ttProfundidade[casaDaRaiz] = nivelDeProfundidade;
          _ttNota[casaDaRaiz] = nota;
          _ttMarcador[casaDaRaiz] = exato;
          _ttLance[casaDaRaiz] = lance;
        } else {
          nota = _negamax(trabalho, nivelDeProfundidade, -vitoria * 2,
              vitoria * 2, 0, 0, semProgressoInicial, semEquilibrioInicial,
              pecasNaRaiz);
          lance = _ttLance[tabuleiro.hash & _mascara];
        }
      } on _NosEsgotados {
        _estatisticas.motivoDaParada = 'nos';
        break;
      } on _TempoEsgotado {
        _estatisticas.motivoDaParada = 'tempo';
        break;
      }

      melhor = Resultado(
          lance, nota, _variantePrincipal(tabuleiro), _estatisticas);
      _estatisticas.profundidadeAtingida = nivelDeProfundidade;

      // Vitória ou derrota forçada: aprofundar não muda mais nada.
      if (nota.abs() > vitoria - 1000) {
        _estatisticas.motivoDaParada = 'decidido';
        break;
      }
    }

    _relogio.stop();
    _estatisticas.tempoSegundos = _relogio.elapsedMicroseconds / 1e6;
    return melhor;
  }

  /// Escolhe o lance com o orçamento de um nível de dificuldade.
  ///
  /// ⚠️ **O nível manda em tudo o que ele define** — inclusive na quiescência.
  /// Um [Buscador] construído com `extensaoDeCaptura: false` volta a tê-la
  /// ligada aqui se o nível a pede, porque "jogar como a Pita" tem de significar
  /// a mesma coisa em qualquer buscador. Quem quer as chaves do construtor
  /// valendo chama [buscar] diretamente.
  Resultado jogar(Tabuleiro tabuleiro, Nivel nivel,
          {HistoricoDaPartida? historico}) =>
      buscar(
        tabuleiro,
        profundidade: nivel.profundidade,
        tetoDeNos: nivel.tetoDeNos,
        tempoMaximo: nivel.tempoMaximo,
        ruido: nivel.ruido,
        historico: historico,
        extensaoDeCaptura: nivel.extensaoDeCaptura,
        chanceDeErrar: nivel.chanceDeErrar,
        margemDoErro: nivel.margemDoErro,
      );
}

/// Quantas peças estão no tabuleiro, varrendo as 32 casas.
///
/// ⚠️ **Chamada uma vez por busca, na raiz** — nunca dentro da árvore. Lá a
/// contagem desce por subtração (`pecas - lance.quantasCapturas`), porque a
/// única coisa que tira peça do tabuleiro é a captura, e o lance já sabe
/// quantas comeu. Coroar uma pedra troca o **tipo** da peça, não o total.
///
/// É pública porque a bancada e os testes precisam do mesmo número para conferir
/// que a subtração da recursão não se descolou da verdade.
int contarPecas(Tabuleiro tabuleiro) {
  var total = 0;
  // As casas jogáveis são numeradas de 1 a 32 — daí o laço não começar em zero.
  for (var casa = 1; casa <= nCasas; casa++) {
    if (tabuleiro.ler(casa) != vazia) total++;
  }
  return total;
}
