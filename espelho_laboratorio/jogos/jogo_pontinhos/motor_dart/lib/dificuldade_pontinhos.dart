// OS NÚMEROS de cada nível de dificuldade **no Jogo dos Pontinhos**.
//
// ⚠️ Não confundir com `NivelDificuldade`, do hub (`lib/core/jogos/` no
// aplicativo): aquele é o degrau da escada (fácil → sagaz), comum a todos os
// jogos; este são os números que fazem o degrau significar alguma coisa **aqui**.
// Nada disto viaja para outro jogo - a velha não tem caixa para fechar, e os
// timers dela são 15/10/7.
//
// ── ⚠️ POR QUE ESTE ENUM MORA NO MOTOR (T093, 28/09/2026) ───────────────────
//
// Ele é a **fonte da verdade** dos parâmetros de dificuldade, e sempre foi (o
// `contrato_dificuldade_pontinhos.json` é a declaração dele, lida pelo servidor).
// Enquanto ele morava dentro do aplicativo, o servidor jogava lendo o contrato e
// reimplementando a política em Python; desde a T093 quem decide o lance no
// servidor é este pacote compilado, e então o enum precisa vir junto.
//
// ⛔ **O getter `nivel` e a função `dificuldadeDe` NÃO estão aqui**, e não é
// esquecimento: os dois falam de `NivelDificuldade`, que é do hub e só existe no
// aplicativo. Um arquivo espelhado que importasse de lá não compilaria no
// laboratório nem no servidor. Eles continuam onde estavam, em
// `logica/modelos.dart`, como a ponte entre os dois vocabulários.
library;

/// Parâmetros de dificuldade do adversário CPU **no Jogo dos Pontinhos**.
///
/// Observação de produto: a CNN embarcada é única (modelo "pequeno"/4×3). Todos
/// os níveis consultam o mesmo modelo; o que os separa é o que está aqui.
enum Dificuldade {
  // ── POLÍTICA DE DIFICULDADE: ε-greedy (desde 2026-07-13) ───────────────────
  //
  // `epsilon` = a PROBABILIDADE de a CPU jogar DE PROPÓSITO fora do melhor lance.
  // A cada jogada tática ela sorteia um número entre 0 e 1: se cair abaixo do
  // `epsilon`, escolhe um traço aleatório qualquer que NÃO seja o melhor (nem um
  // empatado no topo); senão, joga o melhor lance da CNN. Só isso.
  //     • Cacau (fácil)   → 0.80 → erra 80% das jogadas táticas;
  //     • Pita  (normal)  → 0.50 → erra metade;
  //     • Tex   (difícil) → 0.14 → erra 14%;
  //     • Magno (sagaz)   → 0.00 → NUNCA erra de propósito (argmax puro).
  //
  // EXCEÇÃO DO MAGNO — A ABERTURA (desde 2026-07-30). Com `epsilon == 0` e a CNN
  // sendo determinística, o Magno abria TODA partida com a mesma aresta. Quando é
  // ELE quem abre, o primeiro lance — e só ele — passa a ser sorteado entre os
  // traços disponíveis: no tabuleiro vazio todos são equivalentes por simetria,
  // então isso dá variedade sem tirar força. Implementado na Fase 0 de
  // `escolherLance` (`politica_dificuldade_pontinhos.dart`).
  //
  // POR QUE ε-GREEDY, E NÃO O "NÚCLEO TOP-P" DE ANTES. O top-p sorteava entre os
  // lances de maior probabilidade cujo somatório alcançasse um alvo `p`. O problema
  // é que esse núcleo é ADAPTATIVO À CONFIANÇA DA REDE: quando a CNN concentra ~99%
  // num único traço (o que acontece justamente no fim de jogo, com as cadeias já
  // formadas), o primeiro lance sozinho já estoura qualquer alvo `p` — o núcleo
  // colapsa para UM lance e até a Cacau passava a jogar perfeito exatamente no lance
  // que decide a partida. Ou seja: quanto mais decisivo o momento, MENOS aleatória
  // a CPU ficava — o inverso do desejado, e nenhum valor de `p` corrigia isso.
  // O `epsilon` é uma probabilidade FIXA: não olha para a confiança da rede, então
  // o fácil continua errando no fim de jogo, que é onde tem que errar.
  //
  // `usaCapturaGulosa` = se a CPU fecha caixa de graça SEM pensar (Fase A). Vale
  // para Cacau/Pita/Tex: capturar caixa aberta não é habilidade, é instinto — todo
  // iniciante faz. Sabotar isso com o `epsilon` faria a CPU ignorar caixa de graça
  // na cara dela, o que parece DEFEITO, não dificuldade (e ainda quebraria o turno
  // extra que encadeia a captura da cadeia inteira).
  // O Magno é o único com `false`: ele decide TUDO pela CNN, o que o deixa livre
  // para fazer o sacrifício da dupla-cruz (abrir mão das 2 últimas caixas de uma
  // cadeia para manter o turno) — a jogada mestre que os outros três nunca fazem.
  //
  // timerSegundos = relógio da jogada do humano (null = sem timer).
  //
  // ⚠️ **O relógio ⛔ tem efeito nenhum no servidor**, e viaja junto de propósito:
  // é o mesmo contrato que o aplicativo declara, e omiti-lo aqui convidaria a uma
  // segunda leitura parcial em outro lugar.
  //
  // ORDEM DOS VALORES IMPORTA: é a ordem de força (fácil → sagaz), usada para
  // derivar o índice de "força do adversário" no cálculo de XP (partida_screen).
  //
  // ── AJUSTE DE 2026-08-06, a partir de dados de CAMPO ──────────────────────
  //
  // 2 690 partidas de 24 pessoas em produção mostraram que a escada estava
  // comprimida — e num degrau, invertida em relação ao alvo:
  //
  // | nível   | o humano vencia | alvo | o que se fez |
  // |---------|-----------------|------|--------------|
  // | fácil   | 51,0 %          | 70 % | ε 0,70 → **0,80** (Cacau mais burra) |
  // | normal  | 39,7 %          | 50 % | inalterado — o desvio é o menor |
  // | difícil | **30,4 %**      | 20 % | ε 0,20 → **0,14** (Tex mais esperto) |
  // | sagaz   | 1,6 %           | ~0,5 %| inalterado |
  //
  // O difícil estava **mais fácil** que o alvo, e não mais difícil: era o único
  // degrau errado para cima. Sem os dados de campo isso não apareceria — a
  // sensação de quem joga é "está tudo difícil", que aponta para o lado oposto.
  //
  // ⚠️ **Estes dois números são CHUTE calibrado pela direção, não por medição.**
  // Decisão consciente do dono (2026-08-06): mexer só no parâmetro agora, sem
  // tocar na dinâmica, e deixar a calibração precisa para a branch de revisão de
  // dificuldade — quando houver dados dos DOIS jogos em banco. O plano está em
  // `specs/007-jogo-da-velha/revisao-dificuldade-e-xp.md`.
  facil(estrelas: 1, epsilon: 0.80, usaCapturaGulosa: true, timerSegundos: null),
  normal(estrelas: 2, epsilon: 0.50, usaCapturaGulosa: true, timerSegundos: 20),
  dificil(estrelas: 3, epsilon: 0.14, usaCapturaGulosa: true, timerSegundos: 15),
  sagaz(estrelas: 4, epsilon: 0.00, usaCapturaGulosa: false, timerSegundos: 10);

