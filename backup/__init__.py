"""O backup diário do banco do `prd` no Google Drive (T101 da spec 009).

Este pacote é a **imagem própria** de um serviço de cron do Railway
(`Dockerfile.backup`): acorda às 04:00 UTC, copia o banco, criptografa, envia
para o Drive, apaga o que passou do prazo e termina.

⚠️ **Só biblioteca padrão do Python, de propósito.** A imagem parte da oficial
`postgres:18` (é ela que garante um `pg_dump` da mesma versão do servidor) e usa o
Python que o Debian traz. Sem `pip install`, não há dependência para envelhecer,
quebrar o build numa madrugada ou pedir atualização de segurança.

Os módulos, do mais puro ao mais impuro:

- `retencao.py` - a regra de quanto tempo cada backup fica (função pura);
- `drive.py` - o Google Drive pela API REST (só `urllib`);
- `backup_do_banco.py` - o fluxo de uma execução, que junta os dois;
- `autorizar_drive.py` - roda **uma vez**, no PC do dono, para obter a autorização.

O plano e as decisões do dono: `arena-sagaz-frontend/specs/009-desafio-do-dia/
plano-backup-prd.md` e `arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zv.
"""
