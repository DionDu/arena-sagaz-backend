// A BASE DECIDE O FINAL — a consulta na raiz (T185 parte 2a).
//
// ── O que esta função faz ──────────────────────────────────────────────────
//
// Quando a posição da partida cabe na base de finais, não existe "melhor lance
// provável": existe **o** lance certo, e ele está gravado. Esta função pega a
// posição da mesa, olha cada lance legal, pergunta à base o que acontece depois
// de cada um, e devolve o lance que realiza o veredito exato — ganhar o mais
// rápido possível, empatar quando é empate, e resistir o máximo quando está
// perdido.
//
// Nenhum nó é buscado. A resposta não é uma estimativa boa; é a verdade.
//
// ── ⚠️ POR QUE ELE MUDOU DE CASA EM 25/09/2026 ────────────────────────────
//
// Este arquivo nasceu em `arena-sagaz-frontend/lib/modulos/jogos/damas/logica/`,
// e ali era o lugar certo enquanto só o **aplicativo** consultava a base. Desde
// 25/09/2026 o **servidor** joga com este mesmo motor compilado
// (`bin/servidor_de_lances_damas.dart`), para que o gabarito do Desafio do Dia
// seja idêntico ao que a CPU joga no aparelho de quem resolve — e um programa do
// laboratório não pode importar de uma pasta que só existe no app.
//
// ⛔ **Sem esta função, o servidor divergiria em todo final de até 4 peças**: o
// aparelho responde pela base, sem buscar, e o servidor buscaria. É a mesma
// classe de defeito que custou a investigação de 25/09
// (`arena-sagaz-backend/docs/investigacao_paridade_motores.md`): dois motores
// com o mesmo nome jogando jogos diferentes.
//
// ⚠️ **É exatamente a mudança que `oraculo_de_finais_damas.dart` fez em
// 27/08/2026**, pelo mesmo motivo estrutural, e com a mesma solução: o endereço
// antigo no app continua valendo, como reexporte de uma linha.
//
// ⚠️ **Mudar de casa NÃO mudou quem chama.** Esta função continua **acima** dos
// dois motores: quem decide consultá-la é a tela (no app) e o servidor de lances
// (no backend), nunca `busca_damas.dart`. As duas razões originais continuam
// valendo palavra por palavra, e estão logo abaixo.
//
// ── ⚠️ Por que ela NÃO é chamada de dentro da busca ────────────────────────
//
// Este projeto já pagou por essa lição uma vez, e a lição está escrita em
// `atalho_lance_unico_damas.dart` e no research **D-27**: o atalho de lance
// único nasceu **dentro** da busca (motor 1.0.4) e teve de sair no 1.1.0,
// porque de lá ele contaminava a telemetria do motor e a bancada se recusou a
// medir.
//
// Aqui a razão é a mesma, mais uma segunda, que é decisiva:
//
//   1. **Telemetria.** Um lance vindo da base não tem nós, nem profundidade,
//      nem nota. Do lado do app a ausência é gravada como ausência; de dentro
//      do motor ela viraria número inventado.
//
//   2. **⚠️ O cadeado de equivalência.** `busca_damas.dart` é espelhado
//      byte a byte com o laboratório, e `conferir_equivalencia_com_rust.dart`
//      exige que o motor Dart e o motor Rust escolham o **mesmo** lance. Uma
//      base consultada só do lado Dart faria os dois discordarem em todo final
//      de 4 peças — o cadeado cairia, e cairia **com razão**. Enquanto o Rust
//      não tiver a base, o probing não pode entrar em nenhum dos dois. Acima
//      dos dois motores, como aqui, a consulta é indiferente a qual deles teria
//      jogado.
//
// ── ⚠️ A aproximação que a base carrega, e que este código herda ───────────
//
// A base foi construída com `regras_de_empate_aplicadas: true`: os arts. 97-100
// convertem em empate as vitórias que o lado forte não conclui dentro do limite
// de lances do regulamento (ver `empates_declarados_damas.dart`). Só que a base
// conta esse limite **a partir da posição avaliada**, como se o contador
// estivesse zerado ali. Numa partida real ele pode já ter corrido.
//
// O efeito é conhecido e tem um só sentido: a base é **otimista para o lado
// forte** — pode dizer "ganha em 15" onde o contador da mesa só permite 5, e o
// jogo terminará empatado. O contrário não acontece: ela nunca promete empate
// numa posição que se perde. Ou seja, a aproximação custa vitórias que viram
// empate, e **nunca** transforma empate em derrota. Para um nível que se
// vende por não perder, é o lado certo do erro.
//
// ── O que esta função NÃO decide ───────────────────────────────────────────
//
// Ela não sabe de dificuldade. Jogar perfeito é trabalho do Magno; Cacau, Pita
// e Tex precisam ser batíveis, e quem escolhe se consulta a base é a tela, não
// esta função. Diferente do atalho de lance único — que vale para todos porque
// não muda lance nenhum —, **esta consulta muda o lance**, e por isso é uma
// decisão de nível.

