# Imagem do agente da caixa de borda (SDD 7.4, D-66). Construída a partir da raiz do repositório:
#   docker build -f borda/Dockerfile -t patio-caixa:local .
# Na caixa, quem sobe é o compose de infra/caixa/. Os pesos do leitor não ficam na imagem: vêm
# por um volume só de leitura, de modelos/ (e o .dockerignore nem os deixa entrar no contexto).
FROM python:3.12-slim

# Mesma versão do uv da CI e do uv.lock (como na imagem da nuvem).
RUN PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 \
    pip install --no-cache-dir uv==0.8.17

# RTSP por TCP e o FFmpeg só com os erros: os mesmos padrões do comando `caixa`.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp" \
    OPENCV_FFMPEG_LOGLEVEL=16

WORKDIR /caixa

# 1. Só as dependências (camada que muda pouco e fica em cache entre builds).
COPY pyproject.toml uv.lock ./
COPY contratos/pyproject.toml contratos/
COPY nuvem/pyproject.toml nuvem/
COPY borda/pyproject.toml borda/
COPY ferramentas/pyproject.toml ferramentas/
COPY ml/pyproject.toml ml/
RUN uv sync --frozen --no-dev --package patio-borda --no-install-workspace

# 2. O código da caixa e do contrato que ela usa.
COPY contratos/ contratos/
COPY borda/ borda/
RUN uv sync --frozen --no-dev --package patio-borda

# Não roda como root. A pasta de dados (o volume do compose: a chave, a configuração e a fila)
# é do usuário da caixa; o resto da imagem, só leitura.
RUN useradd --system --uid 10001 --no-create-home caixa \
    && mkdir -p /caixa/dados && chown caixa /caixa/dados
USER caixa

ENV PATH="/caixa/.venv/bin:$PATH"
CMD ["caixa", "rodar", "--pasta", "/caixa/dados"]
