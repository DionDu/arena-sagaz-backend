FROM python:3.11-slim

WORKDIR /app

# Instala SOMENTE as dependências de runtime da API (imagem enxuta).
# O requirements.txt completo (notebook/ML/treino) NÃO entra na imagem — ele
# inclui ipython==9.12.0, que exige Python>=3.12 e quebrava este build.
COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

COPY . .

# Roda como usuário SEM privilégios (defesa em profundidade — MEL-01): se um dia
# houver RCE numa dependência, o atacante NÃO cai como root dentro do container.
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Forma "exec" com sh -c: expande o $PORT injetado pelo Railway e repassa sinais
# do SO (SIGTERM) ao uvicorn. ${PORT:-8080} usa 8080 como padrão (mesma porta do
# Custom Domain do Railway) quando $PORT não está definido.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
