// O MOTOR DO APARELHO, ATENDENDO O SERVIDOR — um pedido por linha.
//
// ── Por que este programa existe ────────────────────────────────────────────
//
// Até 25/09/2026 o gerador de desafios jogava com o port **Python** do motor, e
// o aparelho jogava com o Dart (ou com o Rust, que é conferido contra o Dart).
// Os dois liam os mesmos parâmetros do mesmo contrato — `teto_de_nos: 288000` e
// `tempo_maximo: 10.0` — e mesmo assim escolhiam lances diferentes.
//
// A causa não era o port: era o **relógio**. O Python é cerca de 40x mais lento,
// então os 10 segundos de rede de segurança mordiam TODO lance no servidor e
// NUNCA no aparelho. O gabarito saía de uma busca que via 124.928 nós e chegava
// à profundidade 11, enquanto o aparelho via 288.001 e chegava à 12. Desligado o
// relógio, os dois param no mesmo nó e escolhem o mesmo lance.
//
// O diagnóstico inteiro está em
// `arena-sagaz-backend/docs/investigacao_paridade_motores.md`.
//
// ⛔ **A correção não é ajustar números: é parar de ter dois motores.** Este
// programa faz o servidor jogar com **o código que o aparelho embarca** - este
// pacote, byte a byte. Não há port a manter em dia, e a pergunta *"será que
// alguém mudou um lado só?"* deixa de existir.
//
// ── Por que um processo que fica vivo, e não um comando por lance ───────────
//
// A régua mede 20 execuções por mascote, e uma partida tem dezenas de lances.
// Subir um processo por lance pagaria a partida do Dart (carregar o executável,
// aquecer) milhares de vezes. Aqui o processo sobe uma vez e responde a pedidos
// enquanto for alimentado.
//
// ⚠️ **Uma linha de texto por pedido, uma por resposta.** É a mesma decisão da
// fronteira do motor Rust (`motor_rust/src/ffi.rs`): texto, e não estrutura
// binária compartilhada. Texto se lê no log, se cola num relatório de defeito e
// não obriga os dois lados a concordarem sobre layout de memória.
//
// ── O que ele NÃO decide ────────────────────────────────────────────────────
//
// ⛔ **Nenhum parâmetro de nível mora aqui.** Teto de nós, profundidade, ruído e
// relógio chegam **no pedido**, e quem os lê é o servidor, no contrato
// (`contrato_damas.json`). Repetir os números neste arquivo criaria a quinta
// cópia de um número que já está em quatro lugares - exatamente o risco que o
// dono levantou em 25/09/2026.
//
// ── Como rodar ──────────────────────────────────────────────────────────────
//
//   dart compile exe bin/servidor_de_lances_damas.dart \
//       -o bin/servidor_de_lances_damas.exe
//
// e depois, para experimentar à mão (um JSON por linha):
//
//   echo {"fen_inicial":"W:W18:B12","modalidade":"anglo","teto_de_nos":1000} \
//       | bin/servidor_de_lances_damas.exe

import 'dart:convert';
import 'dart:io';

import 'package:motor_damas/base_empacotada_damas.dart';
import 'package:motor_damas/busca_damas.dart';
import 'package:motor_damas/consulta_base_finais_damas.dart';
import 'package:motor_damas/empates_por_historico_damas.dart';
import 'package:motor_damas/oraculo_de_finais_damas.dart';
import 'package:motor_damas/regras_damas.dart';
import 'package:motor_damas/tabuleiro_damas.dart';

import '_resumo_do_motor.g.dart';

/// A versão do PROTOCOLO desta fronteira - não a do motor.
///
/// ⚠️ Ela sobe quando o formato do pedido ou da resposta muda de forma que o
/// outro lado precise saber. O servidor confere na abertura: sem isto, um
/// backend novo conversando com um executável velho receberia respostas
/// plausíveis e erradas, que é o pior modo de falha possível.
///
/// ⚠️ **2 (25/09/2026): a base de finais.** O pedido ganhou `pasta_da_base`, e
/// é ela que faz este programa jogar os finais como o aparelho joga. Um
/// executável da versão 1 ignoraria a chave **em silêncio** e devolveria um
/// lance buscado onde o aparelho responde pela base — exatamente o modo de
/// falha que esta constante existe para impedir.
const int versaoDoProtocolo = 2;

