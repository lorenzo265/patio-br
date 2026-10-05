# Fontes para as primeiras placas de treino (pesquisa de 2026-10-05)

Pergunta: de onde tirar as primeiras 3 a 5 mil placas brasileiras rotuladas, com o site parceiro
adiado (SDD 4.6, `[ABERTO-18]`). Os itens marcados com "conferido" foram lidos de novo na fonte
em 05/10; os outros vêm da pesquisa e precisam de nova leitura antes de qualquer uso.

## Bases públicas brasileiras

- **RodoSol-ALPR:** só uso acadêmico (já era conhecido; SDD 4.6).
- **UFPR-ALPR** (4.500 imagens, só placas antigas): "academic research only", não comercial.
  Mesma situação da RodoSol. https://web.inf.ufpr.br/vri/databases/ufpr-alpr/
- **UFPR-SR-Plates e LPLC** (UFPR): só acadêmico.
- **SSIG-SegPlate** (2.000 imagens): termos sob pedido; tratar como acadêmica.
- **Artificial Mercosur License Plates** (conferido): cerca de 3.840 imagens, **CC BY 4.0**.
  Fotos reais de câmeras de monitoramento e estacionamentos (Natal e Porto Alegre) em que a
  placa antiga foi trocada por uma placa Mercosul sintética. É a única base brasileira usável no
  produto (com atribuição). Se os rostos foram borrados: não confirmado.
  https://data.mendeley.com/datasets/nx9xbs4rgx/2
- **Roboflow Universe** ("Mercosul", "PlacasBrasil"): licença CC BY 4.0 declarada pelo autor,
  origem das imagens não declarada (podem vir da UFPR, da RodoSol ou da web). Fora.
- **Kaggle** (placas BR entre outras): as brasileiras vêm do `openalpr/benchmarks` (AGPL-3.0).
  Fora.
- **Hugging Face** (UniqueData, GlobalPlates): CC BY-NC-ND. Fora.

## Bases de fora, só para o detector

- **Open Images V7**, classe "Vehicle registration plate": anotações CC BY 4.0; imagens
  "listed as" CC BY 2.0, sem garantia do Google. Total da classe: não confirmado.
- **CCPD** (China, mais de 300 mil imagens): MIT. https://github.com/detectRecog/CCPD

## Placas sintéticas

- **Placa Mercosul:** fonte FE-Engschrift. A GL-Nummernschild-Eng declara permissão ilimitada,
  inclusive comercial (licença M+). https://fontlibrary.org/pl/font/gl-nummernschild-mtl
- **Placa cinza (2008 a 2018):** fonte Mandatory, grátis só para uso pessoal; a licença
  comercial é paga, com preço não publicado. https://www.k-type.com/?p=123
- **Evidência** (conferido): Laroca et al., "Advancing Multinational License Plate Recognition
  Through Synthetic and Real Data Fusion" (arXiv 2601.07671). Treinando a leitura com 700 mil
  placas sintéticas mais uma fração das reais:

  | Placas reais | Com sintéticas | Sem sintéticas |
  |---|---|---|
  | 100% | 97,9% | 93,7–95,3% |
  | 10% | 94,5–94,7% | 18,3–23,9% |
  | 1% | 86,4–87,9% | 0% |

  As bases reais do artigo incluem placas brasileiras (SSIG-SegPlate, UFPR-ALPR e RodoSol).
  https://arxiv.org/html/2601.07671
- O fast-plate-ocr (MIT) treinou o modelo da placa Mercosul argentina com placas reais e
  sintéticas.

## Leitor comercial como atalho

- **Plate Recognizer** (conferido): os termos de uso (atualizados em 03/02/2025), item 1.7,
  proíbem "(xviii) use the Service to train, develop, or improve any machine learning or
  artificial intelligence models" e "(xix) use the Service to generate training data or create
  labeled datasets for such models", com multa de US$ 5 milhões. Não serve de pré-rótulo, e o
  que ele lê não vira rótulo. https://platerecognizer.com/terms-of-use/
  - O SDK local custa o mesmo que a nuvem (US$ 50/mês por 50 mil leituras) e não manda a
    imagem para fora. https://platerecognizer.com/pricing/
- **Rekor (OpenALPR):** a licença proíbe criar oferta concorrente (item 5(K)), e a Rekor pode
  treinar com os dados do cliente (item 12). https://cdn.openalpr.com/license.html
- **Sighthound:** os termos não falam de IA; a licença do SDK não foi confirmada.

## LGPD

- A placa é dado pessoal: identifica a pessoa de forma indireta (LGPD, art. 5º, I). A cartilha
  do DNIT dá a placa de automóvel como exemplo.
