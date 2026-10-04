# Fatos técnicos para o SDD (verificados em 2026-09-29)

## Licenças
- Ultralytics YOLO (v8/v11/YOLO26): AGPL-3.0; licença Enterprise exigida para uso comercial fechado, preço não publicado. https://www.ultralytics.com/license
- Apache-2.0: YOLOX, RT-DETR/RT-DETRv2 (lyuwenyu), D-FINE, DEIM, PaddleDetection/PP-YOLOE, PaddleOCR, EasyOCR, parseq, OpenVINO, RF-DETR (Nano a Large; XL/2XL em PML 1.0).
- YOLO-NAS: pesos proíbem uso comercial.
- MIT: fast-plate-ocr, fast-alpr, open-image-models (código; licença dos pesos não explícita; "YOLOv9-based"; YOLOv9 oficial é GPL-3.0, reimplementação MultimediaTechLab é MIT), ByteTrack, supervision, ONNX Runtime, go2rtc, MediaMTX, Frigate (LPR nativo desde 0.16, YOLOv9 leve + PaddleOCR).
- norfair: BSD-3. TensorRT: runtime redistribuível com atribuição (SLA NVIDIA). DeepStream: binários sob SLA NVIDIA.

## Leitores comerciais
- Plate Recognizer: Snapshot/SDK US$ 50/mês (50 mil consultas), US$ 150 (250 mil), US$ 250 (500 mil); Stream US$ 35/câmera/mês; assinatura exige internet a cada 30 dias; declara >98% no Brasil.
- Rekor Scout: US$ 12 (nuvem) a US$ 72 (self-hosted) por câmera/mês.
- Pumatronix JIDOSHA: ~R$ 4.385-4.615 por licença (revendedor, esgotado); lê Mercosul e antiga; Linux x86/ARM.

## Hardware de borda (R$)
- Mini PC N150 16 GB/512 GB: R$ 3.513-3.698 (KaBuM); N100 8 GB: R$ 2.575-2.711; N100 16 GB a partir de R$ 1.799 (Amazon, não aberto).
- Jetson Orin Nano Super: R$ 3.325 (RoboCore, esgotado) a R$ 8.989-14.990.
- Hailo-8L AI HAT+: R$ 855; Hailo-8: R$ 1.330 (esgotado).
- Benchmarks: N100 OpenVINO iGPU YOLOv9 s-320 30 ms; N150 YOLOv9 t-320 16 ms; YOLOv8n INT8 N100 iGPU 15-20 FPS; RT-DETR R18 Orin Nano TensorRT FP16 81 FPS.

## Hospedagem
- AWS Lightsail sa-east-1: US$ 5/7/12/24 por mês (0,5/1/2/4 GB).
- RDS PostgreSQL sa-east-1 db.t4g.micro ~US$ 24,8/mês + US$ 0,219/GB-mês.
- S3 sa-east-1: US$ 0,0405/GB-mês.
- Fly.io GRU existe (x1,615 do preço IAD). Supabase Pro US$ 25/mês (sa-east-1). Neon aws-sa-east-1 existe.
- Magalu Cloud: VM 1 vCPU/1 GB R$ 34,99/mês; PostgreSQL gerenciado 1 vCPU/4 GB R$ 94,22/mês; objetos R$ 0,10/GiB-mês.
- Cloudflare R2: US$ 0,015/GB-mês, sem região na América do Sul.

## Gestão remota
- Tailscale Personal: grátis mas não comercial; Standard US$ 8/usuário/mês; 50 recursos com tag inclusos.
- balenaCloud: grátis até 10 dispositivos; Prototype US$ 159/mês.
- Mender: open source (Apache-2.0) auto-hospedável; hospedado US$ 34/mês até 50 dispositivos.
- Watchtower: não é mais mantido.

## WhatsApp
- Cloud API oficial direta permitida para app próprio; sem taxa de plataforma listada; cobrança por mensagem.
- Brasil a partir de 01/10/2026: utility/authentication/service R$ 0,035; marketing R$ 0,3217.
- Portfólio novo limitado a 250 destinatários únicos/24h; 2.000 após verificação.
- Bibliotecas não oficiais (Baileys, whatsapp-web.js) violam os Termos do WhatsApp.

