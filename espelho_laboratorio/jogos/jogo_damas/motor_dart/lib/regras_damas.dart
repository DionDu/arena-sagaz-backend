/// Gerador de lances em Dart — o que vai rodar no celular.
///
/// Port de `../motor/regras_damas.py`, linha a linha. As decisões de regra
/// **não são tomadas aqui**: elas vivem no motor de referência em Python, que é
/// conferido contra o texto normativo e contra o `perft` publicado. Este arquivo
/// só precisa concordar com aquele.
///
/// Se um dia os dois discordarem, o Python está certo até prova em contrário —
/// é ele que tem a especificação escrita separada do código e a bateria de
/// testes por cláusula.
library;

import 'tabuleiro_damas.dart';

// ---------------------------------------------------------------------------
// O regulamento como parâmetro
// ---------------------------------------------------------------------------

/// As regras que mudam de uma variante de damas para outra.
///
/// Cada campo é uma pergunta cuja resposta muda o jogo. Ver a documentação
/// completa de cada uma em `../motor/regras_damas.py`.
class Regulamento {
  final String identificador;
  final String nome;

  /// A dama percorre a diagonal inteira (brasileiras) ou anda uma casa (anglo)?
  final bool damaVoa;

  /// A pedra pode capturar de recuo? Brasileiras sim, anglo não.
  final bool pedraCapturaParaTras;

  /// A Lei da Maioria. Brasileiras sim; nas anglo basta capturar.
  final bool capturaMaximaObrigatoria;

  /// A **Lei da Qualidade**, que só as portuguesas/espanholas têm (FPD 3.7.b):
  /// entre capturas de mesmo número, é obrigatória a que toma a peça de melhor
  /// qualidade — dama antes de pedra.
  ///
  /// Conta o que **sai** do tabuleiro, não quem captura (FPD 3.7.e).
  final bool desempatePorQualidade;

  /// Nas anglo, a pedra que pisa a coroação para ali, coroada, mesmo havendo
  /// mais capturas. Nas brasileiras ela atravessa e continua como pedra.
  final bool coroacaoEncerraOLance;

  /// Brancas nas brasileiras, pretas nas anglo-americanas.
  final int quemComeca;

  /// Quantos lances **de cada jogador** sem progresso encerram a partida
  /// empatada: art. 97b nas brasileiras (20), WCDF 1.27.2 nas anglo-americanas
  /// (**40**, o dobro).
  ///
  /// ⚠️ Era constante global até 2026-07-28, e por isso o motor aplicava a regra
  /// brasileira em partida anglo-americana. Nenhum `perft` pegaria: regra de
  /// empate não muda a contagem de lances legais.
  final int lancesSemProgressoParaEmpate;

  /// Quantas ocorrências da mesma posição empatam. Três nas duas famílias (art.
  /// 98; WCDF 1.27.1) — parametrizado assim mesmo, porque a coincidência de hoje
  /// não é garantia de amanhã.
  final int repeticoesParaEmpate;

  /// FMJD 8.3 — três damas **ou mais** contra uma dama solitária: empate se o
  /// lado forte não capturar em tantos lances. `null` desliga a regra.
  ///
  /// Ao contrário do art. 100 do CBJD, **não** exige a grande diagonal.
  final int? lancesTresDamasContraUma;

  /// FMJD 8.5 — os dois lados com damas e o equilíbrio sem mudar (sem captura e
  /// sem promoção): empate depois de tantos lances.
  ///
  /// Cada item é `[mínimo de peças, máximo de peças, lances]`.
  ///
  /// ⚠️ O contador desta regra **não é o do art. 97b**: lá mover pedra zera,
  /// aqui não. São dois relógios diferentes correndo juntos.
  final List<List<int>> lancesEquilibrioParado;

  /// O mesmo limite em **meios-lances**, que é como a busca desce a árvore.
  ///
  /// A conversão fica num lugar só: o erro de fator 2 é fácil de cometer e
  /// difícil de notar — faz a regra disparar com metade ou o dobro dos lances, e
  /// a partida continua "parecendo" normal.
  int get meiosLancesSemProgressoParaEmpate => 2 * lancesSemProgressoParaEmpate;