/// Os regulamentos, pelo mesmo identificador que o contrato usa.
///
/// ⚠️ As chaves são as do Python (`REGULAMENTOS` em `regras_damas.py`) e as do
/// banco. Um mapa próprio com outros nomes obrigaria alguém a traduzir no meio,
/// e é no tradutor que a modalidade errada entra sem ninguém ver.
const Map<String, Regulamento> regulamentosPorIdentificador = {
  'brasileira': brasileiras,
  'anglo': angloAmericanas,
  'portuguesa': portuguesas,
  'casa': damasDeCasa,
};

/// As bases de finais já abertas, por pasta e modalidade.
///
/// ⚠️ **Abrir é barato; manter aberto é o que importa.** `doDisco` lê só o
/// manifesto — as fatias ficam fechadas até alguém perguntar por elas, e é a
/// fatia descomprimida que custa. Reabrir a base a cada lance jogaria fora todo
/// o trabalho de descompressão e faria a medição da régua rastejar.
///
/// ⛔ **E o cache não muda lance nenhum.** A base é só leitura e responde sempre
/// o mesmo; o que se reaproveita é o arquivo aberto, nunca um estado de busca.
/// É a mesma fronteira que `MotorDamas` guarda do lado Python: o `Buscador`
/// nasce a cada pedido, a base não.
///
/// O valor `null` guardado é *"esta pasta não tem base utilizável"*, e existe
/// para não tentar de novo a cada lance.
final Map<String, OraculoDeFinais?> _basesAbertas = {};

/// A base daquela pasta e modalidade, ou `null` quando não há.
///
/// ⚠️ **Nunca lança.** Uma base corrompida vira ausência, e a partida corre pela
/// busca — o mesmo tratamento que `_talvezAbrirABase` dá no isolate do app.
/// ⛔ Mas o **servidor** trata a ausência com mais rigor que o aparelho: quem
/// chama daqui (`jogador_dart.py`) exige a base quando o nível a usa, porque um
/// gabarito gerado sem ela descreve outro adversário.
OraculoDeFinais? _baseDeFinais(String? pasta, Regulamento regulamento) {
  if (pasta == null) return null;
  final chave = '$pasta|${regulamento.identificador}';
  return _basesAbertas.putIfAbsent(chave, () {
    try {
      return BaseEmpacotada.doDisco(pasta: pasta, regulamento: regulamento);
    } catch (erro) {
      stderr.writeln('[servidor_de_lances] a base em "$pasta" não abriu: $erro');
      return null;
    }
  });
}

