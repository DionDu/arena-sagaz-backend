<!--
SYNC IMPACT REPORT
==================
Versão anterior → nova: 1.0.0 → 2.0.0
Motivo do bump MAJOR:
  - Escopo expandido de backend exclusivo para projeto full-stack
    (backend Python/FastAPI + frontend Flutter/Dart)
  - Princípio II redefinido: "Tipagem com Pydantic (backend)" →
    "Tipagem Estática (Python + Dart)" — mudança incompatível de escopo
  - Dois novos princípios adicionados (IV e VII)
Princípios modificados:
  - I. Código Limpo e Legibilidade →
       I. Código Limpo, Legível e Comentado (requisito de comentários detalhados)
  - II. Tipagem Estática com Pydantic (backend) →
       II. Tipagem Estática (Python + Dart) — cobre ambas as plataformas
  - III. Testes Unitários Rigorosos →
       III. Testes Automatizados Rigorosos (cobre backend e frontend)
  - V. Documentação Viva — expandida com decisões arquiteturais
  - VI. Idioma: Português do Brasil — expandido com exemplos de termos Flutter
Princípios adicionados:
  - IV. Segurança e Privacidade de Dados (novo)
  - VII. Proteção de Artefatos SpecKit (novo)
Seções modificadas:
  - Padrões Técnicos: adicionada stack do frontend Flutter e regras comuns
  - Fluxo de Desenvolvimento: adicionada etapa de verificação SpecKit (1ª etapa)
  - Governança: adicionada política de sincronização entre os dois projetos
Templates verificados:
  ✅ .specify/templates/plan-template.md — Constitution Check é preenchido em
     runtime pelo /speckit-plan a partir deste arquivo; sem alteração necessária
  ✅ .specify/templates/spec-template.md — sem alteração necessária
  ✅ .specify/templates/tasks-template.md — sem alteração necessária
Itens pendentes:
  - Nenhum placeholder deferido
-->

# Arena Sagaz — Constituição do Projeto

**Escopo**: Backend Python/FastAPI (`arena-sagaz-backend`) e
Frontend Flutter/Dart (`arena-sagaz-frontend`)

## Princípios Fundamentais

### I. Código Limpo, Legível e Comentado

Todo código produzido neste projeto DEVE seguir os princípios de código limpo:
funções e métodos com responsabilidade única, nomes expressivos que dispensem
explicação extra e ausência de duplicação lógica (DRY).

Comentários no código-fonte DEVEM:

- Explicar o **porquê** de uma decisão e as alternativas rejeitadas, nunca
  apenas o *o quê* (o que o código faz já está evidente no código em si).
- Ser suficientemente detalhados para que alguém sem profundo conhecimento de
  Python, Flutter ou Dart consiga compreender a lógica e as escolhas feitas.
- Documentar invariantes não óbvias, restrições do domínio, *workarounds* e
  armadilhas conhecidas.

Complexidade desnecessária DEVE ser justificada antes de introduzida.

**Rationale**: Código bem comentado reduz o custo de manutenção, facilita a
entrada de novos colaboradores e diminui a superfície de bugs silenciosos —
especialmente em projetos que combinam múltiplas tecnologias como Python e Dart.

### II. Tipagem Estática (Inegociável)

**Backend (Python)**:
Todo dado que cruza fronteiras de sistema (entrada de API, saída de API,
leitura de banco, configuração de ambiente) DEVE ser modelado com classes
Pydantic (`BaseModel` ou `BaseSettings`). Funções internas DEVEM usar type
hints do Python (`str`, `int`, `list[X]`, `Optional[X]`, etc.) em todos os
parâmetros e retornos. O uso de `Any` DEVE ser evitado; quando imprescindível,
DEVE ser acompanhado de comentário justificando a exceção.

**Frontend (Dart/Flutter)**:
Toda variável, parâmetro e retorno de função DEVE ter tipo explícito declarado.
O uso de `dynamic` é proibido salvo em integrações com código externo que não
forneça tipagem (nesses casos, o uso DEVE ser isolado e acompanhado de
comentário). Classes de modelo de dados DEVEM ser imutáveis sempre que possível
(usar `final` nos campos e `const` nos construtores).

