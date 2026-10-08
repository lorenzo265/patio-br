"""``python -m nuvem.treino``: a pasta da base de treino (``uv run tarefas treino``, D-71).

Monta, em ``dados/treino`` (ou em ``--destino``), os recortes aceitos e corrigidos, separados
entre o treino e a régua, com um CSV de cada, para o ambiente de treino (D-40). Lê a configuração
do ambiente (``PATIO_URL_BANCO`` e o armazenamento), como a API.
"""

from nuvem.treino.exportacao import principal

principal()