  const Dificuldade({
    required this.estrelas,
    required this.epsilon,
    required this.usaCapturaGulosa,
    required this.timerSegundos,
  });

  /// Quantas estrelas (de 4) o card do personagem exibe.
  final int estrelas;

  /// Probabilidade (0..1) de jogar FORA do melhor lance na fase tática.
  /// `0` = joga sempre o argmax da CNN (Magno). Ver doc do enum acima.
  final double epsilon;

  /// Se fecha caixa de graça por instinto, sem consultar a CNN (Fase A).
  /// Só o Magno é `false` — ver doc do enum acima.
  final bool usaCapturaGulosa;

  /// Tempo da jogada do humano, em segundos. `null` = sem timer (Cacau).
  final int? timerSegundos;

  /// A chave com que este nível é declarado no
  /// `contrato_dificuldade_pontinhos.json` e pedida pelo servidor de lances.
  ///
  /// ⚠️ **É o `name` do valor, e não uma segunda lista escrita à mão.** Uma
  /// tabela paralela envelheceria calada no dia em que um nível fosse
  /// renomeado - e o servidor pediria um nível que ninguém declara.
  String get chave => name;

  /// O nível daquela chave (`facil` · `normal` · `dificil` · `sagaz`).
  ///
  /// ⛔ **Não cai num valor padrão.** Uma chave desconhecida que virasse "fácil"
  /// faria o servidor gerar o gabarito do Magno com o desleixo da Cacau, e
  /// gravar "sagaz" no banco - o pior desfecho possível.
  static Dificuldade daChave(String chave) => values.firstWhere(
        (d) => d.chave == chave,
        orElse: () => throw ArgumentError(
          'nível de dificuldade desconhecido: "$chave". '
          'O motor conhece: ${values.map((d) => d.chave).join(", ")}.',
        ),
      );
}
