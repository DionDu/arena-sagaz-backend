// COMPILA O SERVIDOR DE LANCES E CARIMBA NELE DE QUE CÓDIGO ELE SAIU.
//
// ── O problema que isto resolve ─────────────────────────────────────────────
//
// O servidor de desafios passa a jogar com o motor Dart compilado
// (`servidor_de_lances_damas.exe`). Um executável é opaco: olhando para ele,
// ninguém sabe de que fontes veio. Se alguém corrigir uma regra no motor e
// esquecer de recompilar, o servidor continua gerando gabaritos com o motor
// **antigo** - e o sintoma é o mesmo que custou esta investigação inteira: o
// gabarito não bate com a partida, e nada no dado denuncia.
//
// ⚠️ **É o pedido do dono, em 25/09/2026:** *"Importante também termos algum
// mecanismo que garanta que o motor Dart compilado que vai jogar no servidor
// seja o mesmo embarcado no App."*
//
// ── Como a corrente fecha ───────────────────────────────────────────────────
//
//   app            == laboratório  → `paridade_motor_test.dart`, SHA-256 dos 15
//                                     arquivos de `lib/`, já existia
//   executável     == laboratório  → ESTE programa, que carimba o resumo dos
//                                     mesmos 15 arquivos dentro do binário
//   ───────────────────────────────────────────────────────────────────────
//   logo, executável == app
//
// ⛔ **O carimbo vai para `bin/`, nunca para `lib/`.** Um arquivo novo em `lib/`
// quebraria `paridade_motor_test.dart`, que compara a pasta INTEIRA do
// laboratório com a lista dos 15 - e com razão, porque `lib/` é copiado byte a
// byte para dentro do app.
//
// ── Como rodar ──────────────────────────────────────────────────────────────
//
//   dart run bin/compilar_servidor_de_lances.dart
//
// Roda de novo sempre que um arquivo de `lib/` mudar. O servidor recusa um
// executável cujo carimbo não bata com os fontes, então esquecer não passa
// calado: falha alto, na abertura.

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

/// O SHA-256, em hexadecimal, de cada arquivo `.dart` de `lib/`, por nome.
///
/// ⚠️ Lê em **bytes** (`readAsBytesSync`), e não como texto: ler como texto
/// passaria pela tradução de fim de linha do Windows, e o resumo descreveria um
/// arquivo que não está no disco. É a mesma nota de `job/perfil.py` no backend,
/// pelo mesmo motivo.
Map<String, String> hashesDosFontes(Directory lib) {
  final arquivos = lib
      .listSync()
      .whereType<File>()
      .where((f) => f.path.endsWith('.dart'))
      .toList()
    // Ordem alfabética, e não a do sistema de arquivos: sem isto o mesmo
    // conjunto de arquivos daria resumos diferentes em máquinas diferentes.
    ..sort((a, b) => a.path.compareTo(b.path));

  return {
    for (final arquivo in arquivos)
      arquivo.uri.pathSegments.last:
          sha256.convert(arquivo.readAsBytesSync()).toString(),
  };
}

/// O resumo do conjunto: um hash dos hashes.
///
/// ⚠️ **Resume a LISTA, e não um arquivo concatenado.** Assim o resumo muda
/// quando um arquivo é renomeado ou removido, e não só quando o conteúdo muda -
/// um motor a que falte um arquivo é outro motor.
String resumoDoConjunto(Map<String, String> hashes) {
  final material = hashes.entries.map((e) => '${e.key}:${e.value}').join('\n');
  return sha256.convert(utf8.encode(material)).toString();
}

void main(List<String> argumentos) {
  final raiz = Directory.current;
  final lib = Directory('${raiz.path}/lib');
  if (!lib.existsSync()) {
    stderr.writeln(
      '⛔ rode a partir da raiz do pacote `motor_dart` (não achei `lib/`).',
    );
    exit(2);
  }

  final hashes = hashesDosFontes(lib);
  final resumo = resumoDoConjunto(hashes);
  print('${hashes.length} arquivo(s) em lib/ · resumo ${resumo.substring(0, 16)}');

  // ── O carimbo, como código gerado ────────────────────────────────────────
  //
  // ⚠️ Gerar um arquivo Dart (e não ler um JSON em runtime) é de propósito: o
  // resumo fica DENTRO do binário. Um JSON ao lado poderia ser trocado, perdido
  // na cópia para outra máquina, ou ficar para trás - e aí o executável
  // afirmaria, com toda a confiança, ter saído de um código que não é o dele.
  final gerado = File('${raiz.path}/bin/_resumo_do_motor.g.dart');
  gerado.writeAsStringSync('''
// ⛔ ARQUIVO GERADO por `bin/compilar_servidor_de_lances.dart`. Não edite.
//
// Ele carimba, dentro do executável, o SHA-256 dos arquivos de `lib/` com que
// aquele binário foi compilado. O backend confere na abertura e recusa um
// executável que não corresponda aos fontes do espelho.

/// O resumo dos ${hashes.length} arquivos de `lib/` no momento da compilação.
const String resumoDoMotorDart = '$resumo';

/// Os arquivos e seus hashes, para o erro dizer QUAL divergiu.
const Map<String, String> hashesDoMotorDart = {
${hashes.entries.map((e) => "  '${e.key}': '${e.value}',").join('\n')}
};
''');
  print('carimbo gravado em bin/_resumo_do_motor.g.dart');

  // ── A compilação ─────────────────────────────────────────────────────────
  final alvo = Platform.isWindows
      ? 'bin/servidor_de_lances_damas.exe'
      : 'bin/servidor_de_lances_damas';
  print('compilando $alvo ...');
  final r = Process.runSync(
    Platform.resolvedExecutable, // o próprio `dart` que está rodando
    ['compile', 'exe', 'bin/servidor_de_lances_damas.dart', '-o', alvo],
    workingDirectory: raiz.path,
  );
  stdout.write(r.stdout);
  stderr.write(r.stderr);
  if (r.exitCode != 0) exit(r.exitCode);

  print('✅ pronto. O executável carrega o resumo ${resumo.substring(0, 16)}.');
}
