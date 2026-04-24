<!--
SYNC IMPACT REPORT
==================
Versão anterior → nova: (template em branco) → 1.0.0
Princípios adicionados:
  - I. Código Limpo e Legibilidade
  - II. Tipagem Estática com Pydantic (Inegociável)
  - III. Testes Unitários Rigorosos (Inegociável)
  - IV. Documentação Viva
  - V. Idioma: Português do Brasil (Inegociável)
Seções adicionadas:
  - Padrões Técnicos (Stack e Ferramentas)
  - Fluxo de Desenvolvimento e Qualidade
Templates atualizados:
  ✅ .specify/templates/plan-template.md — Constitution Check alinhado
  ✅ .specify/templates/spec-template.md — sem alteração necessária
  ✅ .specify/templates/tasks-template.md — sem alteração necessária
Itens pendentes:
  - Nenhum placeholder deferido
-->

# Arena Sagaz Backend — Constituição do Projeto

## Princípios Fundamentais

### I. Código Limpo e Legibilidade

Todo código produzido neste projeto DEVE seguir os princípios de código limpo:
funções e métodos com responsabilidade única, nomes expressivos que dispensem
explicação extra e ausência de duplicação lógica (DRY). Comentários no
código-fonte DEVEM explicar o *porquê*, nunca o *o quê* — o código em si deve
ser autoexplicativo. Complexidade desnecessária DEVE ser justificada antes de
introduzida.

**Rationale**: Código legível reduz custo de manutenção, facilita onboarding e
diminui a superfície de bugs silenciosos.

### II. Tipagem Estática com Pydantic (Inegociável)

Todo dado que cruza fronteiras de sistema (entrada de API, saída de API,
leitura de banco, configuração de ambiente) DEVE ser modelado com classes
Pydantic (`BaseModel` ou `BaseSettings`). Funções internas DEVEM usar type
hints do Python (`str`, `int`, `list[X]`, `Optional[X]`, etc.) em todos os
parâmetros e retornos. O uso de `Any` DEVE ser evitado; quando imprescindível,
DEVE ser acompanhado de comentário justificando a exceção.

**Rationale**: Tipagem estática com Pydantic garante validação em runtime,
geração automática de documentação OpenAPI pelo FastAPI e detecção precoce de
erros de contrato.

### III. Testes Unitários Rigorosos (Inegociável)

Testes unitários DEVEM ser escritos para toda lógica de negócio não trivial.
A cobertura mínima aceitável é 80 % nas camadas de serviço e domínio. Testes
DEVEM ser independentes entre si, determinísticos e rápidos (< 1 s por teste
unitário). Dependências externas (banco, HTTP externo) DEVEM ser isoladas via
mocks ou fakes. Nenhum código de produção DEVE ser mesclado à branch principal
sem que os testes relevantes passem.

**Rationale**: Testes rigorosos são a rede de segurança que permite refatorações
seguras e previne regressões em produção.

### IV. Documentação Viva

Toda funcionalidade pública (endpoints FastAPI, classes de domínio, funções
utilitárias) DEVE possuir docstring em pt-BR descrevendo seu propósito,
parâmetros e comportamentos especiais. Os arquivos de especificação em
`.specify/` DEVEM ser criados e mantidos atualizados a cada ciclo de
desenvolvimento. O `README.md` DEVE refletir o estado real do projeto
(como executar, como testar, variáveis de ambiente obrigatórias).

**Rationale**: Documentação desatualizada é pior que ausência de documentação —
engana novos colaboradores e gera retrabalho.

### V. Idioma: Português do Brasil (Inegociável)

Toda comunicação no chat, toda documentação gerada na pasta `.specify/`
(arquivos Markdown), todos os comentários no código-fonte, todos os logs do
sistema e todos os nomes de variáveis, funções e classes de domínio DEVEM ser
escritos estritamente em Português do Brasil (pt-BR). O inglês é permitido
**somente** em:

- Palavras reservadas das linguagens de programação (`class`, `def`, `return`,
  `async`, `await`, etc.)
- Identificadores de pacotes ou frameworks de terceiros (`BaseModel`, `FastAPI`,
  `Request`, `Response`, etc.)
- Termos técnicos sem tradução estabelecida e amplamente reconhecida
  (nesses casos, o termo DEVE aparecer entre aspas ou em itálico na primeira
  ocorrência, seguido de sua definição em pt-BR)

**Rationale**: A consistência de idioma elimina ambiguidade, facilita a
colaboração da equipe local e mantém a documentação coesa.

## Padrões Técnicos (Stack e Ferramentas)

A stack técnica oficial deste projeto é:

- **Linguagem**: Python 3.11+
- **Framework web**: FastAPI (última versão estável)
- **Banco de dados**: PostgreSQL (via SQLAlchemy assíncrono + Alembic para
  migrações)
- **Validação e serialização**: Pydantic v2
- **Testes**: pytest + pytest-asyncio + httpx (para testes de integração de API)
- **Linting/formatação**: Ruff (linting) + Black (formatação)
- **Gerenciador de dependências**: uv ou pip com `requirements.txt` versionado

Toda adição de dependência DEVE ser discutida e aprovada antes de introduzida.
Dependências de desenvolvimento DEVEM ser separadas das de produção.

## Fluxo de Desenvolvimento e Qualidade

O ciclo de desenvolvimento DEVE seguir a ordem:

1. **Especificação**: criar ou atualizar `.specify/specs/<feature>/spec.md`
   antes de escrever código.
2. **Testes primeiro**: escrever testes unitários que FALHEM antes de
   implementar a lógica.
3. **Implementação**: fazer os testes passarem com o mínimo de código necessário.
4. **Refatoração**: melhorar legibilidade e estrutura sem quebrar os testes.
5. **Documentação**: atualizar docstrings, README e arquivos `.specify/` se
   necessário.
6. **Revisão**: nenhum PR é mesclado sem revisão de código de pelo menos um
   outro membro da equipe.

Todo pull request DEVE:
- Passar em todos os testes automatizados
- Não reduzir a cobertura de testes abaixo do mínimo definido no Princípio III
- Seguir os padrões de idioma do Princípio V
- Incluir ou atualizar documentação quando a funcionalidade pública for alterada

## Governança

Esta constituição é o documento de referência máxima do projeto e DEVE ser
consultada no início de cada novo ciclo de desenvolvimento. Em caso de
conflito entre esta constituição e qualquer outro documento, a constituição
prevalece.

**Processo de emenda**:
1. Propor a alteração via issue ou discussão em PR dedicado.
2. Descrever o motivo da mudança e o impacto nos princípios existentes.
3. Obter aprovação de pelo menos dois membros seniores da equipe.
4. Atualizar `LAST_AMENDED_DATE` e incrementar `CONSTITUTION_VERSION`
   conforme o tipo de mudança (MAJOR / MINOR / PATCH).
5. Propagar as mudanças nos templates dependentes em `.specify/templates/`.

**Política de versionamento**:
- MAJOR: remoção ou redefinição incompatível de princípio existente.
- MINOR: adição de novo princípio ou seção com orientação materialmente nova.
- PATCH: esclarecimentos, correções de texto, refinamentos não semânticos.

**Revisão de conformidade**: a cada sprint, o responsável técnico DEVE verificar
se os artefatos produzidos estão em conformidade com os princípios desta
constituição. Violações DEVEM ser registradas e corrigidas antes do próximo
ciclo.

---

**Versão**: 1.0.0 | **Ratificada em**: 2026-04-19 | **Última emenda**: 2026-04-19