import 'indice_damas.dart';
import 'regras_damas.dart';
import 'retrograda_damas.dart';
import 'tabuleiro_damas.dart';
import 'oraculo_de_finais_damas.dart';

/// O que a base tem a dizer sobre a posição — e o lance que realiza isso.
///
/// O [resultado] é do ponto de vista de **quem tem a vez**, e usa os três
/// valores de `indice_damas.dart`: [derrota] (0), [empate] (1), [vitoria] (2).
/// Note que estes NÃO são os valores da avaliação do motor (lá `vitoria` é
/// 1.000.000); são os três estados de um final resolvido.
class VereditoDaBase {
  /// [derrota], [empate] ou [vitoria], para quem está para jogar.
  final int resultado;

  /// Em quantos **meios-lances** a partida acaba, contados desta posição, com
  /// jogo perfeito dos dois lados. Vale [semDistancia] quando o resultado é
  /// empate — um empate não tem "em quantos".
  final int distancia;

  /// O lance que realiza o [resultado]: o mais rápido para ganhar, o mais longo
  /// para perder, um que sustente o empate.
  final Lance lance;

  /// Quantos lances legais foram examinados para chegar aqui. Serve ao log e
  /// aos testes; não é um contador de nós de busca (busca não houve).
  final int lancesExaminados;

  const VereditoDaBase({
    required this.resultado,
    required this.distancia,
    required this.lance,
    required this.lancesExaminados,
  });

  /// Atalhos de leitura, para quem chama não precisar comparar com as
  /// constantes na mão.
  bool get ganha => resultado == vitoria;
  bool get empata => resultado == empate;
  bool get perde => resultado == derrota;
}

/// Os nomes das fatias que uma consulta a esta posição vai precisar.
///
/// ── Por que isto existe ────────────────────────────────────────────────────
///
/// A base de 4 peças inteira ocupa **39,4 MB** — carregá-la para responder uma
/// pergunta sobre uma posição seria pagar o preço de tudo para usar quase nada.
/// Mas o formato é um arquivo por fatia, e uma consulta toca poucas: a fatia da
/// própria posição, mais a de cada filho. Como um lance nunca aumenta material,
/// os filhos ficam na mesma fatia ou numa menor.
///
/// Passe o resultado disto em `apenasAsFatias` de `carregarBaseDeFinais` e o
/// custo despenca. **Medido em 25/08/2026**, num final de 4 peças real
/// (`W:WK28,20:BK3,12`) contra a base do laboratório: **3,9 MB** no lugar dos
/// 39,4 MB da base inteira — dez vezes menos, e a resposta é a mesma. A maior
/// fatia da base de 4 peças (`0112`) tem 2,2 MB somando valores e distâncias.
///
/// Fatias sem os dois lados ficam de fora: elas não existem na numeração
/// (ver [Fatia.temOsDoisLados]), e a posição correspondente é uma partida que
/// já acabou.
Set<String> fatiasNecessariasPara(
  Tabuleiro tabuleiro,
  Regulamento regulamento,
) {
  final necessarias = <String>{};

  void talvezIncluir(Tabuleiro t) {
    final fatia = fatiaDaPosicao(t);
    // `null` = mais de 8 peças de um tipo, ou seja, longe demais da base.
    if (fatia != null && fatia.temOsDoisLados) necessarias.add(fatia.nome);
  }

  talvezIncluir(tabuleiro);
  for (final lance in gerarLances(tabuleiro, regulamento)) {
    talvezIncluir(aplicarLance(tabuleiro, lance));
  }
  return necessarias;
}