  /// Se este regulamento reproduz o **texto normativo** de uma federação.
  ///
  /// O `false` existe para uma coisa só, e é melhor que exista a que uma
  /// variante de casa se disfarce de oficial: a [damasDeCasa] é uma
  /// simplificação que *nós* definimos, para o jeito como a maioria das pessoas
  /// joga em casa. Qualquer tela ou relatório pode consultar este campo para não
  /// apresentá-la como se fosse regra de federação.
  final bool oficial;

  /// Se os arts. 99 e 100 entram na **base de finais** — empates que o
  /// regulamento declara pela posição, sem contar lance nenhum.
  ///
  /// Até 2026-07-29 isto não era um campo: a retrógrada perguntava
  /// `identificador == 'brasileira'`. Funcionava enquanto só as brasileiras os
  /// tinham, e quebraria calado no instante em que a [damasDeCasa] entrou — ela
  /// tem os mesmos empates declarados e receberia uma base **sem** eles, ou
  /// seja, uma base que aponta vitória onde a modalidade manda empatar.
  final bool empatesDeclaradosPorPosicao;

  /// Como citar a regra da posição repetida no motivo do fim da partida.
  ///
  /// Vai para o registro da partida, que outro programa vai ler — citar o artigo
  /// brasileiro numa partida anglo-americana é registro errado. Cada regulamento
  /// declara o seu em vez de haver um `if` por identificador em algum canto.
  final String artigoDaRepeticao;

  /// Idem, para a regra dos lances sem progresso.
  final String artigoDosLancesSemProgresso;

  /// FPD 3.8.b.(1) — **quando** o relógio dos lances sem progresso começa a andar.
  ///
  /// A diferença entre o regulamento português e o brasileiro é de *gatilho*, não
  /// de número: os dois dão 20 lances, mas o brasileiro conta desde o primeiro e o
  /// português só depois que a posição vira final de no máximo quatro peças por
  /// lado, com dama dos dois lados.
  ///
  /// `null` (o padrão) quer dizer "sem gatilho, conta sempre".
  ///
  /// ⚠️ Fora do gatilho o contador **zera**, não fica só parado: o texto diz que
  /// a contagem *começa* quando a posição surge.
  final int? maximoDePecasPorLadoParaContar;

  /// A outra metade do gatilho da FPD 3.8.b.(1): dama de **cada** lado.
  final bool exigeDamaDosDoisLadosParaContar;

  /// FPD 3.8.a — a **«Forçada»**: três damas que ocupam o Rio contra uma dama
  /// solitária têm 12 lances para liquidá-la. `null` desliga a regra.
  ///
  /// O Rio é a grande diagonal ([rio], em `tabuleiro_damas.dart`), e a definição
  /// dele não está no texto do regulamento: está numa figura da página 7.
  ///
  /// Duas leituras que o texto não fecha, e que este motor assume:
  /// - **"12 moves" são 12 lances do lado forte**, não 12 de cada lado (o art.
  ///   3.8.b diz "for each color" quando quer dizer os dois lados; aqui não diz);
  /// - **começada, a contagem não reinicia** se o forte sair do Rio — reiniciar
  ///   seria uma brecha: bastaria sair e voltar para ganhar mais doze lances.
  final int? lancesDaForcada;

  /// Como citar a Forçada no motivo do fim da partida.
  final String artigoDaForcada;

  /// Quantas damas o lado forte tem na Forçada. É 3 no texto português.
  final int damasDaForcada;

  const Regulamento({
    required this.identificador,
    required this.nome,
    required this.damaVoa,
    required this.pedraCapturaParaTras,
    required this.capturaMaximaObrigatoria,
    required this.coroacaoEncerraOLance,
    required this.quemComeca,
    this.oficial = true,
    this.empatesDeclaradosPorPosicao = false,
    this.artigoDaRepeticao = 'art. 98',
    this.artigoDosLancesSemProgresso = 'art. 97b',
    this.desempatePorQualidade = false,
    this.lancesSemProgressoParaEmpate = 20,
    this.repeticoesParaEmpate = 3,
    this.lancesTresDamasContraUma,
    this.lancesEquilibrioParado = const [],
    this.maximoDePecasPorLadoParaContar,
    this.exigeDamaDosDoisLadosParaContar = false,
    this.lancesDaForcada,
    this.artigoDaForcada = 'FPD 3.8.a',
    this.damasDaForcada = 3,
  });
}

