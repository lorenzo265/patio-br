# Imagem da API da nuvem (SDD 7.2). Construída a partir da raiz do repositório:
#   docker build -f nuvem/Dockerfile .
# No ambiente local, quem constrói e sobe é o `uv run tarefas up` (infra/docker-compose.yml).
FROM python:3.12-slim

# Mesma versão do uv da CI e do uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Só as dependências (camada que muda pouco e fica em cache entre builds).
COPY pyproject.toml uv.lock ./
COPY contratos/pyproject.toml contratos/
COPY nuvem/pyproject.toml nuvem/
COPY borda/pyproject.toml borda/
COPY ferramentas/pyproject.toml ferramentas/
COPY ml/pyproject.toml ml/
RUN uv sync --frozen --no-dev --package patio-nuvem --no-install-workspace

# 2. O código da nuvem e do contrato que ela usa.
COPY contratos/ contratos/
COPY nuvem/ nuvem/
RUN uv sync --frozen --no-dev --package patio-nuvem

# Não roda como root.
RUN useradd --system --no-create-home patio
USER patio

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "nuvem.principal:criar_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