**Rationale**: Tipagem estática detecta erros em tempo de compilação e/ou
análise estática, antes de chegarem ao usuário. No backend, Pydantic garante
validação em *runtime* e documentação OpenAPI automática. No frontend, a
tipagem forte do Dart previne erros de categoria e facilita o *refactoring*.

### III. Testes Automatizados Rigorosos (Inegociável)

Testes automatizados DEVEM ser escritos para toda lógica de negócio não
trivial, em ambas as plataformas.

**Backend (Python)**:
- Cobertura mínima de 80 % nas camadas de serviço e domínio.
- Dependências externas (banco, HTTP externo, modelo de IA) DEVEM ser isoladas
  via *mocks* ou *fakes* nos testes unitários.
- Testes de integração DEVEM validar os contratos de API.

**Frontend (Flutter/Dart)**:
- Toda lógica dentro de Providers, serviços e classes de domínio DEVE ter
  testes de unidade (`flutter test`).
- *Widgets* críticos DEVEM ter testes de *widget* validando o comportamento.
- Testes de integração DEVEM cobrir os fluxos principais (*golden paths*).

**Regra universal**:
- Testes DEVEM ser independentes entre si, determinísticos e rápidos
  (< 1 s por teste unitário).
- Testes DEVEM ser executados **sempre** ao validar uma funcionalidade
  implementada ou ajustada — nunca considere uma tarefa concluída sem que os
  testes relevantes passem.
- Nenhum código de produção DEVE ser mesclado à branch principal sem que os
  testes relevantes passem.

**Rationale**: Testes rigorosos são a rede de segurança que permite
refatorações seguras e previne regressões. Em um hub de jogos com lógica de IA
e regras de jogo complexas, a cobertura de testes é crítica para a confiança
nas entregas.

### IV. Segurança e Privacidade de Dados

Segurança e privacidade DEVEM ser consideradas em toda decisão de design e
implementação, desde o início (não como um passo final de revisão).

**Dados pessoais**:
- Dados pessoais de usuários (nome, e-mail, dados de jogo vinculados ao
  usuário) DEVEM ser tratados com o menor privilégio necessário.
- NUNCA registre (*log*) dados pessoais, tokens de autenticação ou senhas.
- Dados pessoais em trânsito DEVEM ser protegidos via HTTPS/TLS.
- A coleta de dados DEVE ser mínima — coletar apenas o estritamente necessário
  para a funcionalidade.

**Credenciais e segredos**:
- NUNCA inclua credenciais, chaves de API, senhas ou tokens em código-fonte
  ou em arquivos rastreados pelo Git.
- Segredos DEVEM ser gerenciados via variáveis de ambiente (arquivo `.env`
  local, nunca versionado) ou serviços dedicados de gestão de segredos.

**Código seguro**:
- Toda entrada de usuário DEVE ser validada antes de ser processada.
- Evite construção dinâmica de *queries* ou comandos a partir de entrada do
  usuário (risco de SQL *injection*, *command injection*).
- Dependências DEVEM ser mantidas atualizadas para incorporar correções de
  segurança.

**Rationale**: A privacidade dos dados dos usuários é um compromisso ético e
legal (LGPD — Lei Geral de Proteção de Dados). Incidentes de segurança
prejudicam a confiança dos usuários e podem ter consequências legais e
financeiras graves.

### V. Documentação Viva

**Backend**: Toda funcionalidade pública (endpoints FastAPI, classes de
domínio, funções utilitárias) DEVE possuir *docstring* em pt-BR descrevendo
seu propósito, parâmetros e comportamentos especiais.

**Frontend**: Toda classe de domínio, Provider e função utilitária DEVE
possuir comentário de documentação descrevendo seu propósito.

**Artefatos SpecKit**: Os arquivos de especificação em `.specify/` DEVEM ser
criados e mantidos atualizados a cada ciclo de desenvolvimento.

