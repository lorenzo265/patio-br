# O simulador de portaria numa imagem (T62, SDD 6.4): faz o papel de uma caixa contra a
# homologação, de qualquer máquina com Docker. Construída a partir da raiz do repositório:
#   docker build -f ferramentas/Dockerfile -t patio-simulador:local .
# A chave da caixa, a configuração e a fila ficam no volume de /simulador/dados; as passagens,
# num arquivo montado. O roteiro do piloto (docs/guias/roteiro-do-piloto.md) diz como usar.
FROM python:3.12-slim

# Mesma versão do uv da CI e do uv.lock (como nas outras imagens).
RUN PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 \
    pip install --no-cache-dir uv==0.8.17

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /simulador

# 1. Só as dependências (camada que muda pouco e fica em cache entre builds).
COPY pyproject.toml uv.lock ./
COPY contratos/pyproject.toml contratos/
COPY nuvem/pyproject.toml nuvem/
COPY borda/pyproject.toml borda/
COPY ferramentas/pyproject.toml ferramentas/
COPY ml/pyproject.toml ml/
RUN uv sync --frozen --no-dev --package patio-ferramentas --no-install-workspace

# 2. O código do simulador, da caixa que ele imita e do contrato.
COPY contratos/ contratos/
COPY borda/ borda/
COPY ferramentas/ ferramentas/
RUN uv sync --frozen --no-dev --package patio-ferramentas

# Não roda como root. Só a pasta de dados (o volume) é dele.
RUN useradd --system --uid 10002 --no-create-home simulador \
    && mkdir -p /simulador/dados && chown simulador /simulador/dados
USER simulador

ENV PATH="/simulador/.venv/bin:$PATH"
ENTRYPOINT ["simulador"]
CMD ["--help"]