- Não há guia da ANPD nem decisão sobre filmar placas para treinar modelo (não confirmado).
- Precisa de advogado: base legal e relatório de legítimo interesse, quem é o controlador numa
  coleta própria, termo com o dono do portão e aviso, filmagem em via pública e prazo de
  guarda.

## Comprar

- Nenhum fornecedor brasileiro de base de placas rotulada encontrado.
- **Unidata:** 4.388 imagens brasileiras, tiradas de vídeos do YouTube; preço sob consulta.
  Descartada pela origem.

## Opções

1. **Sintético e bases abertas, já** (sem dado pessoal): placas Mercosul sintéticas e a
   Artificial Mercosur para a leitura; Open Images e CCPD para o detector. Baixa a necessidade
   de placas reais para 1 a 2 mil (estimativa, a partir do artigo). Risco: a imagem da nossa
   portaria é diferente (caminhão, noite, ângulo).
2. **Coleta própria autorizada:** câmera e caixa em 1 a 3 portões de conhecidos, só gravando,
   com termo escrito e aviso, guardando só a região de gravação (D-39). É o plano B do
   cronograma (SDD 10, "site parceiro demora"). Risco: LGPD; precisa do sim do advogado antes.
3. **Comprar:** descartado.

## Placas reais só para testar (pesquisa da tarde de 05/10)

Pergunta do Lorenzo: dá para **testar** o leitor (não treinar) com placas reais? O teste é a
régua fixa (SDD 4.7): nunca entra no treino e fica em `dados/`, fora do Git.

- **Bases acadêmicas:** não servem sem permissão escrita dos autores. A RodoSol-ALPR (conferido)
  é "for academic research only [...] for non-commercial purposes", e o pedido exige e-mail de
  universidade. A UFPR-ALPR, a UFPR-SR-Plates e a LPLC têm termos iguais. Uma empresa testando
  o próprio produto faz uso comercial, mesmo que interno. Os termos permitem pedir a permissão
  ("expressed permission of the authors"); não achamos precedente de licença para empresa.
  Contato da RodoSol no repositório: https://github.com/raysonlaroca/rodosol-alpr-dataset
- **Fotos Creative Commons** (Wikimedia Commons, Flickr): poucas centenas de placas legíveis
  (estimativa), quase todas cinzas. A licença da foto não cobre a LGPD: quem publicou foi o
  fotógrafo, não o dono do veículo; sobra o legítimo interesse, com relatório revisado pelo
  advogado.
- **Imagens de rua** (Mapillary, Street View, KartaView): as placas são borradas, e os termos do
  Google proíbem usar o conteúdo para testar modelos.
- **Dados públicos e bases de Kaggle ou Hugging Face:** nada com origem e licença confiáveis.
- **Frota de empresa:** a LGPD protege só pessoa natural. A placa de um caminhão de LTDA ou S.A.
  não é dado pessoal da empresa; as exceções são o MEI, o empresário individual e o caminhão de
  agregado ou autônomo (912 mil dos 2,77 milhões de veículos de carga do RNTRC, ago/2025), e o
  motorista, se aparecer. Uma carta de uma página do representante legal autoriza fotografar a
  frota própria parada (só a frota própria, local, datas, finalidade, uso interno, prazo de
  guarda e contato).
- **Carros de conhecidos:** consentimento por escrito, para uma finalidade definida e revogável
  (LGPD, art. 8º); um termo de uma página basta.

**Tamanho do teste** (intervalo de 95% para um acerto de 97%):

| Placas | Margem | Intervalo |
|---|---|---|
| 300 | ±1,9 ponto | 95,1–98,9% |
| 500 | ±1,5 ponto | 95,5–98,5% |
| 1.000 | ±1,1 ponto | 95,9–98,1% |
| 2.000 | ±0,75 ponto | 96,3–97,7% |

Para mostrar, com 80% de chance, que um leitor de 97% é melhor que 95%, são cerca de 815
placas; com 90%, cerca de 1.040. Meta: **cerca de 1.000 placas distintas** (cada veículo uma
vez). Para comparar dois leitores, usar as mesmas placas nos dois.

**Caminhos, do mais limpo ao mais incerto:**

1. **Fotografar a frota própria parada** de 3 a 6 transportadoras ou locadoras, com a carta de
   autorização, guardando só o recorte da placa e a região abaixo do para-brisa (D-39). Cerca
   de 2 a 3 semanas. Risco: a foto parada é mais fácil que a portaria (luz, ângulo, movimento).
   Advogado: só para revisar a carta.
2. **Gravar no portão de um parceiro** (a coleta própria do `[ABERTO-18]`). Risco: veículos de
   terceiros. Advogado: antes de gravar.
3. **Pedir aos autores da RodoSol-ALPR** permissão escrita para avaliar no conjunto de teste
   deles (placas cinzas e Mercosul). Um e-mail; prazo e resposta incertos.