/// O regulamento brasileiro, conferido contra o texto normativo do CBJD
/// (`../../referencias/texto/12_regras_oficiais_cbjd.md`).
const Regulamento brasileiras = Regulamento(
  identificador: 'brasileira',
  nome: 'damas brasileiras',
  damaVoa: true,
  pedraCapturaParaTras: true,
  capturaMaximaObrigatoria: true,
  coroacaoEncerraOLance: false,
  quemComeca: brancas,
  lancesSemProgressoParaEmpate: 20, // art. 97b
  repeticoesParaEmpate: 3, // art. 98
  // As duas regras da FMJD-64 que o CBJD não contradiz — apenas omite, por o
  // extrato que temos ter só 6 páginas. Decisão do dono em 2026-07-28.
  lancesTresDamasContraUma: 15, // FMJD 8.3
  lancesEquilibrioParado: [
    [4, 5, 30], // FMJD 8.5 — finais de 4 e 5 peças
    [6, 7, 60], // FMJD 8.5 — finais de 6 e 7 peças
  ],
  // Arts. 99 e 100: empates declarados pela POSIÇÃO. Não entram na busca —
  // moram dentro da base de finais.
  empatesDeclaradosPorPosicao: true,
  artigoDaRepeticao: 'art. 98',
  artigoDosLancesSemProgresso: 'art. 97b',
);

/// O regulamento anglo-americano, conferido em 2026-07-28 contra as *Revised
/// Rules of Draughts* do WCDF (`../../referencias/texto/13_regras_wcdf_anglo.md`),
/// publicadas pela ACF — que remete a elas as regras de jogo.
///
/// Os quatro parâmetros de jogo já estavam certos (o `perft` contra gabarito
/// publicado sugeria isso). As regras de **empate**, não: o limite é o dobro do
/// brasileiro, e nenhum `perft` pegaria a diferença.
const Regulamento angloAmericanas = Regulamento(
  identificador: 'anglo',
  nome: 'damas anglo-americanas (checkers)',
  damaVoa: false, // WCDF 1.17 — a dama anda UMA casa
  pedraCapturaParaTras: false, // WCDF 1.18 e 1.25
  capturaMaximaObrigatoria: false, // WCDF 1.20 — sem Lei da Maioria
  coroacaoEncerraOLance: true, // WCDF 1.19
  quemComeca: pretas, // WCDF 1.14 — as vermelhas, que são as escuras
  lancesSemProgressoParaEmpate: 40, // WCDF 1.27.2 — o DOBRO do art. 97b
  repeticoesParaEmpate: 3, // WCDF 1.27.1
  // O WCDF não tem equivalente aos arts. 99/100.
  empatesDeclaradosPorPosicao: false,
  artigoDaRepeticao: 'WCDF 1.27.1',
  artigoDosLancesSemProgresso: 'WCDF 1.27.2',
);

/// As damas portuguesas (espanholas) — a **terceira família**, e não uma
/// variação de nenhuma das outras duas.
///
/// Fonte: *Rules of Portuguese Draughts (Spanish Draughts)*, Federação
/// Portuguesa de Damas, em vigor desde 01/04/2026
/// (`../../referencias/texto/16_regras_portuguesas_espanholas_fmjd.md`).
///
/// |                  | dama voa | recuo | coroação encerra | maioria | qualidade |
/// |------------------|----------|-------|------------------|---------|-----------|
/// | brasileiras      | ✔        | ✔     | ✘                | ✔       | ✘         |
/// | anglo-americanas | ✘        | ✘     | ✔                | ✘       | ✘         |
/// | portuguesas      | ✔        | ✘     | ✔                | ✔       | **✔**     |
///
/// Desde 2026-07-29 este regulamento está **completo**: as duas regras de empate
/// próprias dele — o gatilho da regra dos 20 lances (3.8.b) e a "Forçada"
/// (3.8.a) — entraram junto com a descoberta de que o "Rio" é a mesma grande
/// diagonal que o motor já conhecia. Ver `docs/imagens/60_o_rio_e_a_forcada.png`.
const Regulamento portuguesas = Regulamento(
  identificador: 'portuguesa',
  nome: 'damas portuguesas (espanholas)',
  damaVoa: true, // FPD 3.2.a
  pedraCapturaParaTras: false, // FPD 3.4.a — "directly in front of it"
  capturaMaximaObrigatoria: true, // FPD 3.7.a — regra da quantidade
  coroacaoEncerraOLance: true, // FPD 3.1.e
  desempatePorQualidade: true, // FPD 3.7.b — só aqui
  quemComeca: brancas,
  lancesSemProgressoParaEmpate: 20, // FPD 3.8.b — o número bate com o brasileiro…
  // …mas o GATILHO não: lá conta sempre, aqui só depois que a posição vira final
  // de no máximo 4 peças por lado com dama dos dois lados (3.8.b.1).
  maximoDePecasPorLadoParaContar: 4,
  exigeDamaDosDoisLadosParaContar: true,
  lancesDaForcada: 12, // FPD 3.8.a — três damas no Rio × uma dama
  damasDaForcada: 3,
  artigoDaForcada: 'FPD 3.8.a',
  repeticoesParaEmpate: 3, // FPD 5.3
  // Os arts. 99/100 do CBJD não têm equivalente aqui. O que a FPD tem no lugar é
  // a Forçada, que **não** é empate declarado por posição: é um relógio, e por
  // isso mora no histórico da partida, não na base de finais.
  empatesDeclaradosPorPosicao: false,
  artigoDaRepeticao: 'FPD 5.3',
  artigoDosLancesSemProgresso: 'FPD 3.8.b',
);

