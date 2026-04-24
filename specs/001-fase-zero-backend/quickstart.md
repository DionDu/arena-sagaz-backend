# Guia de Início Rápido — Backend Arena Sagaz

**Branch**: `001-fase-zero-backend` | **Data**: 2026-04-19

---

## Pré-Requisitos

- Python 3.11+
- PostgreSQL 15+ (local ou Docker)
- `uv` ou `pip` para gerenciamento de dependências
- Docker (opcional, para banco local em contêiner)

---

## 1. Configuração do Ambiente

```bash
# Clonar e entrar no repositório
git clone <url-do-repositorio>
cd arena-sagaz-backend

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
# Ou com uv:
uv sync
```

---

## 2. Variáveis de Ambiente

Copie o arquivo de exemplo e ajuste os valores:

```bash
cp .env.example .env
```

Conteúdo mínimo do `.env`:

```env
# Banco de Dados
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/arena_sagaz

# JWT
JWT_SECRET=sua-chave-secreta-aqui-minimo-32-chars
JWT_EXPIRACAO_MINUTOS=60
REFRESH_TOKEN_EXPIRACAO_DIAS=30

# XP
XP_BONUS_VITORIA=20

# App
AMBIENTE=desenvolvimento
```

---

## 3. Banco de Dados Local (Docker)

```bash
# Subir PostgreSQL em contêiner
docker run --name arena-sagaz-db \
  -e POSTGRES_USER=arena \
  -e POSTGRES_PASSWORD=arena123 \
  -e POSTGRES_DB=arena_sagaz \
  -p 5432:5432 \
  -d postgres:15

# Executar migrações Alembic
alembic upgrade head

# Carregar dados iniciais (troféus/selos)
psql -h localhost -U arena -d arena_sagaz -f sql/001_trofeus_iniciais.sql
psql -h localhost -U arena -d arena_sagaz -f sql/002_selos_iniciais.sql
```

---

## 4. Executar a API

```bash
# Modo desenvolvimento (hot reload)
uvicorn api.main:app --reload --port 8000

# Verificar que está funcionando
curl http://localhost:8000/v1/health
# Esperado: {"status": "ok", "banco_de_dados": "ok", "versao": "1.0.0"}
```

Documentação interativa disponível em: `http://localhost:8000/docs`

---

## 5. Executar os Testes

```bash
# Testes unitários (sem banco)
pytest tests/unitarios/ -v

# Testes de integração (requer banco rodando)
pytest tests/integracao/ -v

# Cobertura completa
pytest --cov=api --cov=gerador_dados --cov-report=term-missing
```

---

## 6. Fase Zero — Gerador de Dados

```bash
# Gerar dataset para tabuleiro Pequeno (3x4) — usa multiprocessing automático
python -m gerador_dados.gerador --tamanho pequeno --total 50000

# Gerar com profundidade personalizada
python -m gerador_dados.gerador --tamanho grande --total 50000 --profundidade 9

# Retomar geração interrompida (checkpoint automático)
python -m gerador_dados.gerador --tamanho medio --total 50000 --retomar

# Verificar progresso de uma geração em andamento
cat dados/checkpoint_medio.json
```

Os arquivos gerados ficam em `dados/` por padrão:
```
dados/
├── checkpoint_pequeno.json
├── dataset_pequeno_0001.npz
├── dataset_pequeno_0002.npz
└── ...
```

---

## 7. Fase Zero — Visualizador de Matrizes

```bash
# Visualizar um estado específico de um arquivo npz
python -m gerador_dados.visualizador \
  --arquivo dados/dataset_pequeno_0001.npz \
  --indice 0 \
  --saida visualizacoes/estado_0.png

# Visualizar um lote inteiro (primeiros 10 estados)
python -m gerador_dados.visualizador \
  --arquivo dados/dataset_pequeno_0001.npz \
  --lote 10 \
  --saida-dir visualizacoes/lote_01/
```

---

## 8. Fase Zero — Simulador Tático

```bash
# Iniciar simulador contra o Minimax (padrão, não requer modelo)
python -m gerador_dados.simulador.simulador_tatico --tamanho pequeno --modo minimax

# Iniciar simulador contra a CNN (requer modelo .tflite exportado)
python -m gerador_dados.simulador.simulador_tatico \
  --modelo modelos/arena_sagaz_pequeno.tflite \
  --tamanho pequeno \
  --modo cnn
```

> **Nota**: `pygame-ce` é utilizado no lugar do `pygame` padrão. `tflite-runtime` requer Python ≤ 3.12; em Python 3.14 use `--modo minimax`.

**Controles do simulador**:
- Clique no traço desejado para jogar (traços mostrados como pontos amarelos)
- `M` — alternar entre CNN e Minimax sem reiniciar a partida
- `R` — reiniciar partida
- `Q` — encerrar simulador

---

## 9. Deploy no Railway

```bash
# Login no Railway CLI
railway login

# Criar projeto (primeira vez)
railway init

# Definir variáveis de ambiente
railway variables set JWT_SEGREDO=<sua-chave> JWT_EXPIRACAO_MINUTOS=60 ...

# Deploy
railway up

# Verificar logs
railway logs
```

O arquivo `railway.json` na raiz do projeto já contém a configuração de
`healthcheckPath: /v1/health` e `startCommand`.

---

## 10. Estrutura do Projeto

```text
arena-sagaz-backend/
├── api/
│   ├── main.py                  # Ponto de entrada FastAPI
│   ├── configuracao.py          # Pydantic BaseSettings
│   ├── banco/
│   │   ├── conexao.py           # Engine SQLAlchemy async
│   │   └── migrations/          # Alembic
│   ├── auth/                    # Rotas, esquemas e serviço de autenticação
│   ├── usuarios/                # CRUD de usuários
│   ├── partidas/                # Sincronização de partidas
│   ├── ranking/                 # Consulta de ranking
│   ├── trofeus/                 # Modelos de troféus
│   └── nucleo/
│       ├── seguranca.py         # Utilitários JWT e bcrypt
│       ├── log.py               # Logging estruturado JSON
│       └── excecoes.py          # Exceções de domínio
├── gerador_dados/
│   ├── gerador.py               # Script principal de geração
│   ├── minimax.py               # Minimax + Poda Alpha-Beta
│   ├── tabuleiro.py             # Lógica de estado do tabuleiro
│   ├── visualizador.py          # Matriz → PNG
│   └── simulador/
│       └── simulador_tatico.py  # Interface Pygame
├── tests/
│   ├── unitarios/               # Testes sem I/O externo
│   └── integracao/              # Testes com banco real
├── sql/
│   ├── 001_trofeus_iniciais.sql
│   └── 002_selos_iniciais.sql
├── dados/                       # Dataset gerado (gitignored)
├── modelos/                     # Modelos .tflite (gitignored)
├── .env.example
├── railway.json
├── Dockerfile
└── requirements.txt
```
