// COMPILA o servidor de lances do Quatro em Linha, CARIMBANDO de que fontes
// ele saiu (T102, no molde do Pontinhos).
//
//   dart run bin/compilar_servidor_de_lances_quatro.dart
//
// ── Por que carimbar ────────────────────────────────────────────────────────
//
// O executável é um ARTEFATO: ele sai dos arquivos de `lib/` de um instante, e
// continua no disco depois que esses arquivos mudam. Sem carimbo, alguém corrige
// a política, esquece de recompilar, e o servidor passa a gerar gabaritos com o
// motor velho - lances plausíveis, que a pessoa não consegue seguir no aparelho.
//
// O carimbo é o SHA-256 de cada arquivo de `lib/` e o resumo do conjunto,
// escritos num arquivo Dart gerado (`bin/_resumo_do_motor_quatro.g.dart`) que
// entra DENTRO do binário. O servidor de lances o anuncia na abertura, e o
// backend (`motores/nucleo/processo_dart.py`) recalcula o mesmo resumo a partir
// do espelho e recusa a conversa se divergir.
//
// ⚠️ Rode de novo sempre que `lib/` mudar. Esquecer não passa calado: falha
// alto, na abertura, nomeando o arquivo que divergiu.

import 'dart:convert';
import 'dart:io';

// O `crypto` é dependência de DESENVOLVIMENTO de propósito (`pubspec.yaml`):
// o que viaja para o app são os arquivos de `lib/`, que não o usam; `bin/`
// fica no laboratório e no servidor. Daí o aviso calado.
// ignore: depend_on_referenced_packages
import 'package:crypto/crypto.dart';

/// O SHA-256, em hexadecimal, de cada arquivo `.dart` da pasta [lib], por nome.
///
/// ⚠️ Lê em **bytes** (`readAsBytesSync`), e não como texto: ler como texto
/// passaria pela tradução de fim de linha do Windows, e o resumo descreveria um
/// arquivo que não está no disco.
Map<String, String> hashesDosFontes(Directory lib) {
  final arquivos = lib
      .listSync()
      .whereType<File>()
      .where((f) => f.path.endsWith('.dart'))
      .toList()
    // Ordem alfabética do NOME, e não a do sistema de arquivos: sem isto o
    // mesmo conjunto daria resumos diferentes em máquinas diferentes. É a
    // ordem do `sorted(..., key=lambda a: a.name)` do lado Python.
    ..sort((a, b) => a.uri.pathSegments.last.compareTo(b.uri.pathSegments.last));

  return {
    for (final arquivo in arquivos)
      arquivo.uri.pathSegments.last:
          sha256.convert(arquivo.readAsBytesSync()).toString(),
  };
}

/// O resumo do conjunto: um hash dos hashes, linha `nome:hash` por arquivo.
///
/// ⚠️ **Resume a LISTA, e não um arquivo concatenado.** Assim o resumo muda
/// quando um arquivo é renomeado ou removido, e não só quando o conteúdo muda -
/// um motor a que falte um arquivo é outro motor. ⚠️ É a MESMA fórmula de
/// `resumo_dos_fontes` em `motores/nucleo/processo_dart.py`, e o teste deste
/// compilador confere as duas com um conjunto calculado pelo Python.
String resumoDoConjunto(Map<String, String> hashes) {
  final material = hashes.entries.map((e) => '${e.key}:${e.value}').join('\n');
  return sha256.convert(utf8.encode(material)).toString();
}

/// O texto do arquivo gerado com o carimbo.
///
/// ⚠️ Gerar um arquivo Dart (e não ler um JSON em tempo de execução) é de
/// propósito: o resumo fica DENTRO do binário. Um JSON ao lado poderia ser
/// trocado, perdido na cópia para outra máquina, ou ficar para trás - e aí o
/// executável afirmaria, com toda a confiança, ter saído de um código que não
/// é o dele.
String textoDoCarimbo(Map<String, String> hashes) => '''
// ⛔ ARQUIVO GERADO por `bin/compilar_servidor_de_lances_quatro.dart`.
// Não edite.
//
// Ele carimba, dentro do executável, o SHA-256 dos arquivos de `lib/` com que
// aquele binário foi compilado. O backend confere na abertura e recusa um
// executável que não corresponda aos fontes do espelho.

/// O resumo dos ${hashes.length} arquivos de `lib/` no momento da compilação.
const String resumoDoMotorQuatro =
    '${resumoDoConjunto(hashes)}';

/// Os arquivos e seus hashes, para o erro dizer QUAL divergiu.
const Map<String, String> hashesDoMotorQuatro = {
${hashes.entries.map((e) => "  '${e.key}':\n      '${e.value}',").join('\n')}
};
''';

void main(List<String> argumentos) {
  final raiz = Directory.current;
  final lib = Directory('${raiz.path}/lib');
  if (!lib.existsSync()) {
    stderr.writeln(
      '⛔ rode a partir da raiz do pacote `motor_dart` do Quatro em Linha '
      '(não achei `lib/`).',
    );
    exit(2);
  }

  final hashes = hashesDosFontes(lib);
  final resumo = resumoDoConjunto(hashes);
  print('${hashes.length} arquivo(s) em lib/ · resumo ${resumo.substring(0, 16)}');

  File('${raiz.path}/bin/_resumo_do_motor_quatro.g.dart')
      .writeAsStringSync(textoDoCarimbo(hashes));
  print('carimbo gravado em bin/_resumo_do_motor_quatro.g.dart');

  // ── A compilação ─────────────────────────────────────────────────────────
  //
  // No Windows o binário leva `.exe`; no Linux da imagem do job, não. O backend
  // procura pelos dois nomes (`caminho_do_executavel`).
  final alvo = Platform.isWindows
      ? 'bin/servidor_de_lances_quatro.exe'
      : 'bin/servidor_de_lances_quatro';
  print('compilando $alvo ...');
  final r = Process.runSync(
    Platform.resolvedExecutable, // o próprio `dart` que está rodando
    ['compile', 'exe', 'bin/servidor_de_lances_quatro.dart', '-o', alvo],
    workingDirectory: raiz.path,
  );
  stdout.write(r.stdout);
  stderr.write(r.stderr);
  if (r.exitCode != 0) exit(r.exitCode);

  print('✅ pronto. O executável carrega o resumo ${resumo.substring(0, 16)}.');
}
