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