/// **A quarta modalidade, e a única que não vem de federação nenhuma.**
///
/// Comer continua obrigatório — quem pode comer, come. O que sai é a obrigação
/// de comer o **maior número**: havendo duas capturas possíveis, o jogador
/// escolhe.
///
/// Por que ela existe: o público principal do app não são damistas, são pessoas
/// comuns *(diretriz do dono, 2026-07-28)*, e muita gente no Brasil aprendeu
/// damas em casa sem a Lei da Maioria. Para essa pessoa, escolher "Damas
/// Brasileiras" e ter o lance travado por uma regra que ela não sabe que existe
/// é **indistinguível de bug**. A saída não é afrouxar o regulamento oficial — é
/// oferecer ao lado dele a variante que ela já conhece, com nome honesto.
///
/// O que muda no motor: **um campo**. Tudo o mais é idêntico às brasileiras, e
/// isso é de propósito.
///
/// O `perft` é a assinatura da diferença: idêntico ao brasileiro até a
/// profundidade 4 e maior da 5 em diante, que é onde a Lei da Maioria começa a
/// cortar capturas menores.
const Regulamento damasDeCasa = Regulamento(
  identificador: 'casa',
  nome: 'damas de casa',
  // Tudo igual às brasileiras…
  damaVoa: true,
  pedraCapturaParaTras: true,
  coroacaoEncerraOLance: false,
  quemComeca: brancas,
  lancesSemProgressoParaEmpate: 20,
  repeticoesParaEmpate: 3,
  lancesTresDamasContraUma: 15,
  lancesEquilibrioParado: [
    [4, 5, 30],
    [6, 7, 60],
  ],
  empatesDeclaradosPorPosicao: true,
  artigoDaRepeticao: 'art. 98',
  artigoDosLancesSemProgresso: 'art. 97b',
  // …menos ISTO, que é a variante inteira: sem a Lei da Maioria.
  capturaMaximaObrigatoria: false,
  oficial: false,
);

// ---------------------------------------------------------------------------
// O lance
// ---------------------------------------------------------------------------

/// Um lance legal: por onde a peça andou e o que ela tirou do tabuleiro.
///
/// Guarda o caminho inteiro porque, numa captura de dama, o destino não é
/// determinado pela peça tomada — e sem o caminho não dá para detectar a Casa
/// Cruz nem desenhar a sequência.
class Lance {
  final List<int> caminho;
  final List<int> capturadas;
  final bool viraDama;

  const Lance(this.caminho, this.capturadas, {this.viraDama = false});

  int get origem => caminho.first;
  int get destino => caminho.last;
  bool get eCaptura => capturadas.isNotEmpty;
  int get quantasCapturas => capturadas.length;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    if (other is! Lance) return false;
    if (caminho.length != other.caminho.length) return false;
    for (var i = 0; i < caminho.length; i++) {
      if (caminho[i] != other.caminho[i]) return false;
    }
    return true;
  }

  @override
  int get hashCode {
    var hash = 0;
    for (var i = 0; i < caminho.length; i++) {
      hash ^= caminho[i] << (i * 5);
    }
    return hash;
  }

  /// Notação legível: `23-18` para lance simples, `30x23x16` para captura.
  @override
  String toString() => caminho.join(eCaptura ? 'x' : '-');
}