/// Responde a um pedido já decodificado.
///
/// O pedido traz a partida inteira - a posição de onde ela partiu e os lances
/// jogados desde ali - e não só a posição atual.
///
/// ⚠️ **Isso não é desperdício: é o que faz o empate por repetição existir.** Uma
/// posição solta não sabe quantas vezes já apareceu, e o motor que a recebesse
/// jogaria sem enxergar a regra das três repetições. É exatamente o que
/// `EstadoDamas._partida` faz do lado Python, e reproduzir a partida custa menos
/// que um centésimo de uma busca de 288 mil nós.
Map<String, dynamic> responder(Map<String, dynamic> pedido) {
  final modalidade = (pedido['modalidade'] ?? 'brasileira') as String;
  final regulamento = regulamentosPorIdentificador[modalidade];
  if (regulamento == null) {
    return {
      'erro': 'modalidade desconhecida: $modalidade. '
          'O motor conhece: ${regulamentosPorIdentificador.keys.join(", ")}.',
    };
  }

  // ── Reproduz a partida do começo ─────────────────────────────────────────
  var tabuleiro = Tabuleiro.deFen(pedido['fen_inicial'] as String);
  final historico = HistoricoDaPartida.desde(tabuleiro, regulamento);
  final lances = (pedido['lances'] as List?)?.cast<String>() ?? const <String>[];

  for (var i = 0; i < lances.length; i++) {
    // ⚠️ O lance é procurado **entre os legais**, e não interpretado do texto.
    // Um texto que não corresponda a nenhum lance legal simplesmente não
    // existe, e o erro diz em que ponto da sequência a partida se perdeu - é a
    // mesma escolha de `_lance_de_texto` no Python, e é ela que torna o estado
    // autoverificável.
    final legais = gerarLances(tabuleiro, regulamento);
    final escolhido = legais.where((l) => l.toString() == lances[i]);
    if (escolhido.isEmpty) {
      return {
        'erro': 'lance ${i + 1} (${lances[i]}) não é legal em ${tabuleiro.paraFen()}. '
            'Legais: ${legais.map((l) => l.toString()).join(", ")}.',
      };
    }
    final depois = aplicarLance(tabuleiro, escolhido.first);
    historico.registrar(tabuleiro, escolhido.first, depois);
    tabuleiro = depois;
  }

  final legaisAgora = gerarLances(tabuleiro, regulamento);
  if (legaisAgora.isEmpty) {
    return {
      'erro': 'a partida já acabou em ${tabuleiro.paraFen()}: não há lance a escolher.',
    };
  }

  // ── A BASE DECIDE O FINAL, antes de qualquer busca ───────────────────────
  //
  // ⚠️ **Esta ordem é a da tela**, e ela não é detalhe: em `partida_screen.dart`
  // a CPU tenta o atalho de lance único, depois a base, e só então busca. Quando
  // a posição cabe na base não existe "melhor lance provável" - existe **o**
  // lance certo, e ele está gravado.
  //
  // ⛔ **Sem esta consulta o servidor divergiria em todo final de até 4 peças.**
  // Ela é a segunda divergência que a investigação de 25/09/2026 registrou: o
  // aparelho responde pela base (na partida do dono, 795 consultas e 636 acertos
  // num só lance) e o servidor buscava. O diagnóstico está em
  // `arena-sagaz-backend/docs/investigacao_paridade_motores.md`.
  //
  // ⚠️ **O atalho de lance único NÃO é reproduzido aqui, e é indiferente.** Com
  // um lance legal só, a busca devolve esse mesmo lance: o atalho existe no app
  // para não fazer a pessoa esperar, não para mudar a escolha.
  final base = _baseDeFinais(pedido['pasta_da_base'] as String?, regulamento);
  if (base != null) {
    final veredito = consultarBaseDeFinais(
      tabuleiro: tabuleiro,
      lancesLegais: legaisAgora,
      base: base,
    );
    if (veredito != null) {
      return {
        'lance': veredito.lance.toString(),
        'fen_antes': tabuleiro.paraFen(),
        // ⚠️ **Nós, profundidade e nota vão NULOS, e isso é a verdade do dado.**
        // Busca nenhuma houve. É o mesmo que o app grava no log de partidas
        // (`TelemetriaDaBuscaDamas.baseDeFinais`), e inventar um número aqui
        // faria "veio da base" e "buscou raso" ficarem indistinguíveis.
        'nota': null,
        'nos': null,
        'profundidade': null,
        'acertos_na_tabela': null,
        'veio_da_base': true,
        'ms': 0,
      };
    }
  }

  // ── A busca ──────────────────────────────────────────────────────────────
  //
  // ⚠️ Todos os reguladores de força vêm do PEDIDO. `tempo_maximo` ausente (ou
  // nulo) significa **sem relógio**, e é assim que o servidor chama: ele não tem
  // ninguém esperando na tela, e um relógio ali reintroduz precisamente o
  // defeito que este programa existe para fechar - o ponto de parada passaria a
  // depender da carga da máquina, e o mesmo desafio daria lances diferentes em
  // duas execuções.
  //
  // ⚠️ **E a base entra na busca também** (o *probing*, T185 parte 2b): quando um
  // ramo desce até um final resolvido, a busca pergunta em vez de continuar
  // descendo. Ligá-la só na raiz deixaria o servidor buscando sem ela onde o
  // aparelho busca com ela - a mesma divergência, um andar abaixo.
  final buscador = Buscador(
    regulamento: regulamento,
    semente: pedido['semente'] as int?,
    extensaoDeCaptura: (pedido['extensao_de_captura'] as bool?) ?? true,
    baseDeFinais: base,
  );

  final cronometro = Stopwatch()..start();
  final resultado = buscador.buscar(
    tabuleiro,
    profundidade: (pedido['profundidade'] as int?) ?? 64,
    tetoDeNos: pedido['teto_de_nos'] as int?,
    tempoMaximo: (pedido['tempo_maximo'] as num?)?.toDouble(),
    ruido: (pedido['ruido'] as int?) ?? 0,
    historico: historico,
    extensaoDeCaptura: (pedido['extensao_de_captura'] as bool?) ?? true,
    chanceDeErrar: ((pedido['chance_de_errar'] as num?) ?? 0).toDouble(),
    margemDoErro: (pedido['margem_do_erro'] as int?) ?? 200,
  );
  cronometro.stop();

  if (resultado.lance == null) {
    return {'erro': 'a busca não devolveu lance em ${tabuleiro.paraFen()}.'};
  }

  final e = resultado.estatisticas;
  return {
    'lance': resultado.lance.toString(),
    'fen_antes': tabuleiro.paraFen(),
    'nota': resultado.nota,
    // ⚠️ Estes quatro não são enfeite de log: é comparando **nós** e
    // **profundidade** que se descobre que dois motores pararam em pontos
    // diferentes. Foi assim que o defeito de 25/09/2026 apareceu, e sem eles o
    // sintoma teria continuado sendo só "o lance está diferente".
    'nos': e.nos,
    'profundidade': e.profundidadeAtingida,
    'acertos_na_tabela': e.acertosNaTabela,
    // ⚠️ Quantas vezes a busca perguntou à base, e quantas aproveitou. Zero nos
    // dois quando não há base ligada - e é comparando estes números com os do
    // banco (`qt_consultas_base` do log de partidas) que se prova que o servidor
    // e o aparelho enxergaram a mesma base.
    'consultas_base': e.consultasBase,
    'acertos_base': e.acertosBase,
    'veio_da_base': false,
    'ms': cronometro.elapsedMilliseconds,
  };
}

