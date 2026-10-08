---
tipo: "pacote"
fonte: "contratos/src/contratos/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `contratos/src/contratos/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# contratos

Pasta `contratos/src/contratos/`.

Formatos compartilhados entre a borda e a nuvem ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD, seção 3.2]]).

## Módulos

### `contratos.passagem`

`contratos/src/contratos/passagem.py`

A Passagem: o único formato que a borda envia à nuvem ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]]).

Uma passagem é o registro de um veículo passando por uma faixa da portaria: as placas lidas,
as fotos e os horários da caixa. Mudou o formato, muda a versão do contrato.

- **`PlacaLida`** (classe): Uma placa lida por uma câmera durante a passagem.
- **`Foto`** (classe): Referência a uma foto já enviada ao armazenamento; a passagem não carrega a imagem.
- **`Passagem`** (classe): Um veículo passando por uma faixa da portaria, como a caixa de borda o viu.

### `contratos.placa`

`contratos/src/contratos/placa.py`

Placa de veículo brasileira: o formato antigo e o Mercosul ([[4.2 O caminho de cada câmera, dentro da caixa|SDD 4.2]]).

A forma canônica é a que circula entre borda e nuvem: maiúsculas, sem hífen nem espaços.
A entrada aceita também a forma como as pessoas escrevem (``abc-1234``), para que o registro
manual e a importação de planilhas usem a mesma regra.

A correção de leitura por posição (``0→O``, ``1→I``...) não é desta regra: ela é do leitor, na
borda, que registra a correção com confiança menor.

- **`FORMATO_CANONICO`** = `'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'`: Antiga (``ABC1234``) e Mercosul (``ABC1D23``): só a 5ª posição muda entre as duas.
- **`PlacaInvalidaError`** (classe): O texto não é uma placa no formato antigo nem no Mercosul.
- **`normalizar_placa`**: Devolve a placa na forma canônica: maiúsculas, sem hífen nem espaços.
- **`Placa`**: Tipo de campo para modelos pydantic: aceita a placa escrita e guarda a canônica.

### `contratos.saude`

`contratos/src/contratos/saude.py`

A Saude: o que a caixa de borda conta de si à nuvem, a cada minuto ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]] e [[7.4 A caixa de borda|7.4]], [[D-65]]).

A saúde não entra na fila da caixa: sem internet, ela não é guardada, e a próxima vai um minuto
depois. Mudou o formato, muda a versão do contrato, como na passagem.

- **`TEMPERATURA_MAXIMA`** = `150.0`: Fora disso, a leitura do sensor não é de verdade.
- **`SaudeDaCamera`** (classe): Uma câmera de placa aberta pela caixa.
- **`FilaDaCaixa`** (classe): O que espera o envio na caixa.
- **`Saude`** (classe): A saúde da caixa num momento: as versões, a máquina, as câmeras e a fila.

### `contratos.schema`

`contratos/src/contratos/schema.py`

JSON Schema de cada formato do contrato (a Passagem e a Saude), gerado a partir do modelo.

Os arquivos de ``contratos/schema/`` (``passagem.v1.json``, ``saude.v1.json``) descrevem o
contrato para quem não usa Python. Eles nunca são editados à mão: depois de mudar um modelo,
rode ``uv run python -m contratos.schema``. Um teste falha se um arquivo estiver desatualizado.

- **`PASTA_DOS_SCHEMAS`**: ``contratos/schema/``, fora do código do pacote.
- **`SCHEMAS`**: Cada arquivo e o modelo de onde ele sai.
- **`gerar_schema`**: Devolve o JSON Schema do modelo como texto, pronto para gravar no arquivo.
- **`principal`**: Grava cada schema em :data:`PASTA_DOS_SCHEMAS` (com fim de linha ``\n`` em qualquer sistema).

## Testes

- `contratos/tests/test_contratos_pacote.py`: O pacote contratos é instalado pelo workspace do projeto.
- `contratos/tests/test_contratos_passagem.py`: A Passagem v1: o único formato que a borda envia à nuvem ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]]).
- `contratos/tests/test_contratos_placa.py`: Formato de placa: antigo (ABC1234) e Mercosul (ABC1D23), sempre em maiúsculas e sem hífen.
- `contratos/tests/test_contratos_saude.py`: A Saude v1: o que a caixa conta de si a cada minuto ([[3.2 O contrato entre borda e nuvem - a Passagem|SDD 3.2]] e [[7.4 A caixa de borda|7.4]], [[D-65]]).
- `contratos/tests/test_contratos_schema.py`: O JSON Schema de cada formato (a Passagem e a Saude) é gerado do modelo e fica em contratos/schema/.

---

Do [[Mapa do código]].