/// O lance exato para esta posição, ou `null` quando a base não sabe responder.
///
/// Devolve `null` — o que para quem chama significa **"busque normalmente"** —
/// em todas estas situações, e nenhuma delas é um erro:
///
/// * a posição tem material demais e está fora da base;
/// * a partida já acabou ali (um dos lados sem peças, ou nenhum lance legal);
/// * a base foi carregada só com algumas fatias e falta uma que a resposta
///   precisaria (por exemplo, esqueceram de passar [fatiasNecessariasPara]);
/// * a base foi carregada com `comDistancias: false` e a posição é ganha ou
///   perdida — sem distância não há como escolher *qual* vitória.
///
/// O `null` é sempre a saída segura: perder a consulta custa um lance
/// pesquisado em vez de um lance perfeito, e nunca um lance ilegal ou uma
/// exceção no meio da partida.
///
/// [lancesLegais] vem de fora, e não é recalculado aqui, porque quem chama já o
/// tem em mãos (o estado da partida o mantém). Ele **precisa** ser o resultado
/// de `gerarLances` para esta mesma posição — passar outra lista faria a função
/// escolher um lance que não é legal.
VereditoDaBase? consultarBaseDeFinais({
  required Tabuleiro tabuleiro,
  required List<Lance> lancesLegais,
  required OraculoDeFinais base,
  Indexador? indexador,
}) {
  // Sem lance legal não há o que escolher: é afogamento, e transformá-lo em
  // desfecho é trabalho do estado da partida, não desta função.
  if (lancesLegais.isEmpty) return null;

  // ── ⚠️ A GUARDA QUE IMPEDE UM CRASH NO MEIO DA PARTIDA ────────────
  //
  // Uma posição de meio de jogo não pertence a fatia nenhuma, e é isso que
  // [fatiaDaPosicao] devolvendo `null` diz. A guarda cobre de uma vez os **dois**
  // modos de falha que esta função descobriu em 25/08/2026, ao ser a primeira a
  // consultar a base a partir de uma posição **viva**:
  //
  //   * a posição inicial (12×12 pedras) estourava o vetor de 6.561 entradas;
  //   * pior, `3` pedras brancas contra `9` pretas — meio de jogo comumíssimo —
  //     **aliasava** na fatia `3100`, que existe na base de 4 peças.
  //
  // Os dois estão contados no aviso de [codigoDaPosicao]. A **correção de raiz
  // foi lá** (motor 1.1.1), e esta guarda fica aqui de qualquer forma: uma
  // função do app não pode depender de o motor não lançar.
  //
  // Um lado sem peças cai na mesma guarda pelo outro caminho — a fatia existe,
  // mas não tem [Fatia.temOsDoisLados]. `consultar` até responderia (por regra,
  // sem abrir arquivo nenhum), mas devolver um "lance" para uma partida já
  // encerrada seria pior que calar.
  final fatiaDaRaiz = fatiaDaPosicao(tabuleiro);
  if (fatiaDaRaiz == null || !fatiaDaRaiz.temOsDoisLados) return null;

  // Um só [Indexador] para a raiz e todos os filhos: ele carrega tabelas
  // internas, e criar um por consulta desperdiça o trabalho de montá-las.
  final ind = indexador ?? Indexador();

  final resultadoDaRaiz = base.consultar(tabuleiro, indexador: ind);
  // ⚠️ `foraDaBase` e `empate` são coisas completamente diferentes: o primeiro
  // é "não sei", o segundo é "sei, e é empate". Confundi-los faria o app achar
  // que todo meio-jogo está equilibrado.
  if (resultadoDaRaiz == foraDaBase) return null;

  final distanciaDaRaiz = base.distanciaDe(tabuleiro, indexador: ind);
  // ⚠️ **O empate DECLARADO sai da consulta.** Ver a nota longa em
  // [_ehEmpateDeclarado]: naquelas posições o valor gravado é um veredito do
  // *regulamento*, não do jogo, e ele não se reproduz a partir dos filhos.
  if (_ehEmpateDeclarado(resultadoDaRaiz, distanciaDaRaiz)) return null;

  // ── Percorrer os filhos ───────────────────────────────────────────────────
  //
  // O valor gravado é sempre do ponto de vista de quem tem a vez **naquela**
  // posição — depois do meu lance, quem tem a vez é o adversário. Então o que
  // um lance vale para MIM é `2 - valorDoFilho`: a conta troca vitória (2) por
  // derrota (0) e deixa o empate (1) onde está.
  Lance? escolhido;
  var distanciaEscolhida = semDistancia;
  final procuraOMenor = resultadoDaRaiz == vitoria;

  for (final lance in lancesLegais) {
    final filho = aplicarLance(tabuleiro, lance);

    final valorDoFilho = base.consultar(filho, indexador: ind);
    // Numa base completa isto não acontece — um lance nunca aumenta material,
    // então nenhum filho escapa de uma base de N peças (a conferência da parte 1
    // mediu exatamente zero sucessores fora da base). Com carga parcial de
    // fatias, acontece; e aí a escolha seria feita com informação faltando.
    if (valorDoFilho == foraDaBase) return null;

    final meuResultado = 2 - valorDoFilho;
    if (meuResultado != resultadoDaRaiz) continue;

    // Empate não tem distância a comparar: o primeiro que sustenta o empate
    // serve, e ficar com o primeiro deixa a escolha determinística.
    if (resultadoDaRaiz == empate) {
      escolhido = lance;
      break;
    }

    final distanciaDoFilho = _distanciaAposOLance(base, filho, indexador: ind);
    // Ganho ou perdido, a escolha é por distância. Se ela falta, a base foi
    // carregada sem o arquivo de distâncias — e escolher "qualquer vitória"
    // faria o Magno empurrar peça para sempre numa posição ganha, até os
    // arts. 97-100 declararem empate.
    if (distanciaDoFilho == semDistancia) return null;

    if (escolhido == null ||
        (procuraOMenor
            ? distanciaDoFilho < distanciaEscolhida
            : distanciaDoFilho > distanciaEscolhida)) {
      escolhido = lance;
      distanciaEscolhida = distanciaDoFilho;
    }
  }

  // Nenhum filho confirma o veredito da raiz. Pela regra isto é impossível:
  // o valor de uma posição É o melhor que os filhos oferecem. Se acontecer, a
  // base que está na mão contradiz a si mesma.
  //
  // ⚠️ Em desenvolvimento o `assert` derruba na hora, com a posição no texto —
  // é assim que um arquivo corrompido é descoberto. Em produção o `assert` não
  // roda e a função devolve `null`, e a partida segue com uma busca normal:
  // **o app não pode crashar por causa do motor novo.**
  assert(
    escolhido != null,
    'a base contradiz a si mesma: a raiz diz '
    '${_emPalavras(resultadoDaRaiz)} e nenhum dos ${lancesLegais.length} '
    'lances legais leva a isso — posição ${tabuleiro.paraFen()}',
  );
  if (escolhido == null) return null;

  return VereditoDaBase(
    resultado: resultadoDaRaiz,
    // A minha distância é a do filho escolhido mais o meu próprio lance. No
    // empate não há o que somar.
    distancia: resultadoDaRaiz == empate ? semDistancia : distanciaEscolhida + 1,
    lance: escolhido,
    lancesExaminados: lancesLegais.length,
  );
}