## Câmeras
- Intelbras VIP 3430 B IA: RTSP, ONVIF S/T, stream principal 2688x1520 até 20 fps, stream extra até 704x480; IA de humano/veículo, sem LPR.
- LPR embarcado só em linhas dedicadas (Intelbras VIP 5460 LPR IA: identifica tipo de veículo, envia fotos por FTP/SFTP; Hikvision TCG/TCM via ISAPI).

## Pesos do leitor v0 (T13, verificados em 2026-10-03)

Regra (SDD 4.1): no produto, só pesos treinados por nós. Peso de terceiro sem licença clara
para uso comercial serve só para avaliação interna, e isso fica escrito aqui. Fontes abertas
uma a uma (GitHub, Hugging Face, PyPI, ModelScope); nada vem de resumo de busca.

| Modelo | Código | Pesos | Treinado em | Onde ficam os pesos | Veredito |
|---|---|---|---|---|---|
| D-FINE-N (COCO) | Apache-2.0 ([LICENSE](https://github.com/Peterande/D-FINE/blob/master/LICENSE)) | **sem licença declarada**: só a do repositório. O README avisa que pesos com Objects365 "should not be assumed to be commercially cleared under the D-FINE license" | COCO (o N não usa Objects365). O backbone HGNetV2-B0 baixa pesos pré-treinados da Paddle sem dados declarados (`pretrained: True` na configuração) | [Peterande/storage, release dfinev1.0](https://github.com/Peterande/storage/releases/tag/dfinev1.0), `dfine_n_coco.pth`, sem sha256 publicado | **só avaliação interna** |
| YOLOX-Tiny e Nano | Apache-2.0 ([LICENSE](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE)) | **sem licença declarada** | COCO | [release 0.1.1rc0](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0), já em ONNX (`yolox_tiny.onnx`, `yolox_nano.onnx`), sem sha256 publicado | **só avaliação interna** |
| PP-OCRv4 e v5, detecção e leitura (PaddleOCR) | Apache-2.0 ([LICENSE](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE)) | **Apache-2.0 declarada** no cartão de cada modelo da organização PaddlePaddle (verificada) no Hugging Face, ex.: [PP-OCRv5_mobile_det](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det), [PP-OCRv5_mobile_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx) | não declarado | Hugging Face, inclusive em ONNX (`*_onnx`) | licença permite uso comercial; no produto, só se o SDD 4.1 mudar |
| RapidOCR (ONNX convertidos do PaddleOCR) | Apache-2.0 ([LICENSE](https://github.com/RapidAI/RapidOCR/blob/main/LICENSE)) | **Apache-2.0 declarada** ([README](https://github.com/RapidAI/RapidOCR/blob/main/README.md): "Converted model artifacts... are redistributed under the same license terms"; [MODEL_LICENSES.md](https://github.com/RapidAI/RapidOCR/blob/main/python/MODEL_LICENSES.md) cobre os três modelos da roda) | o mesmo do PaddleOCR | a roda do `rapidocr` 3.9.2 traz o PP-OCRv6 small; os outros vêm do ModelScope, com sha256 conferido no download | licença ok, mas o pacote exige o `opencv_python` (ver abaixo) |
| fast-plate-ocr | MIT ([LICENSE](https://github.com/ankandrew/fast-plate-ocr/blob/master/LICENSE)) | **sem licença declarada** | não divulgado; a configuração v2 lista "Brazil" entre as regiões, sem dizer de onde vieram as placas (risco de RodoSol-ALPR, que o SDD 4.6 proíbe) | [release arg-plates](https://github.com/ankandrew/fast-plate-ocr/releases/tag/arg-plates); o GitHub mostra sha256; a biblioteca não confere | **só avaliação interna** |
| ONNX Runtime | MIT ([LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)) | — | — | PyPI `onnxruntime` | pode entrar |
| OpenVINO | Apache-2.0 ([LICENSE](https://github.com/openvinotoolkit/openvino/blob/master/LICENSE)) | — | — | PyPI `openvino` | pode entrar |

Sobre o COCO (todos os detectores acima): as anotações são CC BY 4.0, mas "The COCO Consortium
does not own the copyright of the images. Use of the images must abide by the Flickr Terms of
Use" ([termos](https://cocodataset.org/#termsofuse)). O Objects365 é "available for the
academic purpose only" ([download](https://www.objects365.org/download.html)).

**Para o v0:** o detector de veículos (D-FINE-N ou YOLOX) só pode rodar em avaliação interna,
porque os pesos não têm licença declarada. O OCR do PaddleOCR tem pesos com Apache-2.0
declarada. O v0 inteiro fica, então, só para avaliação interna e para a demonstração do mês 1,
como o SDD 4.1 já permite; o leitor do produto é o v1, com pesos nossos (mês 2). Para treinar o
v1 a partir do D-FINE, a configuração precisa de `pretrained: False` no backbone, ou o treino
parte de pesos de terceiros.

## O que vem dentro das rodas (bibliotecas nativas, verificado em 2026-10-03)

A CI confere só a licença do pacote Python (`pip-licenses`). Algumas rodas trazem, dentro,
bibliotecas nativas com outra licença. Conferido abrindo as rodas para Linux x86-64 do PyPI:

| Pacote | Licença do pacote | O que vem dentro |
|---|---|---|
| `av` 19.0.1 (PyAV) | BSD-3-Clause | FFmpeg com **libx264 e libx265 (GPL-2.0)**: o FFmpeg dessa roda é montado como GPL |
| `supervision` 0.30.6 (ByteTrack) | MIT | exige `av>=14.2`, o PyAV acima |
| `opencv-python` e `-headless` 5.0 | Apache-2.0 | "All wheels ship with FFmpeg licensed under the LGPLv2.1"; a não-headless traz Qt (LGPLv3) ([README](https://github.com/opencv/opencv-python#licensing)) |
| `rapidocr` 3.9.2 | Apache-2.0 | exige `opencv_python` (a não-headless) |
| `numpy` 2.5 e `scipy` 1.18 | BSD | `libgfortran` (GPL-3.0 com a exceção de runtime do GCC, que permite programa fechado) e **`libquadmath` (LGPL-2.1)** |
| `pillow` 12.3 | MIT-CMU | nada GPL nem LGPL (libjpeg, libpng, libtiff, libwebp, FreeType pela licença FTL, HarfBuzz, lcms2, OpenJPEG, zstd, brotli, libavif) |

Isso vira o `[ABERTO-13]` do SDD: a regra "GPL e LGPL nunca" esbarra no FFmpeg (PyAV, OpenCV)
e até na NumPy, que o ONNX Runtime exige. Decidido em 04/10 (SDD D-27): LGPL nativa sem
modificação e carregada dinamicamente entra; GPL só com a exceção de runtime do GCC; FFmpeg só
sem partes GPL.

### A roda do OpenCV, aberta (verificado em 2026-10-04)

`opencv-python-headless` 5.0.0.93 (Apache-2.0), o decodificador de vídeo da caixa (SDD D-29):

| Roda | O que vem dentro | Licença |
|---|---|---|
| Linux x86-64 | FFmpeg (`libavcodec` 62, `libavformat`, `libavutil`, `libswscale`, `libswresample`) | **LGPL 2.1**: as próprias bibliotecas dizem "license: LGPL version 2.1 or later"; montado sem `--enable-gpl` e sem `--enable-nonfree`; nada de x264 nem x265 |
| Linux x86-64 | `libvpx`, `libaom`, `libavif`, OpenBLAS, `libpng`, `libdrm` | BSD, BSD-2, BSD-2, BSD-3, libpng, MIT |
| Linux x86-64 | `libgfortran`, `libquadmath` | GPL-3.0 com a exceção de runtime do GCC; LGPL-2.1 (os mesmos da NumPy) |
| Linux x86-64 | **OpenSSL 1.1.1w** (`libssl`, `libcrypto`), porque o FFmpeg foi montado com `--enable-openssl` | OpenSSL/SSLeay: estilo BSD, com cláusula de propaganda; a série 1.1 não recebe correções desde 2023 (`[ABERTO-14]`, aceito em 04/10: SDD D-31) |
| Windows x86-64 | uma DLL só, `opencv_videoio_ffmpeg500_64.dll`, com o FFmpeg dentro | **LGPL 2.1** ("libswscale license: LGPL version 2.1 or later"); nada de x264, x265 nem OpenSSL |

A lista e o texto das licenças vêm na própria roda, em `cv2/LICENSE-3RD-PARTY.txt`.
