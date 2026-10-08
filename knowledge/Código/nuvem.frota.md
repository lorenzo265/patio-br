---
tipo: "pacote"
fonte: "nuvem/src/nuvem/frota/"
gerada: true
tags: [codigo]
---

> [!note] Gerada de `nuvem/src/nuvem/frota/` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# nuvem.frota

Pasta `nuvem/src/nuvem/frota/`.

Frota de borda ([[3.3 Módulos da nuvem no MVP|SDD 3.3]] e [[7.4 A caixa de borda|7.4]]): as caixas de cada site, a ativação e a chave de cada uma.

## Módulos

### `nuvem.frota.acesso`

`nuvem/src/nuvem/frota/acesso.py`

A caixa que está chamando a nuvem: identificada pela chave em ``Authorization: Bearer``.

- **`obter_caixa`**: Dependência do FastAPI: a caixa dona da chave.

### `nuvem.frota.modelos`

`nuvem/src/nuvem/frota/modelos.py`

Tabelas da frota: os códigos de ativação, as caixas de borda, a saúde e as versões delas (SDD
5.1 e 7.4).

As de dados do cliente têm ``empresa_id`` e apontam para o pai pela dupla (pai, empresa), como
toda tabela filha ([[5.5 Garantias|SDD 5.5]]). As versões são da plataforma ([[D-67]]).

- **`CodigoAtivacao`** (classe): Um código de uso único que a administração gera para ativar uma caixa num site.
- **`CaixaBorda`** (classe): Uma caixa de borda (mini PC na portaria) ativada num site.
- **`SaudeCaixa`** (classe): Uma saúde recebida de uma caixa: o histórico curto, de 7 dias ([[D-65]]).
- **`ResultadoDaAtualizacao`** = `Literal['ok', 'voltou', 'falhou']`: Deu certo, voltou para a versão anterior (a saúde não veio) ou falhou antes de trocar.
- **`VersaoCaixa`** (classe): Uma versão do agente da caixa, pela imagem e pelo resumo dela ([[D-67]]).
- **`EscolhaDeVersao`** (classe): A versão escolhida para todas as caixas, para um site ou para uma caixa ([[D-67]]).
- **`AtualizacaoCaixa`** (classe): Uma troca de versão, como a caixa contou ([[D-67]]). Só se acrescenta.

### `nuvem.frota.rotas`

`nuvem/src/nuvem/frota/rotas.py`

Rotas da frota: a caixa ativa, baixa a configuração, manda a saúde, pergunta a versão e conta
as atualizações; a administração gera códigos, revoga caixas e cuida das versões ([[D-67]]).

Os identificadores que a caixa recebe são os ids da nuvem em texto (SDD [[D-21]]): são os mesmos
que ela põe nas passagens.

- **`PedidoDeAtivacao`** (classe): O que a caixa manda para se ativar.
- **`Ativacao`** (classe): O que a caixa recebe ao se ativar. Guarde a chave: ela não aparece de novo.
- **`CameraDaConfiguracao`** (classe): Uma câmera, com o que a caixa precisa para ler o vídeo dela.
- **`FaixaDaConfiguracao`** (classe): Uma faixa do site, com as câmeras dela.
- **`Configuracao`** (classe): A configuração da caixa: o site dela, as faixas e as câmeras.
- **`CodigoDeAtivacao`** (classe): Um código gerado para a administração entregar a quem instala a caixa.
- **`CaixaPublica`** (classe): Uma caixa como a administração a vê.
- **`VersaoParaCaixa`** (classe): A versão que vale para a caixa: o nome e a imagem pelo resumo.
- **`AtualizacaoRegistrada`** (classe): A atualização gravada.
- **`PedidoDeVersao`** (classe): Uma versão nova do agente ([[D-67]]).
- **`VersaoPublica`** (classe): Uma versão como a administração a vê.
- **`PedidoDeEscolha`** (classe): Para quem vale a versão: uma caixa, um site ou (sem os dois) todas as caixas.
- **`EscolhaPublica`** (classe): A escolha gravada.
- **`ativar`**: Troca o código de ativação pela chave da caixa (401 se o código não vale).
- **`configuracao`**: As faixas e câmeras do site da caixa, com a senha das câmeras.
- **`receber_saude`**: A saúde da caixa, a cada minuto ([[D-65]]): 403 se é de outra caixa ou de outro site.
- **`versao_da_caixa`**: A versão que vale para a caixa ([[D-67]]); 204 se nenhuma foi escolhida.
- **`contar_atualizacao`**: A troca de versão que a caixa fez ([[D-67]]); 422 se o resumo não é de uma versão.
- **`gerar_codigo`**: Gera um código de ativação para o site (vale 24 horas, uma vez).
- **`listar_caixas`**: Todas as caixas, das mais novas para as mais antigas.
- **`revogar`**: Revoga a chave da caixa (404 se a caixa não existir).
- **`cadastrar_versao`**: Cadastra uma versão do agente pelo resumo da imagem (422 se fora do formato ou repetida).
- **`listar_versoes`**: As versões, das mais novas para as mais antigas, com as caixas em que deram certo.
- **`escolher_versao`**: Escolhe a versão para uma caixa, um site ou todas (409 se ainda não deu certo numa caixa).