// ---------------------------------------------------------------------------
// Geração
// ---------------------------------------------------------------------------

const List<int> _todasAsDirecoes = [
  cimaEsquerda,
  cimaDireita,
  baixoEsquerda,
  baixoDireita,
];

/// Esta casa está livre para a peça passar ou pousar?
///
/// Normalmente é a leitura crua do tabuleiro. A exceção é o **interruptor de
/// diagnóstico** [condenadasBloqueiam]: com ele desligado, uma peça já tomada
/// neste lance conta como casa vazia — o que produz os lances que existiriam se
/// ela saísse do tabuleiro no instante do salto, em vez de ficar até o fim
/// (art. 15). Ninguém joga assim; quem usa isso é
/// `explicacao_de_recusa_damas.dart`, para poder dizer ao jogador *"este caminho
/// só está fechado por causa da peça que você acabou de comer"*.
///
/// `@pragma('vm:prefer-inline')` pede à VM que costure esta função no lugar da
/// chamada. Ela está no caminho mais quente do motor — a geração de capturas
/// roda milhões de vezes por busca —, e uma chamada de função por casa
/// examinada apareceria na medição.
@pragma('vm:prefer-inline')
bool _livreParaPassar(
  Tabuleiro trabalho,
  int casa,
  int mascaraCapturadas,
  bool condenadasBloqueiam,
) {
  if (trabalho.ler(casa) == vazia) return true;
  return !condenadasBloqueiam && ((mascaraCapturadas >> casa) & 1) != 0;
}