/// Este empate foi **declarado pelo regulamento**, e não encontrado no jogo?
///
/// ── O discriminador, e por que ele é exato ───────────────────────────
///
/// Um empate de verdade não tem distância: ninguém "empata em 12 lances", e a
/// análise retrógrada grava [semDistancia] neles. Já os arts. 97-100 agem
/// **depois**, trocando só o valor de vitória/derrota para empate e deixando a
/// distância original onde estava (ver `aplicarRegrasDeEmpate` em
/// `empates_declarados_damas.dart`, que escreve `valores[indice] = empate` e não
/// toca em `distancias`).
///
/// Logo: **empate COM distância ⇒ empate declarado**. Isso foi medido nas 41
/// fatias da base real de 4 peças em 25/08/2026 — 54.956 posições com
/// `valor == empate && distancia >= 0`, contra 54.956 `declarados_empate`
/// somados no manifesto, **sem uma fatia divergente**.
///
/// ── Por que elas saem da consulta ──────────────────────────────────
///
/// Por duas razões, e a segunda sozinha já bastaria:
///
/// 1. **O veredito ali é do regulamento, e depende de um contador que a base
///    não tem.** Ela conta o limite de lances como se ele começasse naquela
///    posição; na mesa ele pode já ter corrido. Agir sobre isso é desistir de
///    uma vitória que a partida real talvez ainda permitisse.
///
/// 2. **Ele não se reproduz a partir dos filhos.** A regra desta função — e da
///    conferência da parte 1 — é que o valor de uma posição é o melhor entre os
///    dos filhos, trocado de lado. Numa posição convertida isso deixa de valer:
///    a raiz diz empate e os filhos podem dizer, todos, vitória (é o caso de
///    fronteira — ganha em 21 vira empate, e o filho, ganha em 20, continua
///    vitória). Não haveria lance nenhum realizando o veredito da raiz, e a
///    função não teria o que devolver.
///
/// São **0,42% da base** (54.956 de 13.125.184), então o custo de deixar a busca
/// resolvê-las é pequeno. É a mesma pendência declarada em
/// `empates_declarados_damas.dart`: as duas leituras ambíguas dos arts. 97 e 100
/// se resolvem contra o Aurora Borealis, e até lá não se joga por elas.
bool _ehEmpateDeclarado(int resultado, int distancia) =>
    resultado == empate && distancia != semDistancia;