void main(List<String> argumentos) {
  // ⚠️ `utf8.decoder` explícito: sem ele o Dart lê a entrada na codificação do
  // sistema, e no Windows isso é cp1252 - um FEN é ASCII e sobreviveria, mas uma
  // mensagem de erro com acento voltaria corrompida ao Python.
  final linhas = stdin.transform(utf8.decoder).transform(const LineSplitter());

  // A primeira coisa que sai é quem somos. O servidor lê esta linha antes de
  // mandar qualquer pedido, e é ela que impede um backend novo de conversar com
  // um executável antigo sem perceber.
  stdout.writeln(jsonEncode({
    'pronto': true,
    'versao_do_protocolo': versaoDoProtocolo,
    'motor': 'dart',
    // ⚠️ **De que fontes este binário saiu.** O backend compara este resumo com
    // o dos arquivos que ele tem no espelho e RECUSA a conversa se divergirem -
    // é a trava que impede o servidor de gerar gabaritos com um motor velho,
    // depois de alguém corrigir uma regra e esquecer de recompilar.
    'resumo_do_motor': resumoDoMotorDart,
    'arquivos_do_motor': hashesDoMotorDart,
  }));

  linhas.listen((linha) {
    if (linha.trim().isEmpty) return;
    Map<String, dynamic> resposta;
    try {
      final pedido = jsonDecode(linha) as Map<String, dynamic>;
      resposta = responder(pedido);
      // O identificador viaja de volta sem ser interpretado: é o que permite ao
      // servidor casar resposta com pedido sem depender da ordem.
      if (pedido.containsKey('id')) resposta['id'] = pedido['id'];
    } catch (erro) {
      // ⛔ Um pedido malformado NÃO derruba o processo. Derrubar faria a régua
      // inteira parar no meio por causa de uma linha, e o custo de recomeçar é
      // de horas.
      resposta = {'erro': 'pedido inválido: $erro'};
    }
    stdout.writeln(jsonEncode(resposta));
  });
}