/// Percorre em profundidade todas as continuações de uma captura.
///
/// Só acrescenta a [encontrados] uma sequência que **não pode mais ser
/// estendida** — nunca um prefixo. Parar no meio de uma cadeia não é lance legal
/// em nenhuma das duas famílias; o que muda entre elas é apenas se, entre as
/// cadeias completas, é obrigatório escolher a maior.
///
/// [pecaEDama] **não muda durante a recursão**: é a tradução literal da regra de
/// que a pedra que atravessa a casa de coroação continua pedra até o fim do
/// lance, e portanto continua saltando como pedra.
void _explorarCapturas(
  Tabuleiro trabalho,
  Regulamento regulamento,
  int cor,
  int posicao,
  bool pecaEDama,
  List<int> caminho,
  List<int> capturadas,
  // As mesmas casas de `capturadas`, como bits de um inteiro. Existe em
  // duplicata de propósito: perguntar "já capturei esta?" é a operação mais
  // frequente da geração, e uma varredura da lista aparecia na medição. A lista
  // continua porque a ORDEM importa para montar o `Lance`.
  int mascaraCapturadas,
  List<Lance> encontrados,
  // Ver [_livreParaPassar]. `true` é a regra; `false` só existe para a
  // explicação de recusa descobrir o que o art. 15 barrou.
  bool condenadasBloqueiam,
) {
  // Nas anglo a pedra que pisa a coroação para ali, coroada.
  if (regulamento.coroacaoEncerraOLance &&
      !pecaEDama &&
      caminho.length > 1 &&
      casasDeCoroacao[cor].contains(posicao)) {
    encontrados.add(Lance(List.of(caminho), List.of(capturadas), viraDama: true));
    return;
  }

  var achouSalto = false;

  // A dama sempre captura nos quatro lados; a pedra depende do regulamento.
  final direcoes = (pecaEDama || regulamento.pedraCapturaParaTras)
      ? _todasAsDirecoes
      : direcoesDeAvanco[cor];

  for (final direcao in direcoes) {
    if (pecaEDama && regulamento.damaVoa) {
      // --- dama voadora: desliza até achar a primeira peça ------------------
      final diagonal = raio(posicao, direcao);
      var indice = 0;
      while (indice < diagonal.length &&
          _livreParaPassar(trabalho, diagonal[indice], mascaraCapturadas,
              condenadasBloqueiam)) {
        indice++;
      }
      if (indice == diagonal.length) continue; // só casa vazia até a borda

      final vitima = diagonal[indice];
      if (corDaPeca(trabalho.ler(vitima)) == cor) continue; // peça nossa
      // Já tomada neste lance: não pode ser tomada de novo E continua ocupando
      // a casa, logo fecha a diagonal. É o Tema Turco, sem código especial.
      if ((mascaraCapturadas >> vitima) & 1 != 0) continue;

      // Todas as casas livres depois da vítima são paradas possíveis.
      var pouso = indice + 1;
      while (pouso < diagonal.length &&
          _livreParaPassar(trabalho, diagonal[pouso], mascaraCapturadas,
              condenadasBloqueiam)) {
        achouSalto = true;
        caminho.add(diagonal[pouso]);
        capturadas.add(vitima);
        _explorarCapturas(
            trabalho,
            regulamento,
            cor,
            diagonal[pouso],
            pecaEDama,
            caminho,
            capturadas,
            mascaraCapturadas | (1 << vitima),
            encontrados,
            condenadasBloqueiam);
        caminho.removeLast();
        capturadas.removeLast();
        pouso++;
      }
    } else {
      // --- pedra, ou dama curta: salto de exatamente duas casas -------------
      final vitima = vizinho(posicao, direcao);
      if (vitima == 0 ||
          _livreParaPassar(
              trabalho, vitima, mascaraCapturadas, condenadasBloqueiam)) {
        continue;
      }
      if (corDaPeca(trabalho.ler(vitima)) == cor) continue;
      if ((mascaraCapturadas >> vitima) & 1 != 0) continue;
      final destino = vizinho(vitima, direcao);
      if (destino == 0 ||
          !_livreParaPassar(
              trabalho, destino, mascaraCapturadas, condenadasBloqueiam)) {
        continue;
      }

      achouSalto = true;
      caminho.add(destino);
      capturadas.add(vitima);
      _explorarCapturas(
          trabalho,
          regulamento,
          cor,
          destino,
          pecaEDama,
          caminho,
          capturadas,
          mascaraCapturadas | (1 << vitima),
          encontrados,
          condenadasBloqueiam);
      caminho.removeLast();
      capturadas.removeLast();
    }
  }

  if (!achouSalto && caminho.length > 1) {
    encontrados.add(Lance(
      List.of(caminho),
      List.of(capturadas),
      // A promoção olha ONDE O LANCE TERMINOU, e só aqui.
      viraDama: !pecaEDama && casasDeCoroacao[cor].contains(posicao),
    ));
  }
}

/// Todas as sequências de captura completas de quem tem a vez, sem filtrar.
///
/// **Não clona o tabuleiro.** A versão anterior fazia uma cópia por peça — doze
/// cópias por nó no começo de partida — e isso dominava o custo da geração.
/// Aqui a peça é retirada do próprio tabuleiro e reposta logo depois: o efeito é
/// o mesmo (a casa de origem fica livre, que é o que permite a Casa Cruz) e não
/// se aloca nada.
List<Lance> gerarCapturas(
  Tabuleiro tabuleiro,
  Regulamento regulamento, {
  /// **Deixe no padrão.** Ver [_livreParaPassar]: desligado, este parâmetro
  /// produz lances que o regulamento não permite, e serve só para a explicação
  /// de recusa saber o que o art. 15 barrou.
  bool condenadasBloqueiam = true,
}) {
  final cor = tabuleiro.vez;
  final encontrados = <Lance>[];

  for (var origem = 1; origem <= nCasas; origem++) {
    final peca = tabuleiro.ler(origem);
    if (peca == vazia || corDaPeca(peca) != cor) continue;

    tabuleiro.escrever(origem, vazia);
    _explorarCapturas(tabuleiro, regulamento, cor, origem, eDama(peca), [origem],
        <int>[], 0, encontrados, condenadasBloqueiam);
    tabuleiro.escrever(origem, peca);
  }
  return encontrados;
}