### `nuvem.frota.saude`

`nuvem/src/nuvem/frota/saude.py`

A saúde das caixas de borda na nuvem ([[7.4 A caixa de borda|SDD 7.4]], [[D-65]]).

- **Receber:** a saúde atualiza a caixa (o último contato, as versões, a última saúde e a
  diferença do relógio) e entra no histórico; o histórico da caixa com mais de 7 dias se apaga.
- **Sem contato:** a última saúde chegou há 3 minutos ou mais. A caixa que nunca mandou saúde
  não conta (o site da demonstração tem caixa sem programa rodando).
- **A portaria** vê "site sem conexão desde HH:MM"; **a administração** vê a frota e o
  histórico de cada caixa, hora a hora.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`LIMITE_SEM_CONTATO`** = `timedelta(minutes=3)`: Sem saúde por este tempo, a caixa está sem contato (o tempo do alerta, [[ABERTO-09]]).
- **`SAUDES_POR_HORA`** = `60`: Uma saúde por minuto: a hora sem falta tem 60.
- **`SaudeDeOutraCaixaError`** (classe): A saúde diz outra caixa ou outro site que não os da chave (403).
- **`CameraNaFrota`** (classe): Uma câmera de placa, como a caixa contou na última saúde.
- **`CaixaNaFrota`** (classe): Uma caixa como a administração a vê na frota.
- **`HoraDaCaixa`** (classe): O resumo de uma hora do histórico de uma caixa (no fuso do site).
- **`receber_saude`**: Grava a saúde que a caixa mandou e apaga o histórico dela com mais de 7 dias.
- **`sem_contato`**: Se a caixa está sem contato: mandou saúde, e a última chegou há 3 minutos ou mais.
- **`sem_conexao_desde`**: Desde quando o site está sem conexão: o último contato da caixa que sumiu (a mais antiga, se forem várias); ``None`` se nenhuma caixa do site sumiu.
- **`frota`**: As caixas não revogadas de todas as empresas, das mais novas para as mais antigas.
- **`caixa_da_frota`**: Uma caixa da frota (também a revogada).
- **`historico_por_hora`**: Os últimos 7 dias da caixa, hora a hora, no fuso do site; a hora mais recente primeiro.
- **`nomes_das_cameras`**: O nome de cada câmera dos sites, por (site, id da câmera em texto, como vem na saúde).

### `nuvem.frota.servico`

`nuvem/src/nuvem/frota/servico.py`

Regras da frota: ativação da caixa de borda com código de uso único e chave própria.