**README**: O `README.md` de cada projeto DEVE refletir o estado real do
projeto (como executar, como testar, variáveis de ambiente obrigatórias).

**Decisões arquiteturais**: Toda decisão arquitetural, mudança de rota técnica
ou alteração de formato de dados DEVE ser documentada na mesma resposta em que
a mudança é feita. Não existe "documento depois".

**Rationale**: Documentação desatualizada é pior que ausência de documentação
— engana novos colaboradores e gera retrabalho. Decisões não documentadas se
perdem e se repetem desnecessariamente.

### VI. Idioma: Português do Brasil (Inegociável)

Toda comunicação no chat, toda documentação gerada na pasta `.specify/`
(arquivos Markdown), todos os comentários no código-fonte, todos os logs do
sistema e todos os nomes de variáveis, funções e classes de domínio DEVEM ser
escritos estritamente em Português do Brasil (pt-BR). O inglês é permitido
**somente** em:

- Palavras reservadas das linguagens de programação (`class`, `def`, `return`,
  `async`, `await`, `widget`, `build`, `final`, etc.)
- Identificadores de pacotes ou *frameworks* de terceiros (`BaseModel`,
  `FastAPI`, `Provider`, `Widget`, `BuildContext`, `ChangeNotifier`, etc.)
- Termos técnicos sem tradução estabelecida e amplamente reconhecida na
  comunidade de desenvolvimento (nesses casos, o termo DEVE aparecer entre
  aspas ou em itálico na primeira ocorrência, seguido de sua definição em
  pt-BR — exemplos: *provider*, *widget*, *endpoint*, *mock*, *refactoring*,
  *build*)

**Rationale**: A consistência de idioma elimina ambiguidade, facilita a
colaboração da equipe local e mantém a documentação coesa.

### VII. Proteção de Artefatos SpecKit (Inegociável)

Antes de executar qualquer comando SpecKit (`/speckit-specify`,
`/speckit-plan`, `/speckit-tasks`, `/speckit-clarify`, etc.), DEVE-SE
verificar se o artefato correspondente já existe no diretório da feature
(`.specify/specs/<feature>/`).

**Regras**:
- Se `spec.md` já existir: NÃO executar `/speckit-specify` sem autorização
  explícita do usuário para sobrescrever.
- Se `plan.md` já existir: NÃO executar `/speckit-plan` sem autorização
  explícita do usuário para sobrescrever.
- Se `tasks.md` já existir: NÃO executar `/speckit-tasks` sem autorização
  explícita do usuário para sobrescrever.
- Quando um artefato existente for detectado, DEVE-SE informar o usuário,
  mostrar o que existe e perguntar se deseja substituir, atualizar
  incrementalmente ou cancelar.

**Rationale**: Comandos SpecKit executados sem verificação prévia sobrescrevem
artefatos de especificação elaborados com templates em branco, causando perda
irreversível de trabalho. Este princípio foi adicionado após incidente real de
perda de spec, plan e tasks no projeto.

## Padrões Técnicos (Stack e Ferramentas)

### Backend (arena-sagaz-backend)

- **Linguagem**: Python 3.11+
- **Framework web**: FastAPI (última versão estável)
- **Banco de dados**: PostgreSQL (via SQLAlchemy assíncrono + Alembic para
  migrações)
- **Validação e serialização**: Pydantic v2
- **Testes**: pytest + pytest-asyncio + httpx (para testes de integração de
  API)
- **Linting/formatação**: Ruff (*linting*) + Black (formatação)
- **Gerenciador de dependências**: uv ou pip com `requirements.txt` versionado

### Frontend (arena-sagaz-frontend)

- **Linguagem**: Dart (versão compatível com Flutter estável)
- **Framework**: Flutter (última versão estável)
- **Gerenciamento de estado**: Provider (pacote `provider` — padrão oficial
  adotado neste projeto; NÃO introduzir Riverpod, Bloc ou GetX sem decisão
  arquitetural documentada e aprovada)