/// Os lances sem captura. Só valem quando não há captura alguma disponível.
List<Lance> gerarLancesSimples(Tabuleiro tabuleiro, Regulamento regulamento) {
  final cor = tabuleiro.vez;
  final lances = <Lance>[];

  for (var origem = 1; origem <= nCasas; origem++) {
    final peca = tabuleiro.ler(origem);
    if (peca == vazia || corDaPeca(peca) != cor) continue;
    final pecaEDama = eDama(peca);
    final direcoes = pecaEDama ? _todasAsDirecoes : direcoesDeAvanco[cor];

    for (final direcao in direcoes) {
      if (pecaEDama && regulamento.damaVoa) {
        // "quantas casas quiser dentro da mesma diagonal", até esbarrar.
        for (final destino in raio(origem, direcao)) {
          if (tabuleiro.ler(destino) != vazia) break;
          lances.add(Lance([origem, destino], const []));
        }
      } else {
        final destino = vizinho(origem, direcao);
        if (destino != 0 && tabuleiro.ler(destino) == vazia) {
          lances.add(Lance([origem, destino], const [],
              viraDama: !pecaEDama && casasDeCoroacao[cor].contains(destino)));
        }
      }
    }
  }
  return lances;
}

/// Todos os lances legais de quem tem a vez.
///
/// A ordem das três decisões é a do regulamento, e ela importa: se há captura é
/// obrigatório capturar; entre as capturas aplica-se a Lei da Maioria onde ela
/// vale; sem captura nenhuma, valem os lances simples.
///
/// Lista vazia **não** é erro: é derrota de quem tem a vez. O objetivo do jogo é
/// "imobilizar ou capturar todas as peças do adversário" — ficar sem lance perde
/// igual a ficar sem peça.
List<Lance> gerarLances(Tabuleiro tabuleiro, Regulamento regulamento) {
  final capturas = gerarCapturas(tabuleiro, regulamento);

  if (capturas.isNotEmpty) {
    if (!regulamento.capturaMaximaObrigatoria) return capturas;
    var maximo = 0;
    for (final lance in capturas) {
      if (lance.quantasCapturas > maximo) maximo = lance.quantasCapturas;
    }
    // Filtra NA PRÓPRIA lista, compactando para a frente, em vez de construir
    // outra com `where().toList()`. Numa busca, cada lista a menos por nó conta.
    var escrita = 0;
    for (var leitura = 0; leitura < capturas.length; leitura++) {
      if (capturas[leitura].quantasCapturas == maximo) {
        capturas[escrita++] = capturas[leitura];
      }
    }
    capturas.length = escrita;

    // A Lei da Qualidade (FPD 3.7.b) entra DEPOIS, e só desempata o que a
    // quantidade deixou empatado. A ordem não é comutativa: invertê-la faria o
    // motor tomar uma dama em vez de três pedras, que é lance ilegal ali.
    if (regulamento.desempatePorQualidade) {
      var melhor = 0;
      for (final lance in capturas) {
        final damas = damasCapturadas(tabuleiro, lance);
        if (damas > melhor) melhor = damas;
      }
      escrita = 0;
      for (var leitura = 0; leitura < capturas.length; leitura++) {
        if (damasCapturadas(tabuleiro, capturas[leitura]) == melhor) {
          capturas[escrita++] = capturas[leitura];
        }
      }
      capturas.length = escrita;
    }

    return capturas;
  }

  return gerarLancesSimples(tabuleiro, regulamento);
}

/// Quantas das peças tomadas por este lance são **damas**.
///
/// É o que a Lei da Qualidade mede. Consulta o tabuleiro **de antes** do lance,
/// e isso é obrigatório: durante a geração as capturadas continuam no tabuleiro
/// (Tema Turco), então é aqui que ainda dá para perguntar o que cada uma era.
///
/// ⚠️ **Pública, ao contrário da irmã em Python** (`_damas_capturadas`). Em Dart
/// o `_` esconde de outros ARQUIVOS, não de outras classes, e
/// `explicacao_de_recusa_damas.dart` precisa desta contagem para distinguir a
/// Lei da Qualidade da Lei da Maioria. A alternativa seria recontar as damas lá
/// — cinco linhas triviais que viram uma segunda verdade sobre o que a Lei da
/// Qualidade mede. Uma diferença de visibilidade custa menos que isso.
int damasCapturadas(Tabuleiro tabuleiro, Lance lance) {
  var damas = 0;
  for (final casa in lance.capturadas) {
    final peca = tabuleiro.ler(casa);
    if (peca == damaBranca || peca == damaPreta) damas++;
  }
  return damas;
}