/// A distância depois do lance, do ponto de vista da regra e não do arquivo.
///
/// ⚠️ **O caso que custou 50 falsos positivos na conferência da parte 1.**
/// Quando o lance captura a última peça do adversário, a posição resultante não
/// está em fatia nenhuma — a numeração só cobre posições com peça dos dois
/// lados. [OraculoDeFinais.consultar] responde certo (por regra), mas
/// [OraculoDeFinais.distanciaDe] devolve [semDistancia], porque não há vetor onde
/// procurar.
///
/// Pela regra a distância é conhecida e vale **zero**: a partida acabou naquele
/// lance. Sem isto, o lance que ganha na hora pareceria o pior de todos — a
/// única vitória sem distância — e seria justamente o descartado.
int _distanciaAposOLance(OraculoDeFinais base, Tabuleiro filho,
    {required Indexador indexador}) {
  final fatia = fatiaDaPosicao(filho);
  // `null` não acontece aqui — filho de posição que cabe na base também cabe —
  // mas [semDistancia] é a resposta honesta se um dia acontecer: faz o chamador
  // calar, em vez de confundir "não sei" com "acabou agora".
  if (fatia == null) return semDistancia;
  if (!fatia.temOsDoisLados) return 0;
  return base.distanciaDe(filho, indexador: indexador);
}

/// Só para a mensagem do `assert` acima sair legível.
String _emPalavras(int resultado) => switch (resultado) {
      derrota => 'derrota',
      empate => 'empate',
      vitoria => 'vitória',
      _ => 'valor desconhecido ($resultado)',
    };