1. A administração gera um código para um site (vale 24 horas e uma vez só).
2. A caixa troca o código por uma chave; a nuvem guarda só o resumo da chave.
3. Toda chamada da caixa leva a chave (``Authorization: Bearer``); revogada, não vale mais.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`ALFABETO_DO_CODIGO`** = `'23456789ABCDEFGHJKMNPQRSTUVWXYZ'`: Letras e números sem os que se confundem ao digitar (0 e O, 1, I e L).
- **`TAMANHO_DO_CODIGO`** = `12`: 12 sorteios em 31 símbolos: perto de 59 bits, impossível de adivinhar em 24 horas.
- **`CodigoRecusadoError`** (classe): O código de ativação não existe, já foi usado ou venceu (sem dizer qual).
- **`CodigoGerado`** (classe): O código como a administração o entrega a quem instala a caixa (``XXXX-XXXX-XXXX``).
- **`CaixaAtivada`** (classe): O que a caixa recebe na ativação; a chave aparece só aqui, uma vez.
- **`AcessoDaCaixa`** (classe): Uma caixa identificada pela chave: o site e a empresa dela.
- **`ConfiguracaoDaCaixa`** (classe): O que a caixa baixa da nuvem para trabalhar ([[7.4 A caixa de borda|SDD 7.4]]).
- **`gerar_codigo_de_ativacao`**: Gera um código de ativação de uso único para um site.
- **`ativar`**: Troca um código de ativação por uma caixa nova no site do código, com chave própria.
- **`caixa_da_chave`**: Devolve a caixa dona da chave, ou ``None`` se a chave não existir ou foi revogada.
- **`caixa_do_site`**: A primeira caixa não revogada de um site, ou ``None``.
- **`configuracao`**: As faixas e câmeras do site da caixa (com a senha das câmeras decifrada).
- **`revogar`**: Revoga a chave da caixa: as chamadas dela passam a receber 401. Revogar de novo não muda a data da primeira revogação.
- **`listar_caixas`**: Todas as caixas, das mais novas para as mais antigas. Só para a administração.

### `nuvem.frota.versoes`

`nuvem/src/nuvem/frota/versoes.py`

As versões da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-14]] e [[D-67]]).

- **Cadastrar:** a administração cadastra cada versão pelo nome e pela imagem com o resumo
  (``sha256:…``): a caixa só baixa a imagem pelo resumo, que o Docker confere.
- **Escolher:** para todas as caixas, para um site ou para uma caixa. Vence a escolha mais
  específica (a da caixa, depois a do site, depois a de todas); em cada alcance vale a última.
- **A ordem:** uma versão só vai para um site ou para todas depois de dar certo numa caixa.
- **As atualizações** são contadas pela caixa e aparecem na frota.

As funções gravam com ``flush``; o ``commit`` é de quem chama.

- **`FORMATO_DA_IMAGEM`**: O repositório, sem etiqueta nem resumo (ex.: ``ghcr.io/<conta>/patio-caixa``).
- **`VersaoNaoProvadaError`** (classe): A versão ainda não deu certo numa caixa: só pode ir para uma caixa (409).
- **`RelatoDeAtualizacao`** (classe): O que a caixa conta de uma troca de versão (``POST /api/borda/atualizacoes``).
- **`VersaoNaListagem`** (classe): Uma versão, com em quantas caixas ela já deu certo.
- **`cadastrar_versao`**: Cadastra uma versão do agente.
- **`escolher_versao`**: Escolhe a versão para uma caixa, para um site ou (sem os dois) para todas as caixas.
- **`versao_da_caixa`**: A versão que vale para a caixa (a da caixa, a do site ou a de todas), ou ``None``.
- **`registrar_atualizacao`**: Grava a troca de versão que a caixa contou.
- **`listar_versoes`**: As versões, das mais novas para as mais antigas, com as caixas em que deram certo.
- **`atualizacoes_da_caixa`**: As últimas atualizações da caixa, das mais novas para as mais antigas, com a versão.
- **`Alcances`** (classe): Para quem a administração pode escolher uma versão: os sites e as caixas no ar.
- **`alcances`**: Os sites com caixa não revogada e as caixas não revogadas, para o formulário da escolha.

## Testes

- `nuvem/tests/test_nuvem_frota_ativacao.py`: Ativação da caixa de borda ([[7.4 A caixa de borda|SDD 7.4]]): código de uso único, chave própria, revogação.
- `nuvem/tests/test_nuvem_frota_rotas.py`: Rotas da frota: a administração gera o código; a caixa ativa e baixa a configuração.
- `nuvem/tests/test_nuvem_frota_saude.py`: A saúde da caixa na nuvem ([[7.4 A caixa de borda|SDD 7.4]], [[D-65]]): o último contato, o histórico e a frota.
- `nuvem/tests/test_nuvem_frota_versoes.py`: As versões da caixa ([[7.4 A caixa de borda|SDD 7.4]], [[D-67]]): cadastrar, escolher por alcance, a ordem (uma caixa antes das outras) e as atualizações contadas pela caixa.

---

Do [[Mapa do código]].