/// O que é preciso guardar para desfazer um lance.
///
/// Reaproveitado a cada nó da busca (há um por nível de profundidade), para que
/// aplicar e desfazer um lance não aloque nada.
class DesfazerLance {
  int pecaMovida = 0;
  int vezAnterior = 0;
  Lance? lance;

  /// As peças que estavam nas casas capturadas, na mesma ordem.
  /// 12 é folgado: não existe cadeia que tome mais peças que isso em 8×8.
  final List<int> pecasCapturadas = List<int>.filled(12, 0);
}

/// Aplica o lance **no próprio tabuleiro** e guarda como desfazê-lo.
///
/// É o par *make/unmake*, e ele existe por um motivo medido: [aplicarLance]
/// clona o tabuleiro, e clonar a cada nó de uma busca que visita centenas de
/// milhares de posições por segundo custa caro — apareceu na primeira medição
/// no aparelho. Aqui não se aloca nada: a busca desce mexendo no mesmo objeto e
/// desfaz na volta.
///
/// As peças capturadas saem **todas de uma vez, ao fim do lance**, que é o que o
/// Tema Turco manda. Durante a geração elas ficaram no tabuleiro.
void aplicarNoLugar(Tabuleiro tabuleiro, Lance lance, DesfazerLance desfazer) {
  desfazer
    ..lance = lance
    ..vezAnterior = tabuleiro.vez
    ..pecaMovida = tabuleiro.ler(lance.origem);

  tabuleiro.escrever(lance.origem, vazia);
  for (var i = 0; i < lance.capturadas.length; i++) {
    final casa = lance.capturadas[i];
    desfazer.pecasCapturadas[i] = tabuleiro.ler(casa);
    tabuleiro.escrever(casa, vazia);
  }

  // A cor da dama nova sai da vez ATUAL, antes de a vez virar.
  final peca = lance.viraDama
      ? (tabuleiro.vez == brancas ? damaBranca : damaPreta)
      : desfazer.pecaMovida;
  tabuleiro.escrever(lance.destino, peca);
  tabuleiro.vez = tabuleiro.vez == brancas ? pretas : brancas;
}

/// Desfaz o que [aplicarNoLugar] fez, na ordem inversa.
///
/// A ordem importa num caso: numa captura em ciclo o destino **é** a origem
/// (a peça volta para onde saiu). Limpar o destino antes de repor a origem
/// deixa o resultado certo nos dois casos.
void desfazerNoLugar(Tabuleiro tabuleiro, DesfazerLance desfazer) {
  final lance = desfazer.lance!;
  tabuleiro.vez = desfazer.vezAnterior;
  tabuleiro.escrever(lance.destino, vazia);
  for (var i = lance.capturadas.length - 1; i >= 0; i--) {
    tabuleiro.escrever(lance.capturadas[i], desfazer.pecasCapturadas[i]);
  }
  tabuleiro.escrever(lance.origem, desfazer.pecaMovida);
}

/// Devolve a posição **nova** resultante do lance, sem alterar a original.
///
/// Cômodo e mais lento: aloca um tabuleiro. Bom para script, teste e `perft`;
/// dentro da busca use [aplicarNoLugar].
Tabuleiro aplicarLance(Tabuleiro tabuleiro, Lance lance) {
  final novo = tabuleiro.clonar();
  var peca = novo.ler(lance.origem);

  novo.escrever(lance.origem, vazia);
  for (final casa in lance.capturadas) {
    novo.escrever(casa, vazia);
  }
  if (lance.viraDama) {
    peca = tabuleiro.vez == brancas ? damaBranca : damaPreta;
  }
  novo.escrever(lance.destino, peca);
  novo.vez = tabuleiro.vez == brancas ? pretas : brancas;
  return novo;
}

/// `perft`: quantas posições distintas existem até certa profundidade.
///
/// Conta as **folhas** da árvore de lances legais. É o teste que prova que o
/// gerador está certo, porque os números são publicados por terceiros.
int contarPosicoes(Tabuleiro tabuleiro, int profundidade, Regulamento regulamento) {
  if (profundidade == 0) return 1;
  final lances = gerarLances(tabuleiro, regulamento);
  if (profundidade == 1) return lances.length;

  var total = 0;
  for (final lance in lances) {
    total += contarPosicoes(aplicarLance(tabuleiro, lance), profundidade - 1, regulamento);
  }
  return total;
}