- **Testes**: `flutter test` (unitário e *widget*) + `integration_test`
- **Linting**: `flutter analyze` + regras definidas em
  `analysis_options.yaml`
- **Formatação**: `dart format`

### Regras Comuns às Duas Plataformas

- Toda adição de dependência DEVE ser discutida e aprovada antes de
  introduzida.
- Dependências de desenvolvimento DEVEM ser separadas das de produção.
- O projeto Arena Sagaz é um **hub de jogos** — o Jogo dos Pontinhos é o
  primeiro, não o único. Todo arquivo específico de um jogo DEVE ficar na
  pasta do jogo ou ter o nome do jogo no nome do arquivo. Pastas genéricas
  compartilhadas entre jogos são proibidas para conteúdo específico de jogo.

## Fluxo de Desenvolvimento e Qualidade

O ciclo de desenvolvimento DEVE seguir a ordem:

1. **Verificação SpecKit**: antes de executar qualquer comando SpecKit,
   verificar se os artefatos correspondentes já existem (ver Princípio VII).
2. **Especificação**: criar ou atualizar `.specify/specs/<feature>/spec.md`
   antes de escrever código.
3. **Testes primeiro**: escrever testes que FALHEM antes de implementar a
   lógica (TDD — *Test-Driven Development*, desenvolvimento guiado por testes).
4. **Implementação**: fazer os testes passarem com o mínimo de código
   necessário.
5. **Refatoração**: melhorar legibilidade e estrutura sem quebrar os testes.
6. **Documentação**: atualizar *docstrings*, comentários, README e arquivos
   `.specify/` se necessário.
7. **Validação**: executar a suíte de testes completa para confirmar que
   nada foi quebrado.
8. **Revisão**: nenhum PR é mesclado sem revisão de código.

Todo *pull request* DEVE:
- Passar em todos os testes automatizados
- Não reduzir a cobertura de testes abaixo do mínimo definido no Princípio III
- Seguir os padrões de idioma do Princípio VI
- Incluir ou atualizar documentação quando a funcionalidade pública for
  alterada
- Não introduzir dados pessoais ou credenciais em código ou arquivos
  rastreados pelo Git

## Governança

Esta constituição é o documento de referência máxima do projeto e DEVE ser
consultada no início de cada novo ciclo de desenvolvimento. Em caso de conflito
entre esta constituição e qualquer outro documento, a constituição prevalece.

**Processo de emenda**:
1. Propor a alteração via *issue* ou discussão em PR dedicado.
2. Descrever o motivo da mudança e o impacto nos princípios existentes.
3. Obter aprovação de pelo menos dois membros seniores da equipe.
4. Atualizar `LAST_AMENDED_DATE` e incrementar `CONSTITUTION_VERSION`
   conforme o tipo de mudança (MAJOR / MINOR / PATCH).
5. Propagar as mudanças nos templates dependentes em `.specify/templates/`.
6. **Copiar o constitution atualizado para ambos os projetos** (backend e
   frontend) na mesma operação — nunca deixar as cópias divergirem.

**Política de versionamento**:
- MAJOR: remoção ou redefinição incompatível de princípio existente, ou
  mudança de escopo do documento.
- MINOR: adição de novo princípio ou seção com orientação materialmente nova.
- PATCH: esclarecimentos, correções de texto, refinamentos não semânticos.

**Política de sincronização**:
Este documento DEVE existir e ser **idêntico** em ambos os projetos:
- `arena-sagaz-backend/.specify/memory/constitution.md`
- `arena-sagaz-frontend/.specify/memory/constitution.md`

Toda emenda DEVE ser aplicada simultaneamente nos dois arquivos.

**Revisão de conformidade**: a cada *sprint*, o responsável técnico DEVE
verificar se os artefatos produzidos estão em conformidade com os princípios
desta constituição. Violações DEVEM ser registradas e corrigidas antes do
próximo ciclo.

---

**Versão**: 2.0.0 | **Ratificada em**: 2026-04-19 | **Última emenda**: 2026-06-27

