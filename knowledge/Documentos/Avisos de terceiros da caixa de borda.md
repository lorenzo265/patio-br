---
tipo: "documento"
fonte: "borda/AVISOS-DE-TERCEIROS.md"
gerada: true
tags: [documento]
---

> [!note] Gerada de `borda/AVISOS-DE-TERCEIROS.md` por `uv run tarefas conhecimento`: para mudar, mude a fonte e gere de novo.

# Avisos de terceiros da caixa de borda

A caixa usa bibliotecas de terceiros, cada uma com a sua licença ([[6.1 Stack|SDD 6.1]], [[D-27]], [[D-29]] e [[D-31]]).
O texto completo de cada licença vem dentro do pacote instalado; o do OpenCV e das bibliotecas
que vêm dentro dele, em `cv2/LICENSE-3RD-PARTY.txt`.

Este arquivo guarda os créditos que as licenças pedem. Quem acrescenta uma dependência confere a
roda e anota aqui o que a licença pedir ([[CLAUDE - regras do repositório|CLAUDE.md]], regra 1).

## OpenSSL (dentro do OpenCV para Linux)

A roda do `opencv-python-headless` para Linux traz o OpenSSL 1.1.1w, usado pelo FFmpeg dela
(SDD [[D-31]]). A licença OpenSSL/SSLeay pede estes créditos, que ficam em inglês, como estão:

> This product includes software developed by the OpenSSL Project for use in the OpenSSL
> Toolkit (http://www.openssl.org/).

> This product includes cryptographic software written by Eric Young (eay@cryptsoft.com).

Material de divulgação que cite um recurso que use o OpenSSL precisa trazer esses créditos.

## O que vem dentro das rodas da caixa

| Componente | Vem em | Licença | Como é usado |
|---|---|---|---|
| FFmpeg (`libavcodec`, `libavformat`, `libavutil`, `libswscale`, `libswresample`) | `opencv-python-headless` | LGPL 2.1 | sem modificação, carregado dinamicamente ([[D-27]]); o código-fonte e a montagem estão no projeto [opencv-python](https://github.com/opencv/opencv-python) |
| OpenSSL 1.1.1w | `opencv-python-headless` (Linux) | OpenSSL/SSLeay | créditos acima ([[D-31]]) |
| `libvpx`, `libaom`, `libavif`, OpenBLAS, `libpng`, `libdrm` | `opencv-python-headless` (Linux) | BSD, BSD-2, BSD-2, BSD-3, libpng, MIT | sem modificação |
| `libquadmath` | NumPy e OpenCV (Linux) | LGPL 2.1 | sem modificação, carregada dinamicamente ([[D-27]]) |
| `libgfortran` | NumPy e OpenCV (Linux) | GPL 3.0 com a exceção de runtime do GCC | sem modificação ([[D-27]]) |

O que foi conferido em cada roda está em [[Validação - fatos técnicos da stack|docs/validacao/fatos-tecnicos-stack.md]].
