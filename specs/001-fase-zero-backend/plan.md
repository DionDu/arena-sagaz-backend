# Plano de Implementação: Backend Arena Sagaz — Fase Zero e Infraestrutura de Dados

**Branch**: `001-fase-zero-backend` | **Data**: 2026-04-19 | **Spec**: [spec.md](spec.md)
**Entrada**: Especificação de feature em `specs/001-fase-zero-backend/spec.md`

---

## Resumo

Construção do backend completo do Arena Sagaz em duas frentes paralelas:

1. **Fase Zero (P1 — urgência máxima)**: Scripts Python para geração de 150.000
   registros de treinamento (50k × 3 tamanhos de tabuleiro) via Minimax com Poda
   Alpha-Beta, função de abstração visual Matriz→PNG e simulador tático em Pygame
   para validação empírica da CNN treinada.

2. **Infraestrutura de Produto (P2)**: API REST FastAPI com autenticação JWT,
   sincronização de partidas, ranking e observabilidade, hospedada no Railway com
   PostgreSQL gerenciado.

---

## Contexto Técnico

**Linguagem/Versão**: Python 3.11+
**Dependências Principais**:
- API: FastAPI, SQLAlchemy (async), Alembic, Pydantic v2, python-jose, bcrypt, asyncpg
- Fase Zero: NumPy, Matplotlib, pygame-ce, tflite-runtime (Nota Speckit/Claude: pygame-ce resolve erros de build, tflite-runtime comentado devido a suporte no python 3.14)
- Testes: pytest, pytest-asyncio, httpx, pytest-cov

**Armazenamento**: PostgreSQL 15 (Railway gerenciado em produção; Docker local em desenvolvimento)
**Testes**: pytest + pytest-asyncio + httpx
**Plataforma Alvo**: Linux (Railway PaaS) + desktop local (scripts Fase Zero)
**Tipo de Projeto**: web-service + scripts CLI
**Metas de Performance**: 500 requisições simultâneas; CNN < 1s de resposta no tabuleiro Pequeno
**Restrições**: Modelo exportado < 50 MB; geração do dataset Pequeno < 24h (CPU only)
**Escala/Escopo**: TCC; escala inicial de ~1.000 usuários ativos

---

## Verificação da Constituição

*PORTÃO: Aprovado antes da Fase 0 de pesquisa. Revalidado após design da Fase 1.*

- [x] **I. Código Limpo**: cada módulo tem responsabilidade única
  (gerador / minimax / tabuleiro / api / auth / partidas / ranking)
- [x] **II. Tipagem Estática**: Pydantic v2 em todos os esquemas de API;
  type hints em todas as funções públicas dos módulos de domínio
- [x] **III. Testes Unitários**: planejados para `minimax.py`, `tabuleiro.py`,
  cálculo de XP em `partidas/servico.py` e geração de JWT em `nucleo/seguranca.py`;
  mocks para repositório nos testes unitários; banco real nos de integração
- [x] **IV. Documentação**: `research.md`, `data-model.md`, `contracts/api-v1.md`,
  `quickstart.md` gerados; docstrings em pt-BR em todos os módulos públicos
- [x] **V. Idioma pt-BR**: todos os nomes de domínio, comentários, logs e
  documentação em Português do Brasil

---

## Estrutura de Documentação (esta feature)

```text
specs/001-fase-zero-backend/
├── plan.md              # Este arquivo
├── spec.md              # Especificação da feature
├── research.md          # Pesquisa técnica e decisões de arquitetura
├── data-model.md        # Esquema do banco + modelos de dados
├── quickstart.md        # Guia de setup e execução
├── contracts/
│   └── api-v1.md        # Contratos dos endpoints REST
├── checklists/
│   └── requirements.md  # Checklist de qualidade da spec
└── tasks.md             # Gerado por /speckit-tasks (próxima etapa)
```

---

## Estrutura do Código-Fonte

```text
arena-sagaz-backend/
├── api/
│   ├── main.py                  # App FastAPI + registro de routers
│   ├── configuracao.py          # Pydantic BaseSettings (variáveis de ambiente)
│   ├── banco/
│   │   ├── conexao.py           # Engine SQLAlchemy async + sessão
│   │   └── migrations/          # Alembic: env.py + versões
│   ├── auth/
│   │   ├── rotas.py             # POST /v1/auth/login, /refresh, /logout
│   │   ├── esquemas.py          # Pydantic: LoginEntrada, TokenSaida
│   │   └── servico.py           # Lógica de autenticação e geração de tokens
│   ├── usuarios/
│   │   ├── modelo.py            # SQLAlchemy: Usuario, TokenRefresh
│   │   ├── rotas.py             # POST /v1/usuarios, GET /v1/usuarios/eu
│   │   ├── esquemas.py          # Pydantic: CriarUsuarioEntrada, UsuarioSaida
│   │   └── servico.py           # Criação de conta, validações
│   ├── partidas/
│   │   ├── modelo.py            # SQLAlchemy: Partida
│   │   ├── rotas.py             # POST /v1/partidas
│   │   ├── esquemas.py          # Pydantic: SincronizarPartidaEntrada, PartidaSaida
│   │   └── servico.py           # Cálculo de XP, atualização de ranking
│   ├── ranking/
│   │   ├── modelo.py            # SQLAlchemy: Ranking
│   │   ├── rotas.py             # GET /v1/ranking
│   │   ├── esquemas.py          # Pydantic: EntradaRankingSaida
│   │   └── servico.py           # Consulta paginada de ranking
│   ├── trofeus/
│   │   └── modelo.py            # SQLAlchemy: Trofeu, UsuarioTrofeu
│   └── nucleo/
│       ├── seguranca.py         # JWT (python-jose) + bcrypt
│       ├── log.py               # Logging estruturado JSON
│       ├── excecoes.py          # Exceções de domínio + handlers FastAPI
│       └── dependencias.py      # Dependências FastAPI (get_sessao, usuario_atual)
├── gerador_dados/
│   ├── gerador.py               # CLI: --tamanho, --total, --profundidade, --retomar
│   ├── minimax.py               # Minimax + Poda Alpha-Beta (recursivo)
│   ├── tabuleiro.py             # EstadoTabuleiro: geração, traços, caixas
│   ├── visualizador.py          # matriz_para_png(), lote_para_png()
│   └── simulador/
│       └── simulador_tatico.py  # Pygame: grade interativa, CNN vs Minimax
├── tests/
│   ├── conftest.py              # Fixtures: banco de testes, cliente HTTP
│   ├── unitarios/
│   │   ├── test_minimax.py
│   │   ├── test_tabuleiro.py
│   │   ├── test_visualizador.py
│   │   ├── test_seguranca.py
│   │   └── test_xp.py
│   └── integracao/
│       ├── test_auth.py
│       ├── test_usuarios.py
│       ├── test_partidas.py
│       ├── test_ranking.py
│       └── test_health.py
├── sql/
│   ├── 001_trofeus_iniciais.sql
│   └── 002_selos_iniciais.sql
├── dados/                       # Dataset gerado (gitignored)
├── modelos/                     # Modelos .tflite (gitignored)
├── .env.example
├── .gitignore
├── railway.json
├── Dockerfile
├── alembic.ini
└── requirements.txt
```

**Decisão de Estrutura**: Projeto único com separação por domínio dentro de `api/`
e módulos independentes em `gerador_dados/`. Essa separação permite executar os
scripts da Fase Zero sem inicializar a API, e testar cada domínio da API de forma
isolada.

---

## Rastreamento de Complexidade

> Nenhuma violação da Constituição identificada. Seção não aplicável.
