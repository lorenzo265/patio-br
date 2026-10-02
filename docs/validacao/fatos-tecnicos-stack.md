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
