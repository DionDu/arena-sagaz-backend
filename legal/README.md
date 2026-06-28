# Documentos legais servidos pelo backend (G3)

Esta pasta guarda os documentos legais **versionados** que a API serve como
páginas HTML públicas (ver `api/legal/`).

## Estrutura

```
legal/
└── <versao>/            # ex.: 1.0  (uma pasta por versão publicada)
    ├── pt/
    │   ├── termos.md
    │   ├── privacidade.md
    │   └── exclusao-conta.md
    ├── en/ (idem)
    └── es/ (idem)
```

## URLs

- **Vigente:** `GET /legal/<idioma>/<documento>` (cache curto). A versão vigente é
  a constante `VERSAO_LEGAL` em `api/legal/rotas.py`.
- **Fixa/imutável:** `GET /legal/<versao>/<idioma>/<documento>` (cache de 1 ano,
  `immutable`). Ex.: `/legal/1.0/pt/privacidade`.
- **Índice:** `GET /legal`.

Idiomas: `pt | en | es`. Documentos: `termos | privacidade | exclusao-conta`.

## Imutabilidade e sincronização

- Cada pasta `legal/<versao>/` é **congelada** depois de publicada — nunca edite
  uma versão já no ar; **crie uma nova** (`legal/1.1/…`).
- Ao subir de versão, atualize **juntos**: `VERSAO_LEGAL` (aqui, backend) e
  `versaoLegal` no app (`lib/core/legal/documentos_legais.dart`). Isso dispara o
  **re-aceite** dos termos no app (T052).
- O texto-fonte de cada versão é uma cópia dos documentos do app
  (`arena-sagaz-frontend/legal/<idioma>/`) no momento da publicação. O app embute a
  versão vigente (offline); o backend serve a URL canônica online (lojas).

> Os rascunhos v1.0 (28/06/2026) são iniciais — revisar (idealmente com apoio
> jurídico) antes de considerar definitivos. Não são aconselhamento jurídico.
